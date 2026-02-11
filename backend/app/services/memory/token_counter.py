"""CJK-aware token estimation without external tokenizer dependencies.

Provides a lightweight heuristic for estimating token counts across mixed
CJK/Latin text, tuned for Ollama models (roughly BPE-style tokenization).
"""

from __future__ import annotations

import re

# CJK Unicode ranges (Unified Ideographs + common extensions)
_CJK_RE = re.compile(
    "["
    "\u2e80-\u2eff"   # CJK Radicals Supplement
    "\u3000-\u303f"   # CJK Symbols and Punctuation
    "\u3040-\u309f"   # Hiragana
    "\u30a0-\u30ff"   # Katakana
    "\u3400-\u4dbf"   # CJK Unified Ideographs Extension A
    "\u4e00-\u9fff"   # CJK Unified Ideographs
    "\uf900-\ufaff"   # CJK Compatibility Ideographs
    "\uac00-\ud7af"   # Hangul Syllables
    "]"
)

# Average tokens per CJK character (~2 for BPE tokenizers)
_CJK_TOKENS_PER_CHAR: float = 2.0

# Average tokens per Latin word (~0.75 due to common word merges)
_LATIN_TOKENS_PER_WORD: float = 0.75

# Punctuation and whitespace are roughly 1 token each
_PUNCT_TOKENS: float = 1.0


def estimate_tokens(text: str) -> int:
    """Estimate the token count for mixed CJK/Latin text.

    This is a fast heuristic — not exact, but close enough for budget
    allocation without requiring tiktoken or sentencepiece.

    Args:
        text: Input text (may contain CJK, Latin, or mixed content).

    Returns:
        Estimated token count (always >= 0).
    """
    if not text:
        return 0

    cjk_chars = len(_CJK_RE.findall(text))
    non_cjk = _CJK_RE.sub("", text)
    latin_words = len(non_cjk.split())

    tokens = (cjk_chars * _CJK_TOKENS_PER_CHAR) + (latin_words * _LATIN_TOKENS_PER_WORD)
    return max(1, int(tokens + 0.5))


def truncate_to_budget(text: str, budget: int) -> str:
    """Truncate text to fit within a token budget.

    Uses a binary-search approach to find the longest prefix that fits.

    Args:
        text: Input text.
        budget: Maximum number of tokens allowed.

    Returns:
        Truncated text (or original if it already fits).
    """
    if budget <= 0:
        return ""
    if estimate_tokens(text) <= budget:
        return text

    low, high = 0, len(text)
    result = ""

    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid]
        if estimate_tokens(candidate) <= budget:
            result = candidate
            low = mid + 1
        else:
            high = mid - 1

    return result
