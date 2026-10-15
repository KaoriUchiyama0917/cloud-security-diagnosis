# backend/ai/evaluation_router.py

"""
CSPM Finding を、どのAI判定ルールに回すか振り分ける。

役割:
- check_id を見てAI判定が必要か決める
- 必要な場合、どの判定タイプか返す

ここでは以下は行わない:
- Bedrock呼び出し
- プロンプト生成
- ヒアリング内容の抽出
- AI結果の保存
"""


# ============================================================
# Prowler check_id → AI判定タイプ
# ============================================================

AI_RULE_MAP = {

    # --------------------------------------------------------
    # MFA
    # --------------------------------------------------------
    "iam_user_mfa_enabled_console_access": "mfa",

    # Root MFAは機械判定だけで扱う想定なので、
    # 現時点ではAI対象に入れない
    # "iam_root_mfa_enabled": "mfa",


    # --------------------------------------------------------
    # 管理者権限
    # --------------------------------------------------------

    # User / Group / Role に AdministratorAccess が
    # 付与されている場合、業務上必要な権限かAIで判断する
    "iam_user_administrator_access_policy": "admin_privilege",
    "iam_group_administrator_access_policy": "admin_privilege",
    "iam_role_administratoraccess_policy": "admin_privilege",

    # Policyそのものが管理者相当の権限を持つ場合
    "iam_aws_attached_policy_no_administrative_privileges": "admin_privilege",
    "iam_customer_attached_policy_no_administrative_privileges": "admin_privilege",
    "iam_inline_policy_no_administrative_privileges": "admin_privilege",

    # 権限昇格可能なPolicy
    "iam_policy_allows_privilege_escalation": "admin_privilege",
    "iam_inline_policy_allows_privilege_escalation": "admin_privilege",


    # --------------------------------------------------------
    # 未使用IAM
    # --------------------------------------------------------

    # 一定期間使われていないIAM情報が
    # 本当に不要なのかAIで判断する
    "iam_user_accesskey_unused": "unused_iam",
    "iam_user_console_access_unused": "unused_iam",


    # --------------------------------------------------------
    # アクセスキー
    # --------------------------------------------------------

    # 複数キーや古いキーに正当な理由があるかAIで判断する
    "iam_user_two_active_access_key": "access_key",
    "iam_rotate_access_key_90_days": "access_key",

    # Root Access Keyは存在自体を機械判定するため
    # AI対象にはしない
    # "iam_no_root_access_key": "access_key",


    # --------------------------------------------------------
    # Trust Policy
    # --------------------------------------------------------

    # Roleを利用できる相手が業務上適切かAIで判断する
    "iam_role_cross_service_confused_deputy_prevention": "trust_policy",
    "iam_role_service_trust_restricts_source_to_account": "trust_policy",
    "iam_no_custom_policy_permissive_role_assumption": "trust_policy",
}


# ============================================================
# AI判定タイプ取得
# ============================================================

def get_ai_rule(check_id: str) -> str | None:
    """
    check_id に対応するAI判定タイプを返す。

    AI対象外の場合は None を返す。

    例:
        iam_user_mfa_enabled_console_access
            -> "mfa"

        permission_boundary_user
            -> None
    """

    return AI_RULE_MAP.get(check_id)


# ============================================================
# AI評価対象か確認
# ============================================================

def requires_ai_evaluation(finding: dict) -> bool:
    """
    FindingをAI評価に回す必要があるか判定する。

    現時点では:
    - CSPM判定がFAIL
    - AI_RULE_MAPに登録されている

    この2条件を満たす場合のみAI対象とする。
    """

    # PASSはAI評価しない
    if finding.get("cspm_status") != "FAIL":
        return False

    check_id = finding.get("check_id", "")

    # Routerに登録されていないcheckはAI対象外
    return get_ai_rule(check_id) is not None