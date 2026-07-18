from __future__ import annotations

import re
from typing import Protocol


class TokenCounter(Protocol):
    name: str

    def count(self, text: str) -> int: ...


class RegexTokenCounter:
    """Deterministic fallback; reports itself as an estimate, never exact."""

    name = "regex-estimate-v1"
    _pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def count(self, text: str) -> int:
        return len(self._pattern.findall(text))


class TiktokenCounter:
    name = "o200k_base"

    def __init__(self) -> None:
        import tiktoken

        self._encoding = tiktoken.get_encoding("o200k_base")

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text))


def get_counter() -> TokenCounter:
    try:
        return TiktokenCounter()
    except Exception:
        # The optional package may be present while its encoding cache is not.
        # Token counting must remain available in offline environments; callers
        # can inspect ``name`` to distinguish an exact tokenizer count from the
        # deterministic regex estimate.
        return RegexTokenCounter()
