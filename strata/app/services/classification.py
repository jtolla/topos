"""Document type classification service.

Classifies documents as CONTRACT, POLICY, RFC, or OTHER based on content analysis.
"""

import logging
import re

from app.config import settings
from app.models import DocType

logger = logging.getLogger(__name__)


# Heuristic patterns for classification
CONTRACT_PATTERNS = [
    r"\b(agreement|contract|terms and conditions|party|parties)\b",
    r"\b(whereas|hereby|herein|hereinafter|witnesseth)\b",
    r"\b(effective date|termination|governing law|jurisdiction)\b",
    r"\b(indemnif|warrant|liabilit|breach)\b",
    r"\b(confidential|non-disclosure|nda)\b",
]

POLICY_PATTERNS = [
    r"\b(policy|procedure|guideline|standard)\b",
    r"\b(compliance|regulation|requirement)\b",
    r"\b(must|shall|required|prohibited)\b",
    r"\b(employee|personnel|staff|organization)\b",
    r"\b(acceptable use|code of conduct|privacy)\b",
]

RFC_PATTERNS = [
    r"\b(rfc|request for comments|design doc|technical spec)\b",
    r"\b(architecture|implementation|proposal|specification)\b",
    r"\b(api|endpoint|interface|protocol)\b",
    r"\b(component|service|module|system)\b",
    r"\b(tradeoff|alternative|decision|rationale)\b",
]


def _count_pattern_matches(text: str, patterns: list[str]) -> int:
    """Count how many patterns match in the text."""
    text_lower = text.lower()
    count = 0
    for pattern in patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        count += len(matches)
    return count


def classify_document_heuristic(text: str, title: str = "") -> DocType:
    """
    Classify document type using heuristic pattern matching.

    This is a fast, local classification method that doesn't require LLM calls.
    """
    full_text = f"{title}\n{text[:5000]}".lower()  # Use title + first 5000 chars

    contract_score = _count_pattern_matches(full_text, CONTRACT_PATTERNS)
    policy_score = _count_pattern_matches(full_text, POLICY_PATTERNS)
    rfc_score = _count_pattern_matches(full_text, RFC_PATTERNS)

    # Normalize scores (contracts tend to have more legal language)
    contract_score *= 1.0
    policy_score *= 1.2
    rfc_score *= 1.5

    max_score = max(contract_score, policy_score, rfc_score)

    if max_score < 3:  # Not enough signal
        return DocType.OTHER

    if contract_score == max_score:
        return DocType.CONTRACT
    if policy_score == max_score:
        return DocType.POLICY
    if rfc_score == max_score:
        return DocType.RFC

    return DocType.OTHER


async def classify_document_llm(text: str, title: str = "") -> DocType:
    """
    Classify document type using LLM.

    More accurate but requires API call.
    """
    if not settings.openai_api_key:
        logger.warning("No OpenAI API key configured, falling back to heuristic classification")
        return classify_document_heuristic(text, title)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Use a sample of the document
        sample = text[:3000]

        prompt = f"""Classify the following document into exactly one of these categories:
- CONTRACT: Legal agreements, terms of service, NDAs, SOWs, MSAs
- POLICY: Company policies, procedures, guidelines, compliance documents
- RFC: Technical specifications, design documents, architecture proposals, engineering RFCs
- OTHER: Anything else

Document title: {title}

Document content (first 3000 chars):
{sample}

Respond with ONLY the category name (CONTRACT, POLICY, RFC, or OTHER), nothing else."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )

        result = response.choices[0].message.content.strip().upper()

        if result in ["CONTRACT", "POLICY", "RFC", "OTHER"]:
            return DocType(result)
        logger.warning(f"Unexpected classification result: {result}")
        return DocType.OTHER

    except Exception as e:
        logger.exception(f"LLM classification failed: {e}")
        return classify_document_heuristic(text, title)


async def classify_document(text: str, title: str = "", use_llm: bool = True) -> DocType:
    """
    Classify a document's type.

    Args:
        text: Document text content
        title: Document title
        use_llm: Whether to use LLM classification (falls back to heuristic if unavailable)

    Returns:
        DocType enum value
    """
    if use_llm and settings.openai_api_key:
        return await classify_document_llm(text, title)
    return classify_document_heuristic(text, title)
