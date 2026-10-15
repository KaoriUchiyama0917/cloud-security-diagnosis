CHECK_DEFINITIONS = {
    "iam_root_mfa_enabled": {
        "category": "MFA",
        "title": "Root MFA",
        "target_type": "ROOT",
    },
    "iam_user_mfa_enabled_console_access": {
        "category": "MFA",
        "title": "IAM User MFA",
        "target_type": "IAM_USER",
    },

    # ============================================================
    # 管理者権限
    # ============================================================

    # 既存：Policyそのものに完全な管理者権限（*:*）がないか確認
    "iam_aws_attached_policy_no_administrative_privileges": {
        "category": "管理者権限",
        "title": "AWS管理ポリシーの管理者権限",
        "target_type": "IAM_POLICY",
    },
    "iam_customer_attached_policy_no_administrative_privileges": {
        "category": "管理者権限",
        "title": "カスタマー管理ポリシーの管理者権限",
        "target_type": "IAM_POLICY",
    },
    "iam_inline_policy_no_administrative_privileges": {
        "category": "管理者権限",
        "title": "インラインポリシーの管理者権限",
        "target_type": "IAM_POLICY",
    },

    # 追加：IAM UserにAdministratorAccessが直接付与されていないか確認
    "iam_user_administrator_access_policy": {
        "category": "管理者権限",
        "title": "IAM UserのAdministratorAccess",
        "target_type": "IAM_USER",
    },

    # 追加：IAM GroupにAdministratorAccessが付与されていないか確認
    "iam_group_administrator_access_policy": {
        "category": "管理者権限",
        "title": "IAM GroupのAdministratorAccess",
        "target_type": "IAM_GROUP",
    },

    # 追加：IAM RoleにAdministratorAccessが付与されていないか確認
    "iam_role_administratoraccess_policy": {
        "category": "管理者権限",
        "title": "IAM RoleのAdministratorAccess",
        "target_type": "IAM_ROLE",
    },

    # 追加：管理ポリシーの権限を組み合わせて権限昇格できないか確認
    "iam_policy_allows_privilege_escalation": {
        "category": "管理者権限",
        "title": "管理ポリシーによる権限昇格",
        "target_type": "IAM_POLICY",
    },

    # 追加：インラインポリシーで権限昇格できないか確認
    "iam_inline_policy_allows_privilege_escalation": {
        "category": "管理者権限",
        "title": "インラインポリシーによる権限昇格",
        "target_type": "IAM_POLICY",
    },

    # ============================================================
    # 未使用IAM
    # ============================================================

    "iam_user_accesskey_unused": {
        "category": "未使用IAM",
        "title": "未使用アクセスキー",
        "target_type": "IAM_USER",
    },
    "iam_user_console_access_unused": {
        "category": "未使用IAM",
        "title": "未使用コンソールアクセス",
        "target_type": "IAM_USER",
    },

    # ============================================================
    # アクセスキー
    # ============================================================

    "iam_user_two_active_access_key": {
        "category": "アクセスキー",
        "title": "複数の有効アクセスキー",
        "target_type": "IAM_USER",
    },
    "iam_rotate_access_key_90_days": {
        "category": "アクセスキー",
        "title": "アクセスキーの長期未更新",
        "target_type": "IAM_USER",
    },

    # 追加：RootユーザーにAccess Keyが存在しないか確認
    "iam_no_root_access_key": {
        "category": "アクセスキー",
        "title": "Rootアクセスキー",
        "target_type": "ROOT",
    },

    # ============================================================
    # Trust Policy
    # ============================================================

    "iam_role_cross_service_confused_deputy_prevention": {
        "category": "Trust Policy",
        "title": "Cross-Service Confused Deputy対策",
        "target_type": "IAM_ROLE",
    },
    "iam_role_service_trust_restricts_source_to_account": {
        "category": "Trust Policy",
        "title": "Service TrustのSource Account制限",
        "target_type": "IAM_ROLE",
    },
    "iam_no_custom_policy_permissive_role_assumption": {
        "category": "Trust Policy",
        "title": "過度に許可されたRole Assume",
        "target_type": "IAM_POLICY",
    },
}


def get_all_checks():
    return list(CHECK_DEFINITIONS.keys())


def get_check_definition(check_id):
    return CHECK_DEFINITIONS.get(
        check_id,
        {
            "category": "その他",
            "title": check_id,
            "target_type": "UNKNOWN",
        }
    )