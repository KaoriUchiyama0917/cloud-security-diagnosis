"""
app.py

AWSクラウドセキュリティ診断ツール - FastAPI Web アプリケーション

起動方法:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000

エンドポイント一覧:
  GET  /                          → 事前画面
  GET  /result/{timestamp}        → 結果出力画面
  GET  /history                   → 履歴画面

  POST /api/hearing/upload        → ヒアリングシートアップロード・バリデーション
  POST /api/diagnosis/start       → 診断開始（バックグラウンド実行）
  GET  /api/diagnosis/{id}/progress → 診断進捗（SSE）
  GET  /api/result/{timestamp}    → 診断結果 JSON 取得
  GET  /api/history               → 履歴一覧 JSON 取得
"""

import os
import uuid
import json
import asyncio
import threading
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.input.hearing_reader import load_hearing_sheet
from backend.input.hearing_validator import validate_hearing_sheet
from diagnosis_runner import (
    run_diagnosis,
    get_diagnosis_progress,
    load_history,
    load_result,
)

load_dotenv()

app = FastAPI(title="AWSクラウドセキュリティ診断")

# 静的ファイル（CSS / JS）
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Jinja2 テンプレート
templates = Jinja2Templates(directory="frontend/views")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ============================================================
# ページルーティング
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """事前画面"""
    return templates.TemplateResponse(request=request, name="pre_diagnosis.html")


@app.get("/result/{timestamp}", response_class=HTMLResponse)
async def result_page(request: Request, timestamp: str):
    """結果出力画面（現在診断 / 過去診断共通）"""
    return templates.TemplateResponse(
        request=request, name="result.html", context={"timestamp": timestamp}
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """履歴画面"""
    return templates.TemplateResponse(request=request, name="history.html")


@app.get("/report/{timestamp}", response_class=HTMLResponse)
async def report_page(request: Request, timestamp: str):
    """顧客向けレポート画面"""
    return templates.TemplateResponse(
        request=request, name="report.html", context={"timestamp": timestamp}
    )


@app.get("/api/template/download")
async def api_template_download():
    """ヒアリングシートテンプレートをダウンロードする"""
    template_path = Path("templates/template.xlsx")
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="テンプレートファイルが見つかりません。")
    return FileResponse(
        path=str(template_path),
        filename="ヒアリングシート_テンプレート.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ============================================================
# API: ヒアリングシート
# ============================================================

@app.post("/api/hearing/upload")
async def api_hearing_upload(file: UploadFile = File(...)):
    """
    ヒアリングシート（Excel）をアップロードし、
    内容を読み込んでバリデーション結果を返す。

    レスポンス:
    {
        "ok": bool,
        "errors": [...],
        "hearing": {
            "system_name": str,
            "cloud": str,
            "account_id": str,
            "role_arn": str,
            "region": str,
            "diagnosis_items": ["MFA"],
            "mfa_hearing": {
                "console_access": str | null,
                "usage": str | null,
                "alternative_login": str | null,
                "mfa_exception_reason": str | null,
            }
        },
        "upload_id": str   # 診断開始時に使用
    }
    """
    if not file.filename:
        return JSONResponse(
            {"ok": False, "errors": ["ファイルが選択されていません。"]}, status_code=400
        )

    if not file.filename.endswith((".xlsx", ".xlsm")):
        return JSONResponse(
            {"ok": False, "errors": ["Excel ファイル（.xlsx）を選択してください。"]},
            status_code=400,
        )

    # ファイルサイズ上限チェック（10MB）
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        return JSONResponse(
            {"ok": False, "errors": ["ファイルサイズが 10MB を超えています。"]},
            status_code=400,
        )

    # 一時保存
    upload_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{upload_id}.xlsx"
    save_path.write_bytes(contents)

    # 読み込み
    try:
        hearing = load_hearing_sheet(str(save_path))
    except Exception as e:
        return JSONResponse(
            {"ok": False, "errors": [f"ファイルの読み込みに失敗しました: {e}"]},
            status_code=400,
        )

    # バリデーション
    errors = validate_hearing_sheet(hearing)

    basic = hearing.get("基本情報", {})
    mfa_hearing_raw = hearing.get("権限系", {}).get("MFA", {})

    hearing_display = {
        "system_name": basic.get("診断対象システムの名称は？"),
        "cloud": basic.get("利用しているクラウドサービスは？"),
        "account_id": basic.get("診断対象のAWSアカウントIDは？"),
        "role_arn": basic.get("診断に使用するRole ARNは？"),
        "region": basic.get("診断対象のリージョンは？（任意）"),
        "diagnosis_items": list(hearing.get("権限系", {}).keys()),
        "mfa_hearing": {
            "console_access": mfa_hearing_raw.get("AWS管理画面にログインして操作する利用者はいますか？"),
            "usage": mfa_hearing_raw.get("AWS管理画面を利用する目的は何ですか？"),
            "alternative_login": mfa_hearing_raw.get("SSOなどAWSへログインするための別の仕組みを利用していますか？"),
            "mfa_exception_reason": mfa_hearing_raw.get("MFAを設定していない利用者がいる場合、理由はありますか？"),
        },
    }

    return JSONResponse({
        "ok": len(errors) == 0,
        "errors": errors,
        "hearing": hearing_display,
        "upload_id": upload_id,
    })


# ============================================================
# API: 診断
# ============================================================

class DiagnosisStartRequest(BaseModel):
    upload_id: str
    mfa_code: str   # フロントエンドから受け取る6桁のMFAコード
    model_id: str   # 使用するBedrockモデルID（例: claude-3-haiku / claude-3-5-sonnet）


@app.post("/api/diagnosis/start")
async def api_diagnosis_start(body: DiagnosisStartRequest):
    """
    診断を開始する。

    リクエスト JSON:
    {
        "upload_id": str,
        "mfa_code": str,   # 6桁のMFAコード
        "model_id": str    # BedrockモデルID
    }

    レスポンス:
    { "diagnosis_id": str }
    """
    upload_id = body.upload_id
    mfa_code = body.mfa_code.strip()
    model_id = body.model_id.strip()

    # MFAコードは任意。入力がある場合のみ形式チェック
    if mfa_code and (len(mfa_code) != 6 or not mfa_code.isdigit()):
        raise HTTPException(status_code=400, detail="MFAコードは6桁の数字で入力してください。")

    if not model_id:
        raise HTTPException(status_code=400, detail="AIモデルを選択してください。")

    hearing_path = UPLOAD_DIR / f"{upload_id}.xlsx"
    if not hearing_path.exists():
        raise HTTPException(status_code=404, detail="アップロードされたファイルが見つかりません。")

    diagnosis_id = str(uuid.uuid4())

    # バックグラウンドスレッドで診断実行
    thread = threading.Thread(
        target=run_diagnosis,
        args=(diagnosis_id, str(hearing_path), mfa_code, model_id),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"diagnosis_id": diagnosis_id})


@app.get("/api/diagnosis/{diagnosis_id}/progress")
async def api_diagnosis_progress(diagnosis_id: str):
    """
    診断進捗を SSE（Server-Sent Events）で返す。

    イベント形式:
    data: { "steps": [...], "status": str, "elapsed": int, "error": str|null }
    """

    async def generate():
        while True:
            # get_diagnosis_progress はスレッドセーフな同期関数なので
            # asyncio のイベントループをブロックしないよう run_in_executor で呼ぶ
            loop = asyncio.get_event_loop()
            progress = await loop.run_in_executor(
                None, get_diagnosis_progress, diagnosis_id
            )

            if not progress:
                yield f"data: {json.dumps({'status': 'not_found'}, ensure_ascii=False)}\n\n"
                break

            payload = {
                "steps": progress.get("steps", []),
                "status": progress.get("status", "running"),
                "elapsed": progress.get("elapsed", 0),
                "error": progress.get("error"),
            }

            # 診断完了時は result の timestamp を含める
            if progress.get("status") == "done":
                result = progress.get("result", {})
                summary = result.get("summary", {}) if result else {}
                payload["timestamp"] = summary.get("timestamp")

            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if progress.get("status") in ("done", "error"):
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# API: 結果
# ============================================================

@app.get("/api/result/{timestamp}")
async def api_result(timestamp: str):
    """
    指定タイムスタンプの診断結果 JSON を返す。
    """
    result = load_result(timestamp)
    if result is None:
        raise HTTPException(status_code=404, detail="診断結果が見つかりません。")
    return JSONResponse(result)


# ============================================================
# API: 履歴
# ============================================================

@app.get("/api/history")
async def api_history():
    """
    過去の診断結果一覧を返す。
    """
    history = load_history()
    return JSONResponse(history)


# ============================================================
# API: レポートデータ
# ============================================================

@app.get("/api/report/{timestamp}")
async def api_report(timestamp: str):
    """
    顧客向けレポート用データを返す。
    include_in_report=true かつ review 済みの Finding のみ含む。
    AI判定データは含めず、診断員確定データ（review）のみ返す。
    """
    result_path = Path("output") / timestamp / "diagnosis_result.json"

    if not result_path.exists():
        raise HTTPException(
            status_code=404,
            detail="診断結果が見つかりません。"
        )

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data.get("summary", {})
    findings = data.get("findings", [])

    # レポート掲載対象の Finding のみ抽出
    # ・CSPM判定が FAIL
    # ・診断員レビュー済み（approved）
    # ・顧客レポート掲載対象
    report_findings = []

    for idx, f in enumerate(findings):
        if f.get("cspm_status") != "FAIL":
            continue

        review = f.get("review")

        # 未レビューの Finding は顧客レポートには使用しない
        if not review:
            continue

        # 診断員による確定前のデータは使用しない
        if review.get("status") != "approved":
            continue

        # レポート掲載対象外
        if review.get("include_in_report") is False:
            continue

        report_findings.append({
            "idx": idx,
            "check_title": f.get(
                "check_title",
                f.get("check_id", "")
            ),
            "target": f.get("target", ""),
            "cspm_status": f.get("cspm_status", ""),
            "message": f.get("message", ""),
            "review": review,
        })

    return JSONResponse({
        "summary": summary,
        "findings": report_findings,
    })

# ============================================================
# API: 診断員レビュー
# ============================================================

class ReviewSaveRequest(BaseModel):
    result:           str            # INCORRECT / NEEDS_REVIEW / CORRECT
    severity:         str            # HIGH / MEDIUM / LOW / NONE
    reason:           str
    security_risk:    str
    recommendation:   str = ""
    reviewer_note:    str = ""
    include_in_report: bool = True


@app.post("/api/result/{timestamp}/review/{finding_idx}")
async def api_review_save(timestamp: str, finding_idx: int, body: ReviewSaveRequest):
    """
    指定 Finding の診断員レビューを保存する。
    AI 判定データは変更せず、review フィールドのみ更新する。
    """
    result_path = Path("output") / timestamp / "diagnosis_result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="診断結果が見つかりません。")

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    findings = data.get("findings", [])
    if finding_idx < 0 or finding_idx >= len(findings):
        raise HTTPException(status_code=404, detail="Finding が見つかりません。")

    # AI 判定は変更せず review フィールドのみ追加・更新
    findings[finding_idx]["review"] = {
        "status":            "approved",
        "result":            body.result,
        "severity":          body.severity,
        "reason":            body.reason,
        "security_risk":     body.security_risk,
        "recommendation":    body.recommendation,
        "reviewer_note":     body.reviewer_note,
        "include_in_report": body.include_in_report,
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return JSONResponse({"ok": True})


@app.get("/api/result/{timestamp}/review/{finding_idx}")
async def api_review_get(timestamp: str, finding_idx: int):
    """
    指定 Finding の診断員レビューを取得する。
    """
    result_path = Path("output") / timestamp / "diagnosis_result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="診断結果が見つかりません。")

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    findings = data.get("findings", [])
    if finding_idx < 0 or finding_idx >= len(findings):
        raise HTTPException(status_code=404, detail="Finding が見つかりません。")

    review = findings[finding_idx].get("review")
    if review is None:
        return JSONResponse({"status": "unreviewed"})
    return JSONResponse(review)


# ============================================================
# エントリーポイント
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
