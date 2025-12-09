"""Policy engine for enforcing access and view controls.

Policies control what agents can see and how content is presented.
"""

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentPolicy, Chunk, DocType, Document, Policy
from app.services.sensitivity import detect_sensitivity

logger = logging.getLogger(__name__)


@dataclass
class PolicyConfig:
    """Parsed policy configuration."""

    # Visibility rules
    include_doc_types: list[str] = field(default_factory=list)  # Empty = all allowed
    exclude_doc_types: list[str] = field(default_factory=list)
    include_paths: list[str] = field(default_factory=list)  # Path prefixes
    exclude_paths: list[str] = field(default_factory=list)

    # Redaction rules
    mask_pii: bool = False
    mask_secrets: bool = False
    use_summaries: bool = False  # Use summary_text instead of raw text

    # Content rules
    max_sensitivity_level: str | None = None  # LOW, MEDIUM, HIGH - filter above this

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "PolicyConfig":
        """Parse policy config from dict (as stored in DB)."""
        visibility = config.get("visibility", {})
        redaction = config.get("redaction", {})
        content = config.get("content", {})

        return cls(
            include_doc_types=visibility.get("include_doc_types", []),
            exclude_doc_types=visibility.get("exclude_doc_types", []),
            include_paths=visibility.get("include_paths", []),
            exclude_paths=visibility.get("exclude_paths", []),
            mask_pii=redaction.get("mask_pii", False),
            mask_secrets=redaction.get("mask_secrets", False),
            use_summaries=redaction.get("use_summaries", False),
            max_sensitivity_level=content.get("max_sensitivity_level"),
        )


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""

    allowed: bool = True
    view_type: str = "raw"  # raw, redacted, summary
    filter_reason: str | None = None
    applied_policies: list[str] = field(default_factory=list)


async def get_agent_policies(
    session: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
) -> list[PolicyConfig]:
    """Get all active policies for an agent, sorted by priority."""
    result = await session.execute(
        select(Policy)
        .join(AgentPolicy, AgentPolicy.policy_id == Policy.id)
        .where(
            AgentPolicy.agent_id == agent_id,
            Policy.tenant_id == tenant_id,
            Policy.is_active == True,  # noqa: E712
        )
        .order_by(Policy.priority.desc())
    )
    policies = result.scalars().all()

    return [PolicyConfig.from_dict(p.config) for p in policies]


def evaluate_visibility(
    policy: PolicyConfig,
    doc_type: DocType | None,
    file_path: str,
) -> tuple[bool, str | None]:
    """
    Evaluate if a document is visible under a policy.

    Returns (allowed, reason) tuple.
    """
    # Check doc type exclusions
    if policy.exclude_doc_types:
        if doc_type and doc_type.value in policy.exclude_doc_types:
            return False, f"doc_type {doc_type.value} excluded by policy"

    # Check doc type inclusions (if specified, only these are allowed)
    if policy.include_doc_types:
        if not doc_type or doc_type.value not in policy.include_doc_types:
            return False, "doc_type not in allowed list"

    # Check path exclusions
    for excluded_path in policy.exclude_paths:
        if file_path.startswith(excluded_path):
            return False, f"path excluded: {excluded_path}"

    # Check path inclusions (if specified, only these are allowed)
    if policy.include_paths:
        allowed = False
        for included_path in policy.include_paths:
            if file_path.startswith(included_path):
                allowed = True
                break
        if not allowed:
            return False, "path not in allowed list"

    return True, None


def determine_view_type(policies: list[PolicyConfig]) -> str:
    """
    Determine which view type to use based on policies.

    More restrictive policies take precedence.
    """
    # Check if any policy requires summaries
    for policy in policies:
        if policy.use_summaries:
            return "summary"

    # Check if any policy requires redaction
    for policy in policies:
        if policy.mask_pii or policy.mask_secrets:
            return "redacted"

    return "raw"


async def evaluate_chunk_access(
    session: AsyncSession,
    chunk: Chunk,  # noqa: ARG001
    document: Document,
    file_path: str,
    agent_id: UUID | None,
    tenant_id: UUID,
) -> PolicyDecision:
    """
    Evaluate policy for a specific chunk.

    Returns a PolicyDecision indicating if access is allowed and what view to use.
    """
    decision = PolicyDecision()

    # If no agent, use default (raw) access
    if not agent_id:
        return decision

    # Get agent's policies
    policies = await get_agent_policies(session, agent_id, tenant_id)

    if not policies:
        # No policies = default access
        return decision

    decision.applied_policies = [f"policy_{i}" for i in range(len(policies))]

    # Evaluate visibility against all policies (must pass all)
    for policy in policies:
        allowed, reason = evaluate_visibility(policy, document.doc_type, file_path)
        if not allowed:
            decision.allowed = False
            decision.filter_reason = reason
            return decision

    # Determine view type
    decision.view_type = determine_view_type(policies)

    return decision


def get_chunk_text_for_view(chunk: Chunk, view_type: str) -> str:
    """Get the appropriate text representation for a chunk based on view type."""
    if view_type == "summary" and chunk.summary_text:
        return chunk.summary_text
    if view_type == "redacted" and chunk.redacted_text:
        return chunk.redacted_text
    return chunk.text


def generate_redacted_text(text: str, mask_pii: bool = True, mask_secrets: bool = True) -> str:
    """
    Generate redacted version of text by masking sensitive content.

    Uses the sensitivity detection service to find and mask PII/secrets.
    """
    matches = detect_sensitivity(text)

    if not matches:
        return text

    # Sort matches by position (reverse order for replacement)
    sorted_matches = sorted(matches, key=lambda m: m.match_start, reverse=True)

    redacted = text
    for match in sorted_matches:
        # Determine if we should redact this match
        should_redact = False
        if mask_pii and match.sensitivity_type.value in [
            "PERSONAL_DATA",
            "HEALTH_DATA",
            "FINANCIAL_DATA",
        ]:
            should_redact = True
        if mask_secrets and match.sensitivity_type.value == "SECRETS":
            should_redact = True

        if should_redact:
            # Replace the sensitive content with redaction marker
            replacement = f"[{match.sensitivity_type.value}]"
            redacted = redacted[: match.match_start] + replacement + redacted[match.match_end :]

    return redacted


# Example policy configuration (YAML format shown in comments):
#
# policies:
#   - id: "external_assistant"
#     applies_to_agents: ["external_assistant"]
#     visibility:
#       include_doc_types: ["POLICY", "RFC"]
#       exclude_doc_types: ["CONTRACT"]
#       include_paths: ["/public/", "/docs/"]
#       exclude_paths: ["/internal/", "/hr/"]
#     redaction:
#       mask_pii: true
#       mask_secrets: true
#       use_summaries: false
#     content:
#       max_sensitivity_level: "MEDIUM"
#
#   - id: "legal_assistant"
#     applies_to_agents: ["legal_assistant"]
#     visibility:
#       include_doc_types: ["CONTRACT", "POLICY"]
#     redaction:
#       mask_pii: false
#       mask_secrets: true
