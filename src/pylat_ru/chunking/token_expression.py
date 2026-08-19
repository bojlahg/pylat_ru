"""src/pylat_ru/chunking/token_expression.py

Native Python token expression evaluator for OpenRegex expressions used by RussianChunker.
Supports exact syntax used by pinned LanguageTool RussianChunker:
- `<string=...>`, `<foo>` (token string matching)
- `<regex=...>`, `<regexCS=...>` (token regex matching)
- `<chunk=...>` (chunk tag matching)
- `<pos=...>` (POS tag substring matching)
- `<posre=...>`, `<posregex=...>` (POS tag regex matching)
- Logical AND (`&`) and negation (`!`)
- Quantifiers (`+`, `*`)
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple
import regex


@dataclass
class ChunkTaggedToken:
    """Token representation manipulated by RussianChunker."""
    token: str
    chunk_tags: List[str]
    readings: Any  # AnalyzedTokenReadings or None


class TokenCondition:
    """Atomic condition on a single ChunkTaggedToken."""

    def __init__(
        self,
        kind: str,
        value: str,
        negated: bool = False,
        case_sensitive: bool = False,
    ) -> None:
        self.kind = kind
        self.value = value
        self.negated = negated
        self.case_sensitive = case_sensitive

        # Precompile regex if applicable
        if kind in ("regex", "regexCS", "posre", "posregex"):
            flags = 0 if (kind == "regexCS" or case_sensitive) else regex.IGNORECASE
            self._compiled_regex = regex.compile(f"^{value}$", flags)
        elif kind == "chunk":
            # In Java TokenPredicate, chunk uses StringMatcher.matches(chunkTag)
            # If value contains regex characters, compile, otherwise exact match
            self._compiled_regex = regex.compile(f"^{regex.escape(value)}$", regex.IGNORECASE)
        else:
            self._compiled_regex = None

    def evaluate(self, token: ChunkTaggedToken) -> bool:
        """Evaluate condition on token."""
        result = self._eval_raw(token)
        return not result if self.negated else result

    def _eval_raw(self, token: ChunkTaggedToken) -> bool:
        if self.kind == "string":
            if self.case_sensitive:
                return token.token == self.value
            return token.token.lower() == self.value.lower()

        elif self.kind in ("regex", "regexCS"):
            assert self._compiled_regex is not None
            return self._compiled_regex.search(token.token) is not None

        elif self.kind == "chunk":
            for ct in token.chunk_tags:
                if self.case_sensitive:
                    if ct == self.value:
                        return True
                else:
                    if ct.lower() == self.value.lower():
                        return True
            return False

        elif self.kind == "pos":
            if token.readings is None:
                return False
            for r in token.readings:
                pos = getattr(r, "pos_tag", None)
                if pos and self.value in pos:
                    return True
            return False

        elif self.kind in ("posre", "posregex"):
            if token.readings is None:
                return False
            assert self._compiled_regex is not None
            for r in token.readings:
                pos = getattr(r, "pos_tag", None)
                if pos and self._compiled_regex.search(pos) is not None:
                    return True
            return False

        raise ValueError(f"Unknown condition kind: {self.kind!r}")

    def __repr__(self) -> str:
        neg = "!" if self.negated else ""
        return f"{neg}{self.kind}={self.value}"


class TokenPredicate:
    """Conjunction of TokenConditions joined by '&'."""

    def __init__(self, conditions: List[TokenCondition], raw_str: str = "") -> None:
        self.conditions = conditions
        self.raw_str = raw_str

    def matches(self, token: ChunkTaggedToken) -> bool:
        """Check if token satisfies all conjunction conditions."""
        return all(c.evaluate(token) for c in self.conditions)

    def __repr__(self) -> str:
        return f"<{self.raw_str}>"


def _unquote(s: str) -> str:
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    return s


def parse_token_predicate(raw_inner: str, case_sensitive: bool = False) -> TokenPredicate:
    """Parse inner string of a `<...>` expression into a TokenPredicate."""
    parts = [p.strip() for p in raw_inner.split("&")]
    conditions: List[TokenCondition] = []

    for part in parts:
        if not part:
            continue
        negated = False
        if part.startswith("!"):
            negated = True
            part = part[1:].strip()

        if "=" in part:
            key, val = part.split("=", 1)
            key = key.strip()
            val = _unquote(val.strip())

            if key == "string":
                conditions.append(TokenCondition("string", val, negated, case_sensitive))
            elif key == "regex":
                conditions.append(TokenCondition("regex", val, negated, case_sensitive))
            elif key == "regexCS":
                conditions.append(TokenCondition("regexCS", val, negated, True))
            elif key == "chunk":
                conditions.append(TokenCondition("chunk", val, negated, case_sensitive))
            elif key == "pos":
                conditions.append(TokenCondition("pos", val, negated, True))
            elif key in ("posre", "posregex"):
                conditions.append(TokenCondition("posre", val, negated, True))
            else:
                raise ValueError(f"Unsupported token predicate key: {key!r} in {raw_inner!r}")
        else:
            # Short form <foo> -> string=foo
            val = _unquote(part.strip())
            conditions.append(TokenCondition("string", val, negated, case_sensitive))

    return TokenPredicate(conditions, raw_inner)


@dataclass
class TokenPatternElement:
    predicate: TokenPredicate
    quantifier: str  # "1", "+", or "*"


class TokenExpression:
    """Compiled sequence of TokenPatternElements."""

    def __init__(self, raw_expr: str, case_sensitive: bool = False) -> None:
        self.raw_expr = raw_expr
        self.elements: List[TokenPatternElement] = self._compile(raw_expr, case_sensitive)

    def _compile(self, expr: str, case_sensitive: bool) -> List[TokenPatternElement]:
        elements: List[TokenPatternElement] = []
        i = 0
        n = len(expr)

        while i < n:
            # Skip whitespace
            while i < n and expr[i].isspace():
                i += 1
            if i >= n:
                break

            if expr[i] != "<":
                raise ValueError(f"Expected '<' at position {i} in expression: {expr!r}")

            # Find matching '>'
            j = expr.find(">", i)
            if j == -1:
                raise ValueError(f"Unclosed '<' at position {i} in expression: {expr!r}")

            inner = expr[i + 1 : j].strip()
            pred = parse_token_predicate(inner, case_sensitive)
            i = j + 1

            # Check optional quantifier
            quantifier = "1"
            if i < n and expr[i] in ("+", "*"):
                quantifier = expr[i]
                i += 1

            elements.append(TokenPatternElement(pred, quantifier))

        return elements

    def find_all(self, tokens: Sequence[ChunkTaggedToken]) -> List[Tuple[int, int]]:
        """Find all non-overlapping matches in tokens list."""
        matches: List[Tuple[int, int]] = []
        i = 0
        n = len(tokens)

        while i < n:
            matched_span: Optional[Tuple[int, int]] = None
            for start in range(i, n):
                end = self._match_at(tokens, start, 0)
                if end is not None and end > start:
                    matched_span = (start, end)
                    break

            if matched_span is not None:
                matches.append(matched_span)
                i = matched_span[1]
            else:
                break

        return matches

    def _match_at(
        self,
        tokens: Sequence[ChunkTaggedToken],
        tok_idx: int,
        elem_idx: int,
    ) -> Optional[int]:
        """Backtracking matcher for token expression elements."""
        if elem_idx >= len(self.elements):
            return tok_idx

        elem = self.elements[elem_idx]
        pred = elem.predicate
        quant = elem.quantifier

        if quant == "1":
            if tok_idx < len(tokens) and pred.matches(tokens[tok_idx]):
                return self._match_at(tokens, tok_idx + 1, elem_idx + 1)
            return None

        elif quant in ("+", "*"):
            # Greedily match as many tokens as possible
            match_counts = []
            cur = tok_idx
            while cur < len(tokens) and pred.matches(tokens[cur]):
                cur += 1
                match_counts.append(cur)

            min_count = 1 if quant == "+" else 0
            # Try from longest greedy match down to min_count
            for next_tok_idx in reversed([tok_idx] + match_counts if quant == "*" else match_counts):
                if quant == "+" and next_tok_idx == tok_idx:
                    continue
                res = self._match_at(tokens, next_tok_idx, elem_idx + 1)
                if res is not None:
                    return res
            return None

        return None
