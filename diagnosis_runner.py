"""
diagnosis_runner.py

既存 main.py のバックエンド処理を Web API から呼び出せるように再構成。
診断の各ステップをジェネレータで yield し、
フロントエンドへ SSE（Server-Sent Events）でリアルタイム進捗を送る。

認証情報・ARN・Session Token はフロントへ一切露出しない。
"""

import os
import json
import math
import subprocess
import time
import threading
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from backend.input.hearing_reader import load_hearing_sheet
from backend.input.hearing_validator import validate_hearing_sheet
from backend.aws.aws_connector import assume_role
from backend.ai.ai_input_builder import build_mfa_ai_inputs
from backend.ai.bedrock_evaluator import evaluate_mfa

load_dotenv()

OUTPUT_BASE = Path("output")

BEDROCK_INFERENCE_PROFILE_ID = os.getenv("BEDROCK_INFERENCE_PROFILE_ID")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "ap-northeast-1")
USD_TO_JPY = float(os.getenv("USD_TO_JPY", "155"))


# ============================================================
# 進捗管理
# ============================================================

# diagnosis_id -> {"steps": [...], "status": "running|done|error", "result": {...}}
_diagnosis_store: dict = {}
_store_lock = threading.Lock()


def _set_step(diagnosis_id: str, step: str, status: str, message: str = ""):
    with _store_lock:
        store = _diagnosis_store.setdefault(diagnosis_id, {"steps": [], "status": "running", "result": None, "error": None})
        # 既存ステップを更新 or 追加
        for s in store["steps"]:
            if s["step"] == step:
                s["status"] = status
                s["message"] = message
                return
        store["steps"].append({"step": step, "status": status, "message": message})


def get_diagnosis_progress(diagnosis_id: str):
    with _store_lock:
        return dict(_diagnosis_store.get(diagnosis_id, {}))


def get_all_diagnosis_ids():
    with _store_lock:
        return list(_diagnosis_store.keys())


# ============================================================
# Prowler OCSF JSON → Finding 共通モデル変換
# ============================================================

def _parse_findings(output_path: Path) -> list[dict]:
    """
    Prowler の OCSF JSON を読み込み、
    フロントエンドで扱いやすい共通 Finding モデルに変換する。

    共通 Finding モデル:
    {
        "check_id": str,          # iam_root_mfa_enabled 等
        "check_title": str,       # 表示用タイトル
        "category": str,          # MFA 等
        "target_type": str,       # ROOT / IAM_USER
        "target": str,            # ユーザー名
        "cspm_status": str,       # PASS / FAIL
        "severity": str,          # Critical / High 等（Prowler原値）
        "message": str,           # Prowler の検出メッセージ
        "ai_result": dict | None  # AI評価結果（FAILのみ）
    }
    """

    json_files = list(output_path.glob("*.ocsf.json"))
    if not json_files:
        return []

    with open(json_files[0], "r", encoding="utf-8") as f:
        raw_findings = json.load(f)

    CHECK_TITLE_MAP = {
        "iam_root_mfa_enabled": "Root MFA",
        "iam_user_mfa_enabled_console_access": "IAM User MFA",
    }

    TARGET_TYPE_MAP = {
        "iam_root_mfa_enabled": "ROOT",
        "iam_user_mfa_enabled_console_access": "IAM_USER",
    }

    findings = []
    for raw in raw_findings:
        check_id = raw.get("metadata", {}).get("event_code", "")
        status = raw.get("status_code", "")
        severity = raw.get("severity", "")
        message = raw.get("message", "")

        # 対象名を取得（ARN等は含めない）
        resources = raw.get("resources", [])
        target = "unknown"
        if resources:
            r = resources[0]
            name = r.get("name")
            if name:
                target = name
            else:
                uid = r.get("uid", "")
                if "/" in uid:
                    target = uid.rsplit("/", 1)[-1]
                elif ":" in uid:
                    target = uid.rsplit(":", 1)[-1]

        findings.append({
            "check_id": check_id,
            "check_title": CHECK_TITLE_MAP.get(check_id, check_id),
            "category": "MFA",
            "target_type": TARGET_TYPE_MAP.get(check_id, "UNKNOWN"),
            "target": target,
            "cspm_status": status,
            "severity": severity,
            "message": message,
            "ai_result": None,
        })

    return findings


def _merge_ai_results(findings: list[dict], ai_results: list[dict]) -> list[dict]:
    """
    Finding リストに AI 評価結果をマージする。
    ai_results は {"target": str, "evaluation": dict} のリスト。
    """
    ai_map = {r["target"]: r["evaluation"] for r in ai_results}
    for f in findings:
        if f["cspm_status"] == "FAIL":
            f["ai_result"] = ai_map.get(f["target"])
    return findings


# ============================================================
# AI 料金計算ユーティリティ
# ============================================================

def _calc_cost_display(cost_usd: float) -> dict:
    cost_jpy = cost_usd * USD_TO_JPY
    cost_usd_display = math.ceil(cost_usd * 10000) / 10000
    cost_jpy_display = math.ceil(cost_jpy * 10000) / 10000
    return {
        "usd": cost_usd_display,
        "jpy": cost_jpy_display,
        "usd_str": f"${cost_usd_display:.4f}",
        "jpy_str": f"¥{cost_jpy_display:.4f}",
    }


# ============================================================
# 診断結果サマリー生成
# ============================================================

def _build_summary(hearing: dict, findings: list[dict], ai_results: list[dict], timestamp: str) -> dict:
    basic = hearing.get("基本情報", {})
    system_name = basic.get("診断対象システムの名称は？", "")
    cloud = basic.get("利用しているクラウドサービスは？", "AWS")
    account_id = basic.get("診断対象のAWSアカウントIDは？", "")
    role_arn = basic.get("診断に使用するRole ARNは？", "")
    region = basic.get("診断対象のリージョンは？（任意）", "")

    total = len(findings)
    pass_count = sum(1 for f in findings if f["cspm_status"] == "PASS")
    fail_count = sum(1 for f in findings if f["cspm_status"] == "FAIL")
    ai_count = len(ai_results)

    total_cost_usd = sum(r["evaluation"].get("cost_usd", 0) for r in ai_results)
    cost = _calc_cost_display(total_cost_usd)

    # 最大リスク
    # HIGH > MEDIUM > LOW > NONE の4段階
    risk_order = {
        "HIGH": 4,
        "MEDIUM": 3,
        "LOW": 2,
        "NONE": 1,
    }

    # 問題がない場合は NONE
    max_risk = "NONE"

    for r in ai_results:
        risk = (r["evaluation"].get("risk") or "NONE").upper()

        if risk_order.get(risk, 0) > risk_order.get(max_risk, 0):
            max_risk = risk

    # ヒアリング回答（MFA）
    mfa_hearing = hearing.get("権限系", {}).get("MFA", {})
    hearing_display = {
        "console_access": mfa_hearing.get("AWS管理画面にログインして操作する利用者はいますか？"),
        "usage": mfa_hearing.get("AWS管理画面を利用する目的は何ですか？"),
        "alternative_login": mfa_hearing.get("SSOなどAWSへログインするための別の仕組みを利用していますか？"),
        "mfa_exception_reason": mfa_hearing.get("MFAを設定していない利用者がいる場合、理由はありますか？"),
    }

    # 診断日時を表示用にフォーマット
    try:
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
        diagnosis_datetime = dt.strftime("%Y/%m/%d %H:%M")
    except Exception:
        diagnosis_datetime = timestamp

    return {
        "system_name": system_name,
        "cloud": cloud,
        "account_id": account_id,
        "role_arn": role_arn,
        "region": region,
        "diagnosis_datetime": diagnosis_datetime,
        "timestamp": timestamp,
        "total": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "ai_count": ai_count,
        "max_risk": max_risk,
        "cost": cost,
        "hearing": hearing_display,
    }


# ============================================================
# 診断実行（バックグラウンドスレッド）
# ============================================================

def run_diagnosis(diagnosis_id: str, hearing_path: str, mfa_code: str | None, model_id: str):
    """
    診断をバックグラウンドスレッドで実行する。
    進捗は _diagnosis_store に書き込む。

    Args:
        diagnosis_id: 診断セッションID
        hearing_path: ヒアリングシートのファイルパス
        mfa_code: フロントエンドから受け取った6桁のMFAコード（任意。MFA未設定の場合は None または空文字）
        model_id: 使用するBedrockモデルID（例: claude-3-haiku / claude-3-5-sonnet）
    """

    try:
        # ステップ初期化
        steps = [
            ("AWS認証", "待機中"),
            ("Role切替", "待機中"),
            ("CSPM診断", "待機中"),
            ("AI評価", "待機中"),
        ]
        with _store_lock:
            _diagnosis_store[diagnosis_id] = {
                "steps": [{"step": s, "status": st, "message": ""} for s, st in steps],
                "status": "running",
                "result": None,
                "error": None,
                "started_at": time.time(),
            }

        # --------------------------------------------------------
        # 1. ヒアリングシート読込・バリデーション
        # --------------------------------------------------------
        hearing = load_hearing_sheet(hearing_path)
        errors = validate_hearing_sheet(hearing)
        if errors:
            with _store_lock:
                _diagnosis_store[diagnosis_id]["status"] = "error"
                _diagnosis_store[diagnosis_id]["error"] = "入力エラー: " + " / ".join(errors)
            return

        role_arn = hearing["基本情報"]["診断に使用するRole ARNは？"]

        # --------------------------------------------------------
        # 2. AWS 認証
        # --------------------------------------------------------
        _set_step(diagnosis_id, "AWS認証", "実行中")
        try:
            session, role_credentials = assume_role(role_arn, mfa_code)
        except Exception as e:
            err_str = str(e)
            # AccessDenied かつ MFAコード未入力の場合は分かりやすいメッセージに変換
            if "AccessDenied" in err_str and not mfa_code:
                user_msg = (
                    "AWS認証エラー: アクセスが拒否されました。\n"
                    "このロールへのアクセスには MFA コードが必要な可能性があります。\n"
                    "MFA コードを入力して再度お試しください。"
                )
            else:
                user_msg = f"AWS認証エラー: {err_str}"
            _set_step(diagnosis_id, "AWS認証", "エラー", user_msg)
            with _store_lock:
                _diagnosis_store[diagnosis_id]["status"] = "error"
                _diagnosis_store[diagnosis_id]["error"] = user_msg
            return
        _set_step(diagnosis_id, "AWS認証", "完了")

        # --------------------------------------------------------
        # 3. Role 切替
        # --------------------------------------------------------
        _set_step(diagnosis_id, "Role切替", "完了")

        # --------------------------------------------------------
        # 4. 出力フォルダ作成
        # --------------------------------------------------------
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = (OUTPUT_BASE / timestamp).resolve()
        output_path.mkdir(parents=True, exist_ok=True)

        # Prowler の docker run -v に渡すホスト側パスを決定する。
        # Docker-outside-of-Docker (DooD) 構成では、FastAPI コンテナ内の
        # パスをそのまま -v に渡しても Docker デーモン（ホスト側）が
        # 解釈できないため、ホスト側の絶対パスが必要。
        #
        # compose.yaml で HOST_OUTPUT_DIR=<ホスト側 output 絶対パス> を渡す。
        # 設定されていない場合（ローカル直接起動時）は output_path をそのまま使う。
        host_output_base = os.getenv("HOST_OUTPUT_DIR")
        if host_output_base:
            prowler_output_path = str(Path(host_output_base) / timestamp)
        else:
            prowler_output_path = str(output_path)

        # --------------------------------------------------------
        # 5. Prowler 実行
        # --------------------------------------------------------
        _set_step(diagnosis_id, "CSPM診断", "実行中")

        env = os.environ.copy()
        env["AWS_ACCESS_KEY_ID"] = role_credentials["AccessKeyId"]
        env["AWS_SECRET_ACCESS_KEY"] = role_credentials["SecretAccessKey"]
        env["AWS_SESSION_TOKEN"] = role_credentials["SessionToken"]

        log_path = output_path / "prowler.log"

        with open(log_path, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [
                    "docker", "run", "--rm",
                    "--user", "0:0",
                    "-e", "AWS_ACCESS_KEY_ID",
                    "-e", "AWS_SECRET_ACCESS_KEY",
                    "-e", "AWS_SESSION_TOKEN",
                    "-v", f"{prowler_output_path}:/home/prowler/output",
                    "prowlercloud/prowler:stable",
                    "aws",
                    "-z",
                    "--check",
                    "iam_root_mfa_enabled",
                    "iam_user_mfa_enabled_console_access",
                ],
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            elapsed = 0
            while process.poll() is None:
                time.sleep(1)
                elapsed += 1
                with _store_lock:
                    store = _diagnosis_store.get(diagnosis_id, {})
                    store["elapsed"] = elapsed

        if process.returncode != 0:
            _set_step(diagnosis_id, "CSPM診断", "エラー", f"Prowler終了コード: {process.returncode}")
            with _store_lock:
                _diagnosis_store[diagnosis_id]["status"] = "error"
                _diagnosis_store[diagnosis_id]["error"] = "Prowler診断でエラーが発生しました。"
            return

        _set_step(diagnosis_id, "CSPM診断", "完了")

        # --------------------------------------------------------
        # 6. Finding 解析
        # --------------------------------------------------------
        findings = _parse_findings(output_path)

        # --------------------------------------------------------
        # 7. AI 評価
        # --------------------------------------------------------
        _set_step(diagnosis_id, "AI評価", "実行中")

        ai_inputs = build_mfa_ai_inputs(output_path, hearing)
        ai_results = []

        # model_id が指定されていればそれを使う。未指定なら環境変数のデフォルトを使う。
        effective_model_id = BEDROCK_INFERENCE_PROFILE_ID
        
        if ai_inputs:
            for ai_input in ai_inputs:
                result = evaluate_mfa(
                    session,
                    effective_model_id,
                    BEDROCK_REGION,
                    ai_input,
                )
                ai_results.append({
                    "target": ai_input["finding"]["target"],
                    "evaluation": result,
                })

        _set_step(diagnosis_id, "AI評価", "完了")

        # --------------------------------------------------------
        # 8. Finding に AI 結果をマージ
        # --------------------------------------------------------
        findings = _merge_ai_results(findings, ai_results)

        # --------------------------------------------------------
        # 9. AI 評価結果を JSON 保存
        # --------------------------------------------------------
        if ai_results:
            ai_result_path = output_path / "mfa_ai_evaluation.json"
            with open(ai_result_path, "w", encoding="utf-8") as f:
                json.dump(ai_results, f, ensure_ascii=False, indent=2)

        # --------------------------------------------------------
        # 10. サマリー生成・結果保存
        # --------------------------------------------------------
        summary = _build_summary(hearing, findings, ai_results, timestamp)

        # 結果全体を output_path/diagnosis_result.json に保存（履歴用）
        result_data = {
            "summary": summary,
            "findings": findings,
        }
        result_path = output_path / "diagnosis_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        with _store_lock:
            _diagnosis_store[diagnosis_id]["status"] = "done"
            _diagnosis_store[diagnosis_id]["result"] = result_data
            _diagnosis_store[diagnosis_id]["output_dir"] = str(output_path)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        with _store_lock:
            store = _diagnosis_store.setdefault(diagnosis_id, {})
            store["status"] = "error"
            store["error"] = str(e)
            store["traceback"] = tb


# ============================================================
# 履歴読み込み
# ============================================================

def load_history() -> list[dict]:
    """
    output/ 以下の全診断結果を読み込み、履歴一覧を返す。
    """
    history = []

    if not OUTPUT_BASE.exists():
        return history

    for dir_path in sorted(OUTPUT_BASE.iterdir(), reverse=True):
        if not dir_path.is_dir():
            continue

        result_file = dir_path / "diagnosis_result.json"
        if not result_file.exists():
            continue

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            summary = data.get("summary", {})
            findings = data.get("findings", [])

            # リスクレベル別件数を集計（AI判定 → レビュー優先）
            # リスクレベル別件数を集計
            # ・PASS は NONE
            # ・FAIL はレビュー済みなら review.severity を優先
            # ・未レビューなら AI の risk を使用
            risk_counts = {
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
                "NONE": 0,
            }

            for f_item in findings:
                cspm_status = f_item.get("cspm_status")

                # PASS は基本 NONE
                if cspm_status == "PASS":
                    risk_counts["NONE"] += 1
                    continue

                # FAIL はレビュー結果を優先
                if cspm_status == "FAIL":
                    review = f_item.get("review") or {}
                    ai_result = f_item.get("ai_result") or {}

                    risk = (
                        review.get("severity")
                        or ai_result.get("risk")
                        or "NONE"
                    ).upper()

                    if risk not in risk_counts:
                        risk = "NONE"

                    risk_counts[risk] += 1
            
            # レビュー結果を反映した最大リスクを計算
            risk_order = {
                "HIGH": 4,
                "MEDIUM": 3,
                "LOW": 2,
                "NONE": 1,
            }

            max_risk = "NONE"

            for risk, count in risk_counts.items():
                if count > 0 and risk_order[risk] > risk_order[max_risk]:
                    max_risk = risk

            history.append({
                "timestamp": dir_path.name,
                "system_name": summary.get("system_name", ""),
                "diagnosis_datetime": summary.get("diagnosis_datetime", ""),
                "max_risk": max_risk,
                "total": summary.get("total", 0),
                "pass_count": summary.get("pass_count", 0),
                "fail_count": summary.get("fail_count", 0),
                "risk_counts": risk_counts,
                "cost": summary.get("cost", {}),
            })
        except Exception:
            continue

    return history


def load_result(timestamp: str) -> dict | None:
    """
    指定タイムスタンプの診断結果を返す。
    """
    result_file = OUTPUT_BASE / timestamp / "diagnosis_result.json"
    if not result_file.exists():
        return None

    with open(result_file, "r", encoding="utf-8") as f:
        return json.load(f)
