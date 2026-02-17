"""
Semantic XPath Parser - Parses queries into structured ASTs.

Pipeline:
  1) Global index extraction
  2) Path decomposition
  3) Step parsing (Axis + NodeTestExpr)
  4) Predicate parsing (field=~value + min/max/avg + 1-p)
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Callable

from .parsing_models import (
    Axis,
    EvidenceSelector,
    Index,
    IndexRange,
    NodeTest,
    NodeTestExpr,
    NodeTestLeaf,
    PathExpr,
    Query,
    QueryStep,
    RelativeIndex,
    SourceSpan,
    Step,
)
from .predicate_ast import (
    IdEqPredicate,
    PredicateNode,
    AggPredicate,
    AtomPredicate,
    AndPredicate,
    OrPredicate,
    AvgPredicate,
    NotPredicate,
    Token,
    TokenType,
    tokenize,
)


# =============================================================================
# Errors
# =============================================================================


class QueryParseError(Exception):
    """Raised when query parsing fails."""


class NodeTestParseError(Exception):
    """Raised when node test expression parsing fails."""


class PredicateParseError(Exception):
    """Raised when predicate parsing fails."""


# =============================================================================
# Index Parsing
# =============================================================================


def parse_relative_index(text: str, span: Optional[SourceSpan] = None) -> Optional[RelativeIndex]:
    """
    Parse a relative index string: [@+k] or [@-k].
    Returns RelativeIndex(offset) or None if not a valid relative index.
    """
    s = text.strip()
    if not s or len(s) < 2:
        return None
    if s[0] != "@":
        return None
    rest = s[1:].lstrip()
    if not rest or (rest[0] not in "+-") or (" " in rest):
        return None
    try:
        offset = int(rest)
    except ValueError:
        return None
    if offset == 0:
        raise NodeTestParseError("Relative index 0 is invalid. Use [@+1] or [@-1].")
    return RelativeIndex(offset=offset, span=span)


def parse_index(text: str, span: Optional[SourceSpan] = None) -> Optional[Index]:
    """Parse an index string like '2', '-1', '1:3', or '-2:'."""
    s = text.strip()
    if not s:
        return None

    # Reject relative index syntax; parse_relative_index handles those
    if s.startswith("@"):
        return None

    if s.count(":") > 1:
        return None

    if ":" in s:
        start_str, end_str = s.split(":", 1)
        start_str = start_str.strip()
        end_str = end_str.strip()
        if start_str == "":
            return None
        try:
            start = int(start_str)
        except ValueError:
            return None
        if start == 0:
            raise NodeTestParseError("Index 0 is invalid (1-based indexing).")
        if end_str == "":
            return Index(start=start, end=None, to_end=True, span=span)
        try:
            end = int(end_str)
        except ValueError:
            return None
        if end == 0:
            raise NodeTestParseError("Index 0 is invalid (1-based indexing).")
        return Index(start=start, end=end, span=span)

    try:
        start = int(s)
    except ValueError:
        return None
    if start == 0:
        raise NodeTestParseError("Index 0 is invalid (1-based indexing).")
    return Index(start=start, span=span)


# =============================================================================
# Node Test Expression Parser
# =============================================================================


class NodeTestExprParser:
    """
    Recursive-descent parser for node test expressions.

    Grammar (AND binds tighter than OR):
        expr      := or_expr
        or_expr   := and_expr (OR and_expr)*
        and_expr  := primary (AND primary)*
        primary   := node_test | LPAREN expr RPAREN
        node_test := IDENT | "*"  with optional [index] and [predicate]
    """

    def __init__(
        self,
        text: str,
        base_offset: int = 0,
        predicate_parser: Optional[Callable[[str, int], PredicateNode]] = None,
    ):
        self._text = text
        self._pos = 0
        self._base_offset = base_offset
        self._predicate_parser = predicate_parser or parse_predicate

    def parse(self) -> NodeTestExpr:
        expr = self._parse_or()
        self._skip_ws()
        if self._pos != len(self._text):
            raise NodeTestParseError(
                f"Unexpected trailing input at pos {self._base_offset + self._pos}"
            )
        return expr

    def _skip_ws(self) -> None:
        while self._pos < len(self._text) and self._text[self._pos].isspace():
            self._pos += 1

    def _peek(self) -> str:
        return self._text[self._pos] if self._pos < len(self._text) else ""

    def _match_keyword(self, kw: str) -> bool:
        self._skip_ws()
        end = self._pos + len(kw)
        if self._text[self._pos:end].upper() == kw.upper():
            next_char = self._text[end:end + 1]
            if next_char and (next_char.isalnum() or next_char == "_"):
                return False
            self._pos = end
            return True
        return False

    def _parse_or(self) -> NodeTestExpr:
        left = self._parse_and()
        if self._match_keyword("OR"):
            raise NodeTestParseError(
                f"Keyword OR is not supported at pos {self._base_offset + self._pos}. "
                "Use explicit node tests without boolean keywords."
            )
        return left

    def _parse_and(self) -> NodeTestExpr:
        left = self._parse_primary()
        if self._match_keyword("AND"):
            raise NodeTestParseError(
                f"Keyword AND is not supported at pos {self._base_offset + self._pos}. "
                "Use explicit node tests without boolean keywords."
            )
        return left

    def _parse_primary(self) -> NodeTestExpr:
        self._skip_ws()
        if self._peek() == "(":
            start = self._pos
            self._pos += 1
            expr = self._parse_or()
            self._skip_ws()
            if self._peek() != ")":
                raise NodeTestParseError(
                    f"Expected ')' at pos {self._base_offset + self._pos}"
                )
            self._pos += 1
            expr.span = SourceSpan(self._base_offset + start, self._base_offset + self._pos)
            return expr
        return self._parse_node_test()

    def _parse_node_test(self) -> NodeTestExpr:
        self._skip_ws()
        start = self._pos
        if self._peek() in ("*", "."):
            self._pos += 1
            kind = "wildcard"
            name = None
        else:
            name = self._parse_ident()
            if not name:
                raise NodeTestParseError(
                    f"Expected node test at pos {self._base_offset + self._pos}"
                )
            kind = "type"

        index: Optional[Index] = None
        predicate: Optional[PredicateNode] = None
        relative_index: Optional[RelativeIndex] = None

        while True:
            self._skip_ws()
            if self._peek() != "[":
                break
            content, bracket_span = self._extract_bracket()
            # Relative index [@+k] / [@-k] vs IdEq predicate [@field = "value"]
            if content.strip().startswith("@"):
                rel_idx = parse_relative_index(content, span=bracket_span)
                if rel_idx is not None:
                    if predicate is None:
                        raise NodeTestParseError(
                            f"Relative index at pos {bracket_span.start} requires a predicate. "
                            "Use predicate first, e.g. POI[node =~ \"lunch\"][@-1]"
                        )
                    if relative_index is not None:
                        raise NodeTestParseError(
                            "Multiple relative indices on a node test."
                        )
                    relative_index = rel_idx
                    continue
                # Not @+k/@-k; may be IdEq @field = "value" - fall through to predicate
            idx = parse_index(content, span=bracket_span)
            if idx:
                if index is not None:
                    raise NodeTestParseError("Multiple indices on a node test.")
                index = idx
                continue
            pred = self._predicate_parser(content, bracket_span.start + 1)
            if pred is None:
                raise NodeTestParseError(
                    f"Invalid predicate in brackets at pos {bracket_span.start}"
                )
            if predicate is not None:
                raise NodeTestParseError("Multiple predicates on a node test.")
            predicate = pred

        end = self._pos
        test = NodeTest(
            kind=kind,
            name=name,
            index=index,
            predicate=predicate,
            relative_index=relative_index,
            span=SourceSpan(self._base_offset + start, self._base_offset + end),
        )
        return NodeTestLeaf(test=test, span=test.span)

    def _parse_ident(self) -> str:
        self._skip_ws()
        start = self._pos
        if start >= len(self._text):
            return ""
        if not (self._text[start].isalpha() or self._text[start] == "_"):
            return ""
        self._pos += 1
        while self._pos < len(self._text):
            ch = self._text[self._pos]
            if ch.isalnum() or ch == "_":
                self._pos += 1
            else:
                break
        return self._text[start:self._pos]

    def _extract_bracket(self) -> Tuple[str, SourceSpan]:
        if self._peek() != "[":
            raise NodeTestParseError(
                f"Expected '[' at pos {self._base_offset + self._pos}"
            )
        start = self._pos
        self._pos += 1
        depth = 1
        in_quote: Optional[str] = None
        content_start = self._pos
        while self._pos < len(self._text) and depth > 0:
            ch = self._text[self._pos]
            if in_quote:
                if ch == in_quote:
                    in_quote = None
            else:
                if ch in ('"', "'"):
                    in_quote = ch
                elif ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
            self._pos += 1
        if depth != 0:
            raise NodeTestParseError(
                f"Unterminated '[' starting at pos {self._base_offset + start}"
            )
        content_end = self._pos - 1
        content = self._text[content_start:content_end]
        span = SourceSpan(self._base_offset + start, self._base_offset + self._pos)
        return content, span


# =============================================================================
# Predicate Parser
# =============================================================================


class PredicateParser:
    """
    Recursive-descent parser for predicate expressions.

    Grammar (supported subset):
        predicate   := or_expr
        primary     := atom_expr | func_expr | evidence_agg_expr | LPAREN predicate RPAREN
        atom_expr   := field =~ "value"   # bare semantic match
        func_expr   := min(p1, p2, ...) | max(p1, p2, ...) | avg(p1, p2, ...)
        evidence_agg_expr := agg_min(EvidenceStep) | agg_max(EvidenceStep) | agg_avg(EvidenceStep)
        EvidenceStep := Axis NodeType [Predicate], e.g. /*[node =~ "jazz"] or //POI[content =~ "museum"]

    Unsupported by design:
        AND / OR / NOT keywords, agg_exists(...), agg_prev(...)
    """

    def __init__(self, tokens: List[Token], source_text: str, base_offset: int = 0):
        self._tokens = tokens
        self._text = source_text
        self._pos = 0
        self._base_offset = base_offset

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _peek_ahead(self, delta: int) -> Token:
        idx = self._pos + delta
        if idx >= len(self._tokens):
            return self._tokens[-1]
        return self._tokens[idx]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, tt: TokenType) -> Token:
        tok = self._peek()
        if tok.type != tt:
            raise PredicateParseError(
                f"Expected {tt.name} but got {tok.type.name} ({tok.value!r}) at pos {tok.pos}"
            )
        return self._advance()

    def _match(self, tt: TokenType) -> Optional[Token]:
        if self._peek().type == tt:
            return self._advance()
        return None

    def parse(self) -> PredicateNode:
        node = self._parse_or()
        if self._peek().type != TokenType.EOF:
            tok = self._peek()
            raise PredicateParseError(
                f"Unexpected token {tok.type.name} ({tok.value!r}) at pos {tok.pos}"
            )
        return node

    def _parse_or(self) -> PredicateNode:
        left = self._parse_and()
        if self._peek().type == TokenType.OR:
            tok = self._peek()
            raise PredicateParseError(
                f"Keyword OR is not supported at pos {tok.pos}. Use max(...)."
            )
        return left

    def _parse_and(self) -> PredicateNode:
        left = self._parse_unary()
        if self._peek().type == TokenType.AND:
            tok = self._peek()
            raise PredicateParseError(
                f"Keyword AND is not supported at pos {tok.pos}. Use min(...)."
            )
        return left

    def _parse_unary(self) -> PredicateNode:
        if self._peek().type == TokenType.NOT:
            tok = self._peek()
            raise PredicateParseError(
                f"Keyword NOT is not supported at pos {tok.pos}. Use 1-p form."
            )
        if self._peek().type == TokenType.NUMBER:
            one_tok = self._peek()
            if one_tok.value != "1":
                raise PredicateParseError(
                    f"Only '1-p' is supported for inversion at pos {one_tok.pos}."
                )
            self._advance()
            minus_tok = self._match(TokenType.MINUS)
            if minus_tok is None:
                raise PredicateParseError(
                    f"Expected '-' after '1' for inversion at pos {self._peek().pos}."
                )
            child = self._parse_unary()
            end = child.span.end if child.span else minus_tok.end
            return NotPredicate(child=child, span=SourceSpan(one_tok.pos, end))
        return self._parse_primary()

    def _parse_primary(self) -> PredicateNode:
        tt = self._peek().type

        if tt == TokenType.AT:
            return self._parse_id_eq()

        if tt == TokenType.IDENT:
            if self._peek_ahead(1).type == TokenType.TILDE_EQ:
                return self._parse_atom_direct()
            if self._peek_ahead(1).type == TokenType.LPAREN:
                return self._parse_function_expr()
            return self._parse_atom_direct()

        if tt in (TokenType.AGG_EXISTS, TokenType.AGG_PREV):
            tok = self._peek()
            raise PredicateParseError(
                f"Aggregation expressions are not supported at pos {tok.pos}. "
                "Use max(...) / avg(...)."
            )

        if tt in (TokenType.AGG_MIN, TokenType.AGG_MAX, TokenType.AGG_AVG):
            return self._parse_evidence_agg()

        if tt == TokenType.LPAREN:
            lparen = self._advance()
            inner = self._parse_or()
            rparen = self._expect(TokenType.RPAREN)
            inner.span = SourceSpan(lparen.pos, rparen.end)
            return inner

        tok = self._peek()
        raise PredicateParseError(
            f"Expected field=~value, agg, or ( but got {tok.type.name} ({tok.value!r}) at pos {tok.pos}"
        )

    def _parse_id_eq(self) -> IdEqPredicate:
        """Parse @field = "value" - exact match on attribute."""
        at_tok = self._expect(TokenType.AT)
        field_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.EQ)
        value_tok = self._expect(TokenType.STRING)
        span = SourceSpan(at_tok.pos, value_tok.end)
        return IdEqPredicate(
            field=field_tok.value,
            value=value_tok.value,
            span=span,
        )

    def _parse_atom_direct(self) -> AtomPredicate:
        field_tok = self._expect(TokenType.IDENT)
        if self._peek().type != TokenType.TILDE_EQ:
            raise PredicateParseError(
                f"Expected '=~' after field at pos {self._peek().pos}"
            )
        self._advance()
        value_tok = self._expect(TokenType.STRING)
        span = SourceSpan(field_tok.pos, value_tok.end)
        return AtomPredicate(
            field=field_tok.value,
            operator="=~",
            value=value_tok.value,
            span=span,
        )

    def _parse_function_expr(self) -> PredicateNode:
        fn_tok = self._expect(TokenType.IDENT)
        fn_name = fn_tok.value
        lparen = self._expect(TokenType.LPAREN)

        idx = self._find_matching_rparen_idx()
        if idx is None:
            raise PredicateParseError(
                f"Unterminated function expression starting at pos {fn_tok.pos}"
            )

        rparen = self._tokens[idx]
        inner_start = lparen.end - self._base_offset
        inner_end = rparen.pos - self._base_offset
        inner_text = self._text[inner_start:inner_end]

        self._pos = idx + 1
        span = SourceSpan(fn_tok.pos, rparen.end)

        if fn_name in {"min", "max", "avg"}:
            args = _split_top_level_args(inner_text)
            if not args:
                raise PredicateParseError(f"{fn_name}(...) requires at least one argument.")
            children: List[PredicateNode] = []
            for raw_arg, arg_start in args:
                stripped = raw_arg.strip()
                if not stripped:
                    raise PredicateParseError(f"{fn_name}(...) contains an empty argument.")
                leading_ws = len(raw_arg) - len(raw_arg.lstrip())
                arg_offset = lparen.end + arg_start + leading_ws
                children.append(parse_predicate(stripped, offset=arg_offset))
            if len(children) == 1:
                return children[0]
            if fn_name == "min":
                return AndPredicate(children=children, span=span)
            if fn_name == "max":
                return OrPredicate(children=children, span=span)
            return AvgPredicate(children=children, span=span)

        raise PredicateParseError(
            f"Unsupported predicate function '{fn_tok.value}' at pos {fn_tok.pos}. "
            "Supported functions are min(...), max(...), avg(...)."
        )

    def _parse_evidence_agg(self) -> AggPredicate:
        tok = self._advance()
        agg_map = {
            TokenType.AGG_MIN: "min",
            TokenType.AGG_MAX: "max",
            TokenType.AGG_AVG: "avg",
        }
        agg_type = agg_map[tok.type]
        self._expect(TokenType.LPAREN)

        idx = self._find_matching_rparen_idx()
        if idx is None:
            raise PredicateParseError(
                f"Unterminated agg_{agg_type}(...) starting at pos {tok.pos}"
            )

        rparen = self._tokens[idx]
        lparen_tok = self._tokens[self._pos - 1]
        inner_start = lparen_tok.end - self._base_offset
        inner_end = rparen.pos - self._base_offset
        inner_text = self._text[inner_start:inner_end]

        self._pos = idx + 1
        span = SourceSpan(tok.pos, rparen.end)

        selector, inner_pred = parse_evidence_step(inner_text, self._base_offset + inner_start)

        return AggPredicate(
            agg_type=agg_type,
            selector=selector,
            inner=inner_pred,
            span=span,
        )

    def _find_matching_rparen_idx(self) -> Optional[int]:
        depth = 1
        idx = self._pos
        while idx < len(self._tokens):
            tok = self._tokens[idx]
            if tok.type == TokenType.LPAREN:
                depth += 1
            elif tok.type == TokenType.RPAREN:
                depth -= 1
                if depth == 0:
                    return idx
            idx += 1
        return None


def parse_predicate(text: str, offset: int = 0) -> PredicateNode:
    """Convenience: tokenize + parse a predicate string."""
    tokens = tokenize(text, offset=offset)
    return PredicateParser(tokens, text, base_offset=offset).parse()


def parse_evidence_step(
    text: str, base_offset: int = 0
) -> Tuple[EvidenceSelector, PredicateNode]:
    """
    Parse an evidence step: Axis NodeType [Predicate].
    E.g. /*[node =~ "jazz"] or //Day[node =~ "museum"].
    Returns (EvidenceSelector, PredicateNode).
    """
    s = text.strip()
    pos = 0
    if pos >= len(s):
        raise PredicateParseError(
            f"Evidence step expected axis (/ or //) at pos {base_offset}"
        )

    if s.startswith("//"):
        axis = Axis.DESC
        pos = 2
    elif s[pos] == "/":
        axis = Axis.CHILD
        pos = 1
    else:
        raise PredicateParseError(
            f"Evidence step expected axis (/ or //) at pos {base_offset + pos}"
        )

    while pos < len(s) and s[pos] in " \t":
        pos += 1
    if pos >= len(s):
        raise PredicateParseError(
            f"Evidence step expected node type (* or name) at pos {base_offset + pos}"
        )

    if s[pos] == "*":
        node_test = NodeTestLeaf(test=NodeTest(kind="wildcard", name=None))
        pos += 1
    elif s[pos].isalpha() or s[pos] == "_":
        start = pos
        pos += 1
        while pos < len(s) and (s[pos].isalnum() or s[pos] == "_"):
            pos += 1
        name = s[start:pos]
        node_test = NodeTestLeaf(test=NodeTest(kind="type", name=name))
    else:
        raise PredicateParseError(
            f"Evidence step expected node type (* or name) at pos {base_offset + pos}"
        )

    while pos < len(s) and s[pos] in " \t":
        pos += 1
    if pos >= len(s) or s[pos] != "[":
        raise PredicateParseError(
            f"Evidence step requires predicate [...] at pos {base_offset + pos}"
        )

    bracket_start = pos
    pred_content, _ = _extract_balanced_bracket(s, pos)
    pred_offset = base_offset + bracket_start + 1
    inner = parse_predicate(pred_content, offset=pred_offset)

    selector = EvidenceSelector(axis=axis, test=node_test)
    return selector, inner


def _extract_balanced_bracket(text: str, start: int) -> Tuple[str, int]:
    """
    Extract content of balanced [...] starting at start.
    Returns (content, end_pos) where end_pos is past the closing ].
    """
    if start >= len(text) or text[start] != "[":
        raise PredicateParseError(f"Expected '[' at position {start}")
    depth = 1
    i = start + 1
    in_quote: Optional[str] = None
    while i < len(text) and depth > 0:
        ch = text[i]
        if in_quote:
            if ch == in_quote:
                in_quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            i += 1
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        i += 1
    if depth != 0:
        raise PredicateParseError("Unterminated '[' in evidence step")
    content = text[start + 1 : i - 1]
    return content, i


def _split_top_level_args(text: str) -> List[Tuple[str, int]]:
    """
    Split function arguments by top-level commas.

    Commas nested inside parentheses/brackets or quotes are ignored.
    Returns (arg_text, arg_start_offset_in_text) tuples.
    """
    args: List[Tuple[str, int]] = []
    if text.strip() == "":
        return args

    paren_depth = 0
    bracket_depth = 0
    in_quote: Optional[str] = None
    start = 0

    for i, ch in enumerate(text):
        if in_quote:
            if ch == in_quote:
                in_quote = None
            continue

        if ch in ('"', "'"):
            in_quote = ch
            continue
        if ch == "(":
            paren_depth += 1
            continue
        if ch == ")":
            paren_depth = max(0, paren_depth - 1)
            continue
        if ch == "[":
            bracket_depth += 1
            continue
        if ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
            continue
        if ch == "," and paren_depth == 0 and bracket_depth == 0:
            args.append((text[start:i], start))
            start = i + 1

    args.append((text[start:], start))
    return args


# =============================================================================
# Query Parser
# =============================================================================


class QueryParser:
    """
    Parses Semantic XPath queries into structured ASTs.
    """

    def parse(self, query: str) -> Query:
        if not query:
            raise QueryParseError("Empty query.")

        start = _skip_leading_ws(query, 0)
        end = _skip_trailing_ws(query, len(query))
        text = query[start:end]

        inner_text = text
        inner_offset = start
        global_index: Optional[Index] = None

        if text.startswith("("):
            close_idx = _find_matching_paren(text, 0)
            if close_idx is not None:
                after = text[close_idx + 1:].lstrip()
                if after.startswith("[") and text.rstrip().endswith("]"):
                    bracket_start = close_idx + 1 + (len(text[close_idx + 1:]) - len(after))
                    idx_content, bracket_end = _extract_bracket_global(text, bracket_start)
                    if text[bracket_end:].strip() == "":
                        idx_span = SourceSpan(
                            inner_offset + bracket_start,
                            inner_offset + bracket_end,
                        )
                        idx = parse_index(idx_content, span=idx_span)
                        if idx is None:
                            raise QueryParseError("Invalid global index.")
                        global_index = idx
                        inner_text = text[1:close_idx]
                        inner_offset = start + 1

        path = self._parse_path(inner_text, inner_offset)
        span = SourceSpan(start, end)
        return Query(path=path, global_index=global_index, span=span)

    def parse_legacy(self, query: str) -> Tuple[List[QueryStep], Optional[IndexRange]]:
        """
        Legacy parse mode returning QueryStep + IndexRange for backward compatibility.
        """
        parsed = self.parse(query)
        steps: List[QueryStep] = []
        for step in parsed.path.steps:
            if not isinstance(step.test, NodeTestLeaf):
                raise QueryParseError("Legacy parse supports only simple node tests.")
            test = step.test.test
            if test.kind == "wildcard":
                node_type = "*"
            else:
                node_type = test.name or "?"
            axis = step.axis.value if step.axis != Axis.NONE else "child"
            index = None
            if test.index:
                index = IndexRange(
                    start=test.index.start,
                    end=test.index.end,
                    to_end=test.index.to_end,
                )
            steps.append(QueryStep(
                node_type=node_type,
                predicate=test.predicate,
                index=index,
                axis=axis,
            ))

        global_index = None
        if parsed.global_index:
            global_index = IndexRange(
                start=parsed.global_index.start,
                end=parsed.global_index.end,
                to_end=parsed.global_index.to_end,
            )
        return steps, global_index

    def _parse_path(self, text: str, base_offset: int) -> PathExpr:
        steps: List[Step] = []
        for part, start, end, axis_hint in _split_path(text, base_offset):
            step = self._parse_step(part, start, end, axis_hint)
            steps.append(step)
        span = SourceSpan(base_offset, base_offset + len(text))
        return PathExpr(steps=steps, span=span)

    def _parse_step(self, text: str, start: int, end: int, axis_hint: Axis) -> Step:
        trimmed, trim_offset = _lstrip_with_offset(text)
        axis, axis_len = _parse_axis_prefix(trimmed)
        body = trimmed[axis_len:]
        if axis_len == 0:
            axis = axis_hint
        body_offset = start + trim_offset + axis_len
        parser = NodeTestExprParser(body, base_offset=body_offset, predicate_parser=parse_predicate)
        expr = parser.parse()
        span = SourceSpan(start, end)
        return Step(axis=axis, test=expr, span=span)


# =============================================================================
# Helpers
# =============================================================================


def _parse_axis_prefix(text: str) -> Tuple[Axis, int]:
    if text.startswith("//"):
        return Axis.DESC, len("//")
    if text.startswith("/"):
        return Axis.NONE, len("/")
    return Axis.NONE, 0


def _skip_leading_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _skip_trailing_ws(text: str, pos: int) -> int:
    while pos > 0 and text[pos - 1].isspace():
        pos -= 1
    return pos


def _lstrip_with_offset(text: str) -> Tuple[str, int]:
    original_len = len(text)
    stripped = text.lstrip()
    return stripped, original_len - len(stripped)


def _find_matching_paren(text: str, start: int) -> Optional[int]:
    if text[start] != "(":
        return None
    depth = 0
    in_quote: Optional[str] = None
    for i in range(start, len(text)):
        ch = text[i]
        if in_quote:
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ('"', "'"):
            in_quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _extract_bracket_global(text: str, start: int) -> Tuple[str, int]:
    if text[start] != "[":
        raise QueryParseError("Expected '[' for global index.")
    depth = 1
    in_quote: Optional[str] = None
    i = start + 1
    while i < len(text) and depth > 0:
        ch = text[i]
        if in_quote:
            if ch == in_quote:
                in_quote = None
        else:
            if ch in ('"', "'"):
                in_quote = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
        i += 1
    if depth != 0:
        raise QueryParseError("Unterminated global index bracket.")
    return text[start + 1:i - 1], i


def _split_path(text: str, base_offset: int) -> List[Tuple[str, int, int, Axis]]:
    parts: List[Tuple[str, int, int, Axis]] = []
    bracket_depth = 0
    paren_depth = 0
    in_quote: Optional[str] = None
    current_start = 0
    pending_axis = Axis.NONE

    i = 0
    while i < len(text):
        ch = text[i]
        if in_quote:
            if ch == in_quote:
                in_quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = ch
            i += 1
            continue
        if ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
        elif ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        elif ch == "/" and bracket_depth == 0 and paren_depth == 0:
            is_double = i + 1 < len(text) and text[i + 1] == "/"
            segment = text[current_start:i]
            if segment:
                start = base_offset + current_start
                end = base_offset + i
                parts.append((segment, start, end, pending_axis))
                pending_axis = Axis.NONE
            if is_double:
                pending_axis = Axis.DESC
                i += 1
            else:
                pending_axis = Axis.NONE
            current_start = i + 1
        i += 1

    if current_start < len(text):
        segment = text[current_start:]
        if segment:
            start = base_offset + current_start
            end = base_offset + len(text)
            parts.append((segment, start, end, pending_axis))

    # Trim leading empty segment for absolute paths
    if parts and parts[0][0] == "":
        parts = parts[1:]
    return parts


# Singleton instance
_parser_instance: Optional[QueryParser] = None


def get_parser() -> QueryParser:
    """Get singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = QueryParser()
    return _parser_instance
