# IAM権限を変更できるか確認する対象操作
IAM_MANAGEMENT_ACTIONS = [
    "iam:CreateUser",
    "iam:CreateRole",
    "iam:CreatePolicy",
    "iam:AttachUserPolicy",
    "iam:AttachRolePolicy",
    "iam:PutUserPolicy",
    "iam:PutRolePolicy",
    "iam:CreatePolicyVersion",
    "iam:SetDefaultPolicyVersion",
]


def _can_manage_iam(iam, principal_arn):
    """
    User / Role がIAM権限を変更できるか確認する。
    """

    response = iam.simulate_principal_policy(
        PolicySourceArn=principal_arn,
        ActionNames=IAM_MANAGEMENT_ACTIONS,
    )

    # 1つでも許可されていれば True
    return any(
        result.get("EvalDecision") == "allowed"
        for result in response.get("EvaluationResults", [])
    )

def collect_permission_boundaries(session):
    """
    IAM User / Role の Permission Boundary 設定状況を取得する。
    """

    iam = session.client("iam")

    result = {
        "users": [],
        "roles": [],
    }

    # IAM Users
    user_paginator = iam.get_paginator("list_users")

    for page in user_paginator.paginate():
        for user in page["Users"]:

            detail = iam.get_user(
                UserName=user["UserName"]
            )["User"]

            boundary = detail.get("PermissionsBoundary")
            # このUserがIAM権限を変更できるか
            can_manage_iam = _can_manage_iam(
                iam,
                user["Arn"]
            )

            result["users"].append({
                "name": user["UserName"],
                "has_boundary": boundary is not None,
                "boundary_policy_arn": (
                    boundary.get("PermissionsBoundaryArn")
                    if boundary
                    else None
                ),
                "can_manage_iam": can_manage_iam,
            })

    # IAM Roles
    role_paginator = iam.get_paginator("list_roles")

    for page in role_paginator.paginate():
        for role in page["Roles"]:

            detail = iam.get_role(
                RoleName=role["RoleName"]
            )["Role"]

            boundary = detail.get("PermissionsBoundary")
            # このRoleがIAM権限を変更できるか
            can_manage_iam = _can_manage_iam(
                iam,
                role["Arn"]
            )

            result["roles"].append({
                "name": role["RoleName"],
                "has_boundary": boundary is not None,
                "boundary_policy_arn": (
                    boundary.get("PermissionsBoundaryArn")
                    if boundary
                    else None
                ),
                "can_manage_iam": can_manage_iam,
            })

    return result