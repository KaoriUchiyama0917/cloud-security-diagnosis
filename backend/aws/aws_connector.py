import os
import boto3
from pathlib import Path

def assume_role(role_arn: str, mfa_code: str | None = None):
    """
    IAMユーザーのAccess KeyでAWSへ接続し、
    指定されたRoleをAssumeRoleする。
    MFAコードが指定された場合はMFA認証を経由する。

    Args:
        role_arn: AssumeRole対象のARN
        mfa_code: フロントエンドから受け取った6桁のMFAコード（任意）
    """

    # ① Access Keyを使って元のIAMユーザーとして接続
    base_session = boto3.Session()

    iam = base_session.client("iam")
    sts = base_session.client("sts")

    # ② 現在のIAMユーザー名を取得
    user = iam.get_user()
    user_name = user["User"]["UserName"]

    print(f"認証ユーザー: {user_name}")

    if mfa_code:
        # ③ MFAコードがある場合：MFAデバイスを取得してMFA認証を実施
        mfa_devices = iam.list_mfa_devices(
            UserName=user_name
        )["MFADevices"]

        if not mfa_devices:
            raise Exception("MFAデバイスが設定されていません。")

        mfa_serial = mfa_devices[0]["SerialNumber"]

        # ④ MFA認証済みの一時認証情報を取得
        token_response = sts.get_session_token(
            SerialNumber=mfa_serial,
            TokenCode=mfa_code
        )

        token_credentials = token_response["Credentials"]

        # ⑤ MFA認証済みSessionを作成
        assume_session = boto3.Session(
            aws_access_key_id=token_credentials["AccessKeyId"],
            aws_secret_access_key=token_credentials["SecretAccessKey"],
            aws_session_token=token_credentials["SessionToken"]
        )

        print("MFA認証: 完了")

    else:
        # ③' MFAコードなし：元のSessionをそのまま使用
        assume_session = base_session
        print("MFA認証: スキップ（MFA未設定）")

    # ⑥ AssumeRole
    assume_sts = assume_session.client("sts")

    role_response = assume_sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="CloudSecurityDiagnosis"
    )

    role_credentials = role_response["Credentials"]

    # ⑦ 診断用RoleのSessionを作成
    role_session = boto3.Session(
        aws_access_key_id=role_credentials["AccessKeyId"],
        aws_secret_access_key=role_credentials["SecretAccessKey"],
        aws_session_token=role_credentials["SessionToken"]
    )

    return role_session, role_credentials
