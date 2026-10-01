import re


def validate_hearing_sheet(hearing):
    errors = []

    # ========================================================
    # 基本情報シートを取得
    # ========================================================

    basic = hearing.get("基本情報", {})

    system_name = basic.get("診断対象システムの名称は？")
    cloud = basic.get("利用しているクラウドサービスは？")
    account_id = basic.get("診断対象のAWSアカウントIDは？")
    role_arn = basic.get("診断に使用するRole ARNは？")


    # ========================================================
    # 必須チェック
    # ========================================================

    if not system_name:
        errors.append("診断対象システムの名称を入力してください。")

    if not cloud:
        errors.append("利用しているクラウドサービスを入力してください。")

    if not account_id:
        errors.append("AWSアカウントIDを入力してください。")

    if not role_arn:
        errors.append("診断に使用するRole ARNを入力してください。")


    # ========================================================
    # クラウドサービス
    # ========================================================

    if cloud and cloud != "AWS":
        errors.append("現在対応しているクラウドサービスはAWSのみです。")


    # ========================================================
    # AWSアカウントID
    # ========================================================

    if account_id and not re.fullmatch(r"\d{12}", str(account_id)):
        errors.append("AWSアカウントIDは12桁の数字で入力してください。")


    # ========================================================
    # Role ARN
    # ========================================================

    if role_arn:
        role_pattern = r"^arn:aws:iam::\d{12}:role/.+$"

        if not re.fullmatch(role_pattern, str(role_arn)):
            errors.append("診断用Role ARNの形式が正しくありません。")


    # ========================================================
    # 権限系シート
    # ========================================================

    permission = hearing.get("権限系", {})

    # 今回はMFAのみ対応
    if "MFA" not in permission:
        errors.append("権限系シートにMFAの診断項目がありません。")


    return errors
