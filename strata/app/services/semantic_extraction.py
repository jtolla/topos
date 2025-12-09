"""Semantic extraction service.

Extracts structured fields from documents based on their type using LLM.
"""

import json
import logging
from typing import Any

from app.config import settings
from app.models import DocType

logger = logging.getLogger(__name__)


# JSON schemas for structured extraction
CONTRACT_SCHEMA = {
    "parties": "List of party names involved in the contract",
    "effective_date": "Date when the contract becomes effective (YYYY-MM-DD or null)",
    "term_months": "Contract term duration in months (integer or null)",
    "auto_renew": "Whether the contract auto-renews (boolean or null)",
    "governing_law": "Jurisdiction/governing law (string or null)",
    "payment_terms": "Summary of payment terms (string or null)",
    "termination_clauses": "Summary of termination conditions (string or null)",
    "key_obligations": "List of key obligations for each party",
    "sla_details": "SLA commitments if present (string or null)",
}

POLICY_SCHEMA = {
    "policy_name": "Name of the policy",
    "policy_type": "Type of policy (e.g., HR, IT, Security, Privacy)",
    "effective_date": "Date when policy becomes effective (YYYY-MM-DD or null)",
    "review_date": "Next review date (YYYY-MM-DD or null)",
    "owner": "Policy owner or department",
    "scope": "Who/what the policy applies to",
    "key_requirements": "List of key requirements or rules",
    "violations": "Consequences of policy violations (string or null)",
    "related_policies": "List of related policy names",
}

RFC_SCHEMA = {
    "title": "RFC title",
    "authors": "List of author names",
    "status": "Document status (draft, proposed, accepted, implemented, deprecated)",
    "created_date": "Creation date (YYYY-MM-DD or null)",
    "affected_systems": "List of systems/services affected",
    "problem_statement": "Summary of the problem being solved",
    "proposed_solution": "Summary of the proposed solution",
    "alternatives_considered": "List of alternatives that were considered",
    "decision": "Final decision or recommendation",
    "implementation_notes": "Key implementation considerations",
}


def get_schema_for_doc_type(doc_type: DocType) -> dict[str, str]:
    """Get the extraction schema for a document type."""
    if doc_type == DocType.CONTRACT:
        return CONTRACT_SCHEMA
    if doc_type == DocType.POLICY:
        return POLICY_SCHEMA
    if doc_type == DocType.RFC:
        return RFC_SCHEMA
    return {}


async def extract_structured_fields(
    text: str,
    doc_type: DocType,
    title: str = "",
) -> dict[str, Any]:
    """
    Extract structured fields from a document using LLM.

    Args:
        text: Document text content
        doc_type: Type of document
        title: Document title

    Returns:
        Dictionary of extracted fields
    """
    if doc_type == DocType.OTHER:
        return {}

    if not settings.openai_api_key:
        logger.warning("No OpenAI API key configured, skipping semantic extraction")
        return {}

    schema = get_schema_for_doc_type(doc_type)
    if not schema:
        return {}

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Build the schema description
        schema_desc = "\n".join([f"- {k}: {v}" for k, v in schema.items()])

        # Use first 8000 chars for extraction (balance between coverage and token limits)
        sample = text[:8000]

        prompt = (
            f"Extract structured information from the following "
            f"{doc_type.value.lower()} document.\n\n"
            f"Document title: {title}\n\n"
            f"Document content:\n{sample}\n\n"
            f"Extract the following fields:\n{schema_desc}\n\n"
            "Respond with a valid JSON object containing only the fields listed above. "
            "Use null for fields that cannot be determined from the document. "
            "For list fields, use empty arrays [] if no items are found.\n\n"
            "JSON:"
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0,
        )

        result_text = response.choices[0].message.content.strip()

        # Clean up the response (remove markdown code blocks if present)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        # Parse the JSON
        extracted = json.loads(result_text)

        # Validate that we got a dict with expected keys
        if not isinstance(extracted, dict):
            logger.warning(f"Extraction returned non-dict: {type(extracted)}")
            return {}

        # Filter to only include schema keys
        filtered = {k: v for k, v in extracted.items() if k in schema}

        logger.info(f"Extracted {len(filtered)} fields for {doc_type.value} document")
        return filtered

    except json.JSONDecodeError as e:
        logger.exception(f"Failed to parse extraction JSON: {e}")
        return {}
    except Exception as e:
        logger.exception(f"Semantic extraction failed: {e}")
        return {}


async def extract_section_structure(text: str) -> list[dict[str, Any]]:
    """
    Extract section structure from a document.

    Returns a list of sections with their headings and content boundaries.
    """
    # Simple heuristic-based section detection
    import re

    sections = []

    # Pattern for numbered sections like "1.", "1.1", "Section 1", etc.
    heading_pattern = re.compile(
        r"^(?:"
        r"(?:section\s+)?(\d+(?:\.\d+)*\.?)\s+(.+)|"  # "1.2 Title" or "Section 1.2 Title"
        r"([A-Z][A-Z\s]{2,})|"  # "ALL CAPS HEADING"
        r"(#{1,4})\s+(.+)"  # Markdown headings
        r")$",
        re.MULTILINE | re.IGNORECASE,
    )

    lines = text.split("\n")
    current_section = None

    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if not stripped_line:
            continue

        match = heading_pattern.match(stripped_line)
        if match:
            # Save previous section
            if current_section:
                current_section["end_line"] = i - 1
                sections.append(current_section)

            # Start new section
            if match.group(1):  # Numbered section
                number = match.group(1)
                title = match.group(2) or ""
            elif match.group(3):  # All caps
                number = None
                title = match.group(3)
            elif match.group(4):  # Markdown
                number = None
                title = match.group(5)
            else:
                continue

            current_section = {
                "number": number,
                "title": title.strip(),
                "start_line": i,
                "level": len(number.split(".")) if number else 1,
            }

    # Save last section
    if current_section:
        current_section["end_line"] = len(lines) - 1
        sections.append(current_section)

    return sections
