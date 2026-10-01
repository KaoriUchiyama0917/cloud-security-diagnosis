import os
import json
import subprocess
import time
import math
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from backend.input.hearing_reader import load_hearing_sheet
from backend.input.hearing_validator import validate_hearing_sheet
from backend.aws.aws_connector import assume_role
from backend.ai.ai_input_builder import build_mfa_ai_inputs
from backend.ai.bedrock_evaluator import evaluate_mfa

load_dotenv()
# ============================================================
# 基本設定
# ============================================================

# 診断に使用するヒアリングシート
# CSV_PATH = "templates/hearing_template.csv"
HEARING_PATH = "templates/hearing_template_v2.xlsx"

# Prowlerの診断結果を保存する親フォルダ
OUTPUT_BASE = Path("output")

# Bedrock設定
BEDROCK_INFERENCE_PROFILE_ID = os.getenv(
    "BEDROCK_INFERENCE_PROFILE_ID"
)

BEDROCK_REGION = os.getenv(
    "BEDROCK_REGION",
    "ap-northeast-1"
)


# ============================================================
# ProwlerのMFA結果だけを集計してコンソール表示する
# ============================================================

def print_mfa_summary(output_path):

    # Prowlerが出力したOCSF JSONを探す
    json_files = list(output_path.glob("*.ocsf.json"))

    if not json_files:
        print("\n=== MFA診断結果 ===")
        print("診断結果JSONが見つかりませんでした。")
        return

    json_path = json_files[0]

    # JSONを読み込む
    with open(json_path, "r", encoding="utf-8") as file:
        findings = json.load(file)

    # Root MFA
    root_status = "結果なし"

    # IAMユーザー MFA
    iam_pass = 0
    iam_fail = 0

    # Findingを1件ずつ確認
    for finding in findings:

        # ProwlerのチェックID
        check_id = finding.get("metadata", {}).get("event_code")

        # PASS / FAIL
        status = finding.get("status_code")

        # ----------------------------
        # RootユーザーのMFA
        # ----------------------------
        if check_id == "iam_root_mfa_enabled":
            root_status = status

        # ----------------------------
        # IAMユーザーのMFA
        # ----------------------------
        elif check_id == "iam_user_mfa_enabled_console_access":

            if status == "PASS":
                iam_pass += 1

            elif status == "FAIL":
                iam_fail += 1

    # 必要な結果だけコンソール表示
    print("\n=== MFA診断結果 ===")
    print(f"Root MFA     : {root_status}")
    print(f"IAM User MFA : PASS {iam_pass}件 / FAIL {iam_fail}件")


def main():

    # ========================================================
    # 1. ヒアリングシートを読み込む
    # ========================================================

    # hearing = load_hearing_sheet(CSV_PATH)
    hearing = load_hearing_sheet(HEARING_PATH)

    print("=== ヒアリングシート読込結果 ===")

    # for question, answer in hearing.items():
    #     print(f"{question}: {answer}")

    print("\n[基本情報]")
    for question, answer in hearing["基本情報"].items():
        print(f"{question}: {answer or ''}")

    print("\n[権限系 - MFA]")
    for question, answer in hearing["権限系"].get("MFA", {}).items():
        print(f"{question}: {answer or ''}")


    # ========================================================
    # 2. ヒアリングシートの入力内容をチェックする
    # ========================================================

    print("\n=== 入力チェック ===")

    errors = validate_hearing_sheet(hearing)

    if errors:
        print("入力エラーがあります。")

        for error in errors:
            print(f"- {error}")

        # 入力エラーがある場合は診断を開始しない
        return

    print("入力チェックOK")


    # ========================================================
    # 3. AWSの診断用Roleへ切り替える
    # ========================================================

    # ヒアリングシートから診断用Role ARNを取得
    # role_arn = hearing["診断に使用するRole ARNは？"]
    role_arn = hearing["基本情報"]["診断に使用するRole ARNは？"]

    print("\n=== AWS Role切り替え ===")

    # MFA認証後、診断用RoleへAssumeRole
    # role_credentialsにはProwlerへ渡す一時認証情報が入る
    session, role_credentials = assume_role(role_arn)

    print("Role切り替えOK")


    # ========================================================
    # 4. 今回の診断結果を保存するフォルダを作成する
    # ========================================================

    # 例：20260924_180331
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # output/20260924_180331 のような保存先を作成
    output_path = (OUTPUT_BASE / timestamp).resolve()

    output_path.mkdir(parents=True, exist_ok=True)


    # ========================================================
    # 5. Prowlerへ渡すAWS一時認証情報を準備する
    # ========================================================

    # 現在の環境変数をコピー
    env = os.environ.copy()

    # AssumeRoleで取得した一時認証情報を設定
    # 認証情報そのものはコンソールには表示しない
    env["AWS_ACCESS_KEY_ID"] = role_credentials["AccessKeyId"]
    env["AWS_SECRET_ACCESS_KEY"] = role_credentials["SecretAccessKey"]
    env["AWS_SESSION_TOKEN"] = role_credentials["SessionToken"]


    # ========================================================
    # 6. Prowlerを一時Dockerコンテナで実行する
    # ========================================================

    print("\n=== Prowler診断 ===")
    print("診断を開始しました...")

    # Prowlerの詳細ログ保存先
    log_path = output_path / "prowler.log"

    # 大量のProwlerログはコンソールではなくファイルへ保存
    with open(log_path, "w", encoding="utf-8") as log_file:

        process = subprocess.Popen(
            [
                "docker",
                "run",

                # Prowler終了後に一時コンテナを削除
                "--rm",

                # AWS一時認証情報をコンテナへ渡す
                "-e", "AWS_ACCESS_KEY_ID",
                "-e", "AWS_SECRET_ACCESS_KEY",
                "-e", "AWS_SESSION_TOKEN",

                # Prowlerの診断結果をPC側へ保存
                "-v", f"{output_path}:/home/prowler/output",

                # 使用するProwlerイメージ
                "prowlercloud/prowler:stable",

                # AWSを診断
                "aws",

                # 今回はMFA関連のみ診断
                "--check",

                # RootユーザーのMFA
                "iam_root_mfa_enabled",

                # コンソールアクセス可能なIAMユーザーのMFA
                "iam_user_mfa_enabled_console_access"
            ],

            # AWS一時認証情報をDockerへ渡す
            env=env,

            # Prowlerの標準出力・エラーをログファイルへ保存
            stdout=log_file,
            stderr=subprocess.STDOUT,

            text=True,
            encoding="utf-8",
            errors="replace"
        )


        # ====================================================
        # 7. 診断中であることを30秒ごとに表示する
        # ====================================================

        elapsed_seconds = 0

        while process.poll() is None:

            # 1秒ごとに終了確認
            time.sleep(1)

            elapsed_seconds += 1

            # 30秒ごとにコンソール表示
            if elapsed_seconds % 30 == 0:
                minutes = elapsed_seconds // 60
                seconds = elapsed_seconds % 60

                print(f"診断中... {minutes}分{seconds:02d}秒経過")


    # ========================================================
    # 8. Prowlerの実行結果を確認する
    # ========================================================
    
    if process.returncode == 0:

        # Prowler結果からMFAだけを集計して表示
        print_mfa_summary(output_path)

        print("\nProwler診断完了")
        print(f"結果保存先: {output_path}")

        # ====================================================
        # 9. MFA FAIL FindingだけAI評価
        # ====================================================

        ai_inputs = build_mfa_ai_inputs(
            output_path,
            hearing
        )

        # FAILがなければAIは呼ばない
        if not ai_inputs:
            print("\n=== AI評価 ===")
            print("AI評価が必要なMFA FAILはありません。")

        else:
            print("\n=== AI評価 ===")

            ai_results = []

            for ai_input in ai_inputs:

                result = evaluate_mfa(
                    session,
                    BEDROCK_INFERENCE_PROFILE_ID,
                    BEDROCK_REGION,
                    ai_input
                )

                target = ai_input["finding"]["target"]

                print(f"\n対象: {target}")
                print(f"判定: {result['decision']}")
                print(f"リスク: {result['risk']}")
                print(f"理由: {result['reason']}")
                print(f"危険性: {result['security_risk']}")

                # 追加確認事項
                missing_information = result.get(
                    "missing_information",
                    []
                )

                if missing_information:
                    print("追加確認:")

                    for item in missing_information:
                        print(f"- {item}")

                # ====================================================
                # AI利用料金を表示
                # ====================================================

                cost_usd = result["cost_usd"]

                USD_TO_JPY = float(
                    os.getenv("USD_TO_JPY", "155")
                )

                cost_jpy = cost_usd * USD_TO_JPY

                # 小数第4位より下を切り上げ
                cost_usd_display = (
                    math.ceil(cost_usd * 10000)
                    / 10000
                )

                cost_jpy_display = (
                    math.ceil(cost_jpy * 10000)
                    / 10000
                )

                print(
                    f"Cost: ${cost_usd_display:.4f} "
                    f"(約 ¥{cost_jpy_display:.4f})"
                )

                # 保存用
                ai_results.append({
                    "target": target,
                    "evaluation": result
                })

            # ====================================================
            # AI評価結果をJSON保存
            # ====================================================

            ai_result_path = (
                output_path
                / "mfa_ai_evaluation.json"
            )

            with open(
                ai_result_path,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    ai_results,
                    file,
                    ensure_ascii=False,
                    indent=2
                )


# ============================================================
# main.pyを直接実行した場合にmain()を開始する
# ============================================================

if __name__ == "__main__":
    main()