# backend/ai/ai_input_builder.py

from backend.ai.evaluation_router import (
    get_ai_rule,
    requires_ai_evaluation,
)


# ============================================================
# AI判定タイプ → ヒアリングシートのカテゴリ
# ============================================================

HEARING_SECTION_MAP = {
    "mfa": "MFA",
    "admin_privilege": "管理者権限",
    "unused_iam": "未使用IAM",
    "access_key": "アクセスキー",
    "trust_policy": "Trust Policy",
}


# ============================================================
# AIへ渡すヒアリング情報取得
# ============================================================

def _get_hearing_for_ai(
    evaluation_type: str,
    hearing: dict
) -> dict:
    """
    AI判定タイプに対応するヒアリングカテゴリの回答だけ取得する。

    例:
        mfa
            -> hearing["権限系"]["MFA"]

        admin_privilege
            -> hearing["権限系"]["管理者権限"]

    Permission BoundaryはAI評価対象ではないため、
    このMAPには登録しない。
    """

    section_name = HEARING_SECTION_MAP.get(
        evaluation_type
    )

    if not section_name:
        return {}

    return (
        hearing
        .get("権限系", {})
        .get(section_name, {})
    )


# ============================================================
# AI入力生成
# ============================================================

def build_ai_inputs(
    findings: list[dict],
    hearing: dict
) -> list[dict]:
    """
    全FindingからAI評価対象だけ抽出し、
    共通形式のAI入力を生成する。

    AIへ渡すもの:
    - CSPM Finding
    - 対象名
    - CSPM判定
    - 判定対象カテゴリのヒアリング回答

    AIへ渡さないもの:
    - AI評価対象外のFinding
    - Permission Boundary
    - 他カテゴリの不要なヒアリング回答
    """

    ai_inputs = []

    for finding in findings:

        # AI評価対象外はスキップ
        if not requires_ai_evaluation(finding):
            continue

        check_id = finding.get("check_id", "")
        evaluation_type = get_ai_rule(check_id)

        ai_inputs.append({
            "evaluation_type": evaluation_type,

            "finding": {
                "check_id": check_id,
                "check_title": finding.get("check_title"),
                "category": finding.get("category"),
                "target_type": finding.get("target_type"),
                "target": finding.get("target"),
                "cspm_status": finding.get("cspm_status"),
                "severity": finding.get("severity"),
                "message": finding.get("message"),
            },

            "hearing": _get_hearing_for_ai(
                evaluation_type,
                hearing,
            ),
        })

    return ai_inputs