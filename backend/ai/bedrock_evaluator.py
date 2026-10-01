import json

# Haiku 4.5 日本向けクロスリージョン推論
# 100万トークンあたりの料金（USD）
INPUT_PRICE_PER_MILLION = 1.10
OUTPUT_PRICE_PER_MILLION = 5.50


def evaluate_mfa(session, inference_profile_id, region, ai_input):
    """
    MFAのFAIL Findingとヒアリング情報を
    Amazon Bedrock / Haikuへ送り、評価結果を返す。

    ai_inputには、AIへ渡してよい情報だけが入っている前提。
    """

    # Bedrock Runtimeクライアントを作成
    client = session.client(
        "bedrock-runtime",
        region_name=region
    )

    # ========================================================
    # AIへの指示
    # ========================================================

    system_prompt = """
あなたはクラウドセキュリティ診断の評価AIです。

AWSのMFA設定について、
CSPMツールが検出した結果とヒアリング情報だけを使って評価してください。

重要:
- 与えられていない情報を推測しないでください。
- null または空欄は「情報不明」として扱ってください。
- MFAがFAILでも、ヒアリング情報から例外と断定できない場合は
NEEDS_REVIEW としてください。
- AWSアカウント、ARN、認証情報など、
入力に存在しない情報を推測しないでください。

判定基準:
- CORRECT:
設定上問題ないと判断できる
- INCORRECT:
MFA設定が不適切で、対応が必要
- NEEDS_REVIEW:
情報不足などにより追加確認が必要

リスク:
- HIGH
- MEDIUM
- LOW

必ず次のJSON形式だけで返してください。

{
"decision": "CORRECT | INCORRECT | NEEDS_REVIEW",
"risk": "HIGH | MEDIUM | LOW",
"reason": "なぜその判定なのか",
"security_risk": "問題がある場合、何がどう危険なのか",
"missing_information": []
}
"""

    # AIに渡してよい最小データだけJSON化
    user_prompt = json.dumps(
        ai_input,
        ensure_ascii=False,
        indent=2
    )

    # ========================================================
    # Bedrock / Haikuを呼び出す
    # ========================================================

    response = client.converse(
        # .envで設定したHaiku推論プロファイルARN
        modelId=inference_profile_id,

        system=[
            {
                "text": system_prompt
            }
        ],

        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": user_prompt
                    }
                ]
            }
        ],

        inferenceConfig={
            # 同じ入力で結果がぶれにくいようにする
            "temperature": 0,

            # 今回は短い評価JSONだけなので十分
            "maxTokens": 800
        }
    )

    # ========================================================
    # Haikuの回答を取得
    # ========================================================

    text = response["output"]["message"]["content"][0]["text"]

    text = text.strip()

    # ```json ... ``` 形式で返ってきた場合にも対応
    if text.startswith("```"):
        text = (
            text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

    # JSONとしてPythonのdictへ変換
    result = json.loads(text)

    # ========================================================
    # AI利用料金を計算
    # ========================================================

    usage = response.get("usage", {})

    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)

    input_cost = (
        input_tokens
        / 1_000_000
        * INPUT_PRICE_PER_MILLION
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * OUTPUT_PRICE_PER_MILLION
    )

    total_cost = input_cost + output_cost

    # main.py側で表示できるように結果へ追加
    result["cost_usd"] = total_cost

    return result
