"""Prompt Injection Defense and Input Hygiene Filters.
Sanitizes user objectives and untrusted tool outputs.
"""
import re
from typing import Tuple

# Common prompt injection patterns (instruction overrides, delimiter breakouts, roleplay bypass)
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"<\s*\|\s*im_start\s*\|\s*>", re.IGNORECASE),
    re.compile(r"<\s*\|\s*im_end\s*\|\s*>", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]", re.IGNORECASE),
    re.compile(r"\[\s*/\s*INST\s*\]", re.IGNORECASE),
    re.compile(r"you\s+must\s+grant\s+(me\s+|yourself\s+)?admin", re.IGNORECASE),
    re.compile(r"override\s+policy", re.IGNORECASE),
]


class InjectionGuard:
    """Detects and neutralizes prompt injection threats."""

    @staticmethod
    def inspect_and_sanitize(text: str) -> Tuple[str, bool]:
        """Inspects text for prompt injection markers.
        Returns: (sanitized_text, was_flagged)
        """
        flagged = False
        cleaned = text

        for pattern in INJECTION_PATTERNS:
            if pattern.search(cleaned):
                flagged = True
                cleaned = pattern.sub("[FILTERED_POTENTIAL_INJECTION]", cleaned)

        # Truncate overly long single-token strings (buffer overflow mitigation)
        if len(cleaned) > 10000:
            cleaned = cleaned[:10000] + " [TRUNCATED_FOR_SAFETY]"
            flagged = True

        return cleaned, flagged


injection_guard = InjectionGuard()
