from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    ExposureLevel,
    FileEffectiveAccess,
    Principal,
    SensitivityFinding,
    SensitivityLevel,
    SensitivityType,
)


async def compute_exposure(
    session: AsyncSession,
    tenant_id: UUID,
    document_id: UUID,
    file_id: UUID,
) -> tuple[ExposureLevel, int, dict]:
    """
    Compute exposure score and level for a document.

    Returns:
        Tuple of (exposure_level, exposure_score, access_summary)
    """
    # Count principals with read access
    result = await session.execute(
        select(func.count(FileEffectiveAccess.id)).where(
            FileEffectiveAccess.tenant_id == tenant_id,
            FileEffectiveAccess.file_id == file_id,
            FileEffectiveAccess.can_read == True,  # noqa: E712
        )
    )
    principal_count = result.scalar() or 0

    # Compute principal breadth score
    if principal_count <= 10:
        principal_breadth_score = 20
        principal_count_bucket = "0-10"
    elif principal_count <= 100:
        principal_breadth_score = 50
        principal_count_bucket = "11-100"
    else:
        principal_breadth_score = 80
        principal_count_bucket = ">100"

    # Check for broad groups
    broad_group_names = settings.broad_group_names
    result = await session.execute(
        select(Principal.display_name)
        .join(
            FileEffectiveAccess,
            FileEffectiveAccess.principal_id == Principal.id,
        )
        .where(
            FileEffectiveAccess.tenant_id == tenant_id,
            FileEffectiveAccess.file_id == file_id,
            FileEffectiveAccess.can_read == True,  # noqa: E712
            Principal.display_name.in_(broad_group_names),
        )
    )
    found_broad_groups = [row[0] for row in result.fetchall()]

    if found_broad_groups:
        principal_breadth_score += 20

    # Compute sensitivity score from findings
    result = await session.execute(
        select(
            SensitivityFinding.sensitivity_type,
            SensitivityFinding.sensitivity_level,
        ).where(
            SensitivityFinding.tenant_id == tenant_id,
            SensitivityFinding.document_id == document_id,
        )
    )
    findings = result.fetchall()

    sensitivity_score = 20  # Default
    for finding_type, finding_level in findings:
        if finding_type in (SensitivityType.SECRETS, SensitivityType.FINANCIAL_DATA):
            if finding_level == SensitivityLevel.HIGH:
                sensitivity_score = max(sensitivity_score, 80)
        elif finding_type == SensitivityType.PERSONAL_DATA:
            sensitivity_score = max(sensitivity_score, 60)
        elif finding_type == SensitivityType.HEALTH_DATA:
            sensitivity_score = max(sensitivity_score, 70)

    # Final exposure score
    exposure_score = min(100, sensitivity_score + principal_breadth_score)

    # Derive exposure level
    if exposure_score < 40:
        exposure_level = ExposureLevel.LOW
    elif exposure_score < 70:
        exposure_level = ExposureLevel.MEDIUM
    else:
        exposure_level = ExposureLevel.HIGH

    # Build access summary
    access_summary = {
        "broad_groups": found_broad_groups,
        "principal_count_bucket": principal_count_bucket,
    }

    return exposure_level, exposure_score, access_summary
