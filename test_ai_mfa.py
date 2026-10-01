import os
import math
from pathlib import Path

from dotenv import load_dotenv

from backend.input.hearing_reader import load_hearing_sheet
from backend.input.hearing_validator import validate_hearing_sheet
from backend.aws.aws_connector import assume_role

from backend.ai.ai_input_builder import build_mfa_ai_inputs
from backend.ai.bedrock_evaluator import evaluate_mfa


# ============================================================
# .envを読み込む
# ============================================================

load_dotenv()


# ============================================================
# 基本設定
# ============================================================

# ヒアリングシート
HEARING_PATH = "templates/hearing_template_v2.xlsx"

# ダミーFindingを置いているフォルダ
DUMMY_FINDING_PATH = Path("testdata")

# Bedrock設定
BEDROCK_INFERENCE_PROFILE_ID = os.getenv(
    "BEDROCK_INFERENCE_PROFILE_ID"
)

BEDROCK_REGION = os.getenv(
    "BEDROCK_REGION",
    "ap-northeast-1"
)

# ドル円換算
USD_TO_JPY = float(
    os.getenv("USD_TO_JPY", "155")
)


def main():

    # ========================================================
    # 1. ヒアリングシートを読み込む
    # ========================================================

    hearing = load_hearing_sheet(HEARING_PATH)

    print("=== ヒアリングシート読込 ===")

    # 入力チェック
    errors = validate_hearing_sheet(hearing)

    if errors:
        print("入力エラーがあります。")

        for error in errors:
            print(f"- {error}")

        return

    print("入力チェックOK")


    # ========================================================
    # 2. AWS Roleへ切り替える
    # ========================================================

    role_arn = hearing["基本情報"][
        "診断に使用するRole ARNは？"
    ]

    print("\n=== AWS Role切り替え ===")

    session, role_credentials = assume_role(role_arn)

    print("Role切り替えOK")


    # ========================================================
    # 3. ダミーFindingからAI用データを作る
    # ========================================================

    print("\n=== AI入力データ作成 ===")

    ai_inputs = build_mfa_ai_inputs(
        DUMMY_FINDING_PATH,
        hearing
    )

    if not ai_inputs:
        print("AI評価対象のMFA FAILが見つかりませんでした。")
        return

    print(f"AI評価対象: {len(ai_inputs)}件")


    # ========================================================
    # 4. HaikuでMFA設定を評価
    # ========================================================

    print("\n=== AI評価 ===")
    print(
    "推論プロファイル設定:",
    "OK" if BEDROCK_INFERENCE_PROFILE_ID else "未設定"
    )

    print(
        "Bedrock Region:",
        BEDROCK_REGION
    )

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


        # ====================================================
        # 追加確認事項
        # ====================================================

        missing_information = result.get(
            "missing_information",
            []
        )

        if missing_information:

            print("追加確認:")

            for item in missing_information:
                print(f"- {item}")


        # ====================================================
        # AI料金表示
        # ====================================================

        cost_usd = result["cost_usd"]

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


if __name__ == "__main__":
    main()