import re
from dataclasses import dataclass

from app.models import SensitivityLevel, SensitivityType


@dataclass
class SensitivityMatch:
    """A detected sensitive content match."""

    sensitivity_type: SensitivityType
    sensitivity_level: SensitivityLevel
    snippet: str
    match_start: int
    match_end: int


# Email pattern
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Phone number patterns (US-centric for v0)
PHONE_PATTERNS = [
    re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),  # 123-456-7890
    re.compile(r"\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b"),  # (123) 456-7890
]

# SSN pattern (XXX-XX-XXXX)
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Credit card patterns (13-19 digits, possibly with spaces/dashes)
CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# Secret/API key patterns
SECRET_PATTERNS = [
    # AWS Access Key ID
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # Generic API key patterns
    re.compile(r"(?i)api[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"(?i)secret[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"(?i)access[_-]?token['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{20,}"),
    # Bearer tokens
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}"),
    # Private keys
    re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    # GitHub tokens
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"),
    # Slack tokens
    re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,}"),
]


def luhn_check(card_number: str) -> bool:
    """
    Validate a credit card number using the Luhn algorithm.
    """
    # Remove spaces and dashes
    digits = re.sub(r"[\s-]", "", card_number)

    if not digits.isdigit():
        return False

    if len(digits) < 13 or len(digits) > 19:
        return False

    # Luhn algorithm
    total = 0
    for i, digit in enumerate(reversed(digits)):
        d = int(digit)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d

    return total % 10 == 0


def get_snippet(text: str, start: int, end: int, context: int = 50) -> str:
    """
    Get a snippet of text around a match with context.
    Redacts the actual sensitive content.
    """
    snippet_start = max(0, start - context)
    snippet_end = min(len(text), end + context)

    prefix = "..." if snippet_start > 0 else ""
    suffix = "..." if snippet_end < len(text) else ""

    # Get the snippet
    snippet = text[snippet_start:snippet_end]

    # Calculate the position of the match within the snippet
    match_start_in_snippet = start - snippet_start
    match_end_in_snippet = end - snippet_start

    # Redact the sensitive part
    matched_text = snippet[match_start_in_snippet:match_end_in_snippet]
    redacted = "[REDACTED]" if len(matched_text) > 4 else "****"

    snippet = snippet[:match_start_in_snippet] + redacted + snippet[match_end_in_snippet:]

    return prefix + snippet + suffix


def detect_sensitivity(text: str, chunk_start: int = 0) -> list[SensitivityMatch]:
    """
    Detect sensitive content in text.

    Args:
        text: The text to analyze
        chunk_start: Offset to add to match positions (for chunk-relative positions)

    Returns:
        List of SensitivityMatch objects
    """
    matches: list[SensitivityMatch] = []

    # Detect emails
    for match in EMAIL_PATTERN.finditer(text):
        matches.append(
            SensitivityMatch(
                sensitivity_type=SensitivityType.PERSONAL_DATA,
                sensitivity_level=SensitivityLevel.MEDIUM,
                snippet=get_snippet(text, match.start(), match.end()),
                match_start=chunk_start + match.start(),
                match_end=chunk_start + match.end(),
            )
        )

    # Detect phone numbers
    for pattern in PHONE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append(
                SensitivityMatch(
                    sensitivity_type=SensitivityType.PERSONAL_DATA,
                    sensitivity_level=SensitivityLevel.MEDIUM,
                    snippet=get_snippet(text, match.start(), match.end()),
                    match_start=chunk_start + match.start(),
                    match_end=chunk_start + match.end(),
                )
            )

    # Detect SSNs
    for match in SSN_PATTERN.finditer(text):
        matches.append(
            SensitivityMatch(
                sensitivity_type=SensitivityType.PERSONAL_DATA,
                sensitivity_level=SensitivityLevel.HIGH,
                snippet=get_snippet(text, match.start(), match.end()),
                match_start=chunk_start + match.start(),
                match_end=chunk_start + match.end(),
            )
        )

    # Detect credit cards (with Luhn validation)
    for match in CC_PATTERN.finditer(text):
        card_text = match.group()
        if luhn_check(card_text):
            matches.append(
                SensitivityMatch(
                    sensitivity_type=SensitivityType.FINANCIAL_DATA,
                    sensitivity_level=SensitivityLevel.HIGH,
                    snippet=get_snippet(text, match.start(), match.end()),
                    match_start=chunk_start + match.start(),
                    match_end=chunk_start + match.end(),
                )
            )

    # Detect secrets
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            matches.append(
                SensitivityMatch(
                    sensitivity_type=SensitivityType.SECRETS,
                    sensitivity_level=SensitivityLevel.HIGH,
                    snippet=get_snippet(text, match.start(), match.end()),
                    match_start=chunk_start + match.start(),
                    match_end=chunk_start + match.end(),
                )
            )

    return matches
