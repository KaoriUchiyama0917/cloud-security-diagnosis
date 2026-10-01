import json
from pathlib import Path


def _get_target_name(finding):
    """
    Prowler FindingからAIへ渡してよい対象名だけ取得する。
    ARN全体などはAIへ渡さない。
    """

    resources = finding.get("resources", [])

    if not resources:
        return "unknown"

    resource = resources[0]

    # nameがあれば名前だけ使う
    name = resource.get("name")

    if name:
        return name

    # uidしかない場合はARN等の末尾だけ使う
    uid = resource.get("uid", "")

    if "/" in uid:
        return uid.rsplit("/", 1)[-1]

    if ":" in uid:
        return uid.rsplit(":", 1)[-1]

    return "unknown"


def build_mfa_ai_inputs(output_path, hearing):
    """
    ProwlerのMFA FindingからFAILだけを取得し、
    AIへ渡してよい情報だけを抽出する。

    AIへ渡すもの:
    - 対象種別
    - 対象名
    - MFA判定
    - MFAに関係するヒアリング回答

    AIへ渡さないもの:
    - AWSアカウントID
    - ARN全体
    - Role情報
    - Resource Tags
    - Compliance情報
    - Access Key等の認証情報
    """

    json_files = list(Path(output_path).glob("*.ocsf.json"))

    if not json_files:
        return []

    # Prowler結果を読み込む
    with open(json_files[0], "r", encoding="utf-8") as file:
        findings = json.load(file)

    # ========================================================
    # ヒアリングシートからMFA関連だけ取得
    # ========================================================

    mfa_hearing = hearing.get("権限系", {}).get("MFA", {})

    hearing_for_ai = {
        "console_access": mfa_hearing.get(
            "AWS管理画面にログインして操作する利用者はいますか？"
        ),
        "usage": mfa_hearing.get(
            "AWS管理画面を利用する目的は何ですか？"
        ),
        "alternative_login": mfa_hearing.get(
            "SSOなどAWSへログインするための別の仕組みを利用していますか？"
        ),
        "mfa_exception_reason": mfa_hearing.get(
            "MFAを設定していない利用者がいる場合、理由はありますか？"
        )
    }

    ai_inputs = []

    # ========================================================
    # FindingからMFA FAILだけ抽出
    # ========================================================

    for finding in findings:

        check_id = finding.get(
            "metadata",
            {}
        ).get(
            "event_code"
        )

        status = finding.get("status_code")

        # PASSはAIへ送らない
        if status != "FAIL":
            continue

        # ----------------------------
        # IAMユーザーのMFA
        # ----------------------------
        if check_id == "iam_user_mfa_enabled_console_access":

            ai_inputs.append({
                "finding": {
                    "target_type": "IAM_USER",
                    "target": _get_target_name(finding),
                    "mfa_status": "FAIL"
                },
                "hearing": hearing_for_ai
            })

        # ----------------------------
        # RootユーザーのMFA
        # ----------------------------
        elif check_id == "iam_root_mfa_enabled":

            ai_inputs.append({
                "finding": {
                    "target_type": "ROOT",
                    "target": "root",
                    "mfa_status": "FAIL"
                },
                "hearing": hearing_for_ai
            })

    return ai_inputs
