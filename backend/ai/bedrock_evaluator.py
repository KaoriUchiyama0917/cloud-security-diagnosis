import json


# ============================================================
# Bedrock料金設定
# ============================================================

# Haiku 4.5 日本向けクロスリージョン推論
# 100万トークンあたりの料金（USD）
INPUT_PRICE_PER_MILLION = 1.10
OUTPUT_PRICE_PER_MILLION = 5.50


def evaluate_finding(
    session,
    inference_profile_id,
    region,
    ai_input,
    system_prompt
):
    """
    Amazon BedrockへAI評価を依頼する共通処理。

    このファイルでは、
    MFA・管理者権限・Trust Policyなどの
    診断項目ごとの判定ルールは持たない。

    外部から受け取った以下の情報をBedrockへ送信する。
    - system_prompt : AIへの判定指示
    - ai_input      : Findingやヒアリング情報

    処理内容:
    1. Bedrock Runtimeクライアントを作成
    2. AIへデータを送信
    3. AIの回答をJSONへ変換
    4. 利用トークン・料金を計算
    5. 評価結果を返す
    """

    # ========================================================
    # Bedrock Runtimeクライアントを作成
    # ========================================================

    client = session.client(
        "bedrock-runtime",
        region_name=region
    )

    # ========================================================
    # AIへ渡すデータをJSON化
    # ========================================================

    user_prompt = json.dumps(
        ai_input,
        ensure_ascii=False,
        indent=2
    )

    # ========================================================
    # Bedrockを呼び出す
    # ========================================================

    response = client.converse(
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

            # 短い評価JSONを想定
            "maxTokens": 800
        }
    )

    # ========================================================
    # AIの回答を取得
    # ========================================================

    text = response["output"]["message"]["content"][0]["text"]
    text = text.strip()

    # ```json ... ``` の形式で返ってきた場合にも対応
    if text.startswith("```"):
        text = (
            text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

    # ========================================================
    # AI回答をJSONとして解析
    # ========================================================

    try:
        result = json.loads(text)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"AIの回答をJSONとして解析できませんでした: {text}"
        ) from e

    # ========================================================
    # AI利用トークンを取得
    # ========================================================

    usage = response.get("usage", {})

    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)

    # ========================================================
    # AI利用料金を計算
    # ========================================================

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

    # ========================================================
    # 利用情報を結果へ追加
    # ========================================================

    result["usage"] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }

    result["cost_usd"] = total_cost

    return result