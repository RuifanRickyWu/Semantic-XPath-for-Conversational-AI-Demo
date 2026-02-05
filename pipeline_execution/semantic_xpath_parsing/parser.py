"""
Query Parser - Parses Semantic XPath query strings into structured QueryStep objects.

Grammar:
    Query Q := Step | Step / Query | (Query)[GlobalIndex]
    Step := Axis NodeType Index [Predicate]
    Axis := none | desc ::
    Index := none | [i] | [-i] | [i:j]
    Predicate := Predicate AND Predicate | Predicate OR Predicate | not(Predicate) | Atom | Agg
    Atom := atom(content =~ "value")
    Agg := agg_exists(Axis ChildType [Predicate]) | agg_prev(Axis ChildType [Predicate])

Predicate parsing uses a tokenizer + recursive-descent parser with correct
operator precedence: NOT > AND > OR.
"""

import re
from typing import List, Optional, Tuple

from .parsing_models import IndexRange, QueryStep
from .predicate_ast import (
    PredicateNode,
    AtomPredicate,
    AggExistsPredicate,
    AggPrevPredicate,
    AndPredicate,
    OrPredicate,
    NotPredicate,
    Token,
    TokenType,
    tokenize,
)


# =============================================================================
# Predicate Parser (recursive descent over token stream)
# =============================================================================

class PredicateParseError(Exception):
    """Raised when predicate parsing fails."""
    pass


class PredicateParser:
    """
    Recursive-descent parser that converts a token stream into a PredicateNode AST.

    Grammar (priority low → high):
        predicate   := or_expr
        or_expr     := and_expr ( OR and_expr )*
        and_expr    := unary_expr ( AND unary_expr )*
        unary_expr  := NOT LPAREN predicate RPAREN
                     | primary
        primary     := atom_expr
                     | agg_exists_expr
                     | agg_prev_expr
                     | LPAREN predicate RPAREN        # grouping
        atom_expr   := ATOM LPAREN IDENT TILDE_EQ STRING RPAREN
        agg_expr    := (AGG_EXISTS|AGG_PREV) LPAREN agg_inner RPAREN
        agg_inner   := [axis COLONCOLON] IDENT LBRACK predicate RBRACK
                     | predicate
    """

    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos = 0

    # -- helpers --------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

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

    # -- grammar rules --------------------------------------------------------

    def parse(self) -> PredicateNode:
        """Entry point.  Parse the full predicate expression."""
        node = self._parse_or_expr()
        # Must have consumed everything (except EOF)
        if self._peek().type != TokenType.EOF:
            tok = self._peek()
            raise PredicateParseError(
                f"Unexpected token {tok.type.name} ({tok.value!r}) at pos {tok.pos}"
            )
        return node

    def _parse_or_expr(self) -> PredicateNode:
        """or_expr := and_expr ( OR and_expr )*"""
        left = self._parse_and_expr()
        parts = [left]
        while self._match(TokenType.OR):
            parts.append(self._parse_and_expr())
        if len(parts) == 1:
            return parts[0]
        return OrPredicate(children=parts)

    def _parse_and_expr(self) -> PredicateNode:
        """and_expr := unary_expr ( AND unary_expr )*"""
        left = self._parse_unary_expr()
        parts = [left]
        while self._match(TokenType.AND):
            parts.append(self._parse_unary_expr())
        if len(parts) == 1:
            return parts[0]
        return AndPredicate(children=parts)

    def _parse_unary_expr(self) -> PredicateNode:
        """unary_expr := NOT LPAREN predicate RPAREN | primary"""
        if self._peek().type == TokenType.NOT:
            self._advance()
            self._expect(TokenType.LPAREN)
            inner = self._parse_or_expr()
            self._expect(TokenType.RPAREN)
            return NotPredicate(child=inner)
        return self._parse_primary()

    def _parse_primary(self) -> PredicateNode:
        """primary := atom_expr | agg_exists_expr | agg_prev_expr | LPAREN predicate RPAREN"""
        tt = self._peek().type

        if tt == TokenType.ATOM:
            return self._parse_atom_expr()

        if tt == TokenType.AGG_EXISTS:
            return self._parse_agg_expr(is_exists=True)

        if tt == TokenType.AGG_PREV:
            return self._parse_agg_expr(is_exists=False)

        if tt == TokenType.LPAREN:
            # Grouping parentheses
            self._advance()
            inner = self._parse_or_expr()
            self._expect(TokenType.RPAREN)
            return inner

        tok = self._peek()
        raise PredicateParseError(
            f"Expected atom/agg_exists/agg_prev/( but got {tok.type.name} "
            f"({tok.value!r}) at pos {tok.pos}"
        )

    def _parse_atom_expr(self) -> AtomPredicate:
        """atom_expr := ATOM LPAREN IDENT TILDE_EQ STRING RPAREN"""
        self._expect(TokenType.ATOM)
        self._expect(TokenType.LPAREN)
        field_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.TILDE_EQ)
        value_tok = self._expect(TokenType.STRING)
        self._expect(TokenType.RPAREN)
        return AtomPredicate(field=field_tok.value, value=value_tok.value)

    def _parse_agg_expr(self, *, is_exists: bool) -> PredicateNode:
        """
        agg_expr := (AGG_EXISTS|AGG_PREV) LPAREN agg_inner RPAREN
        agg_inner := [axis COLONCOLON] IDENT LBRACK predicate RBRACK
                   | predicate     (no child type)
        """
        self._advance()  # consume AGG_EXISTS or AGG_PREV
        self._expect(TokenType.LPAREN)

        child_axis = "child"
        child_type: Optional[str] = None

        # Lookahead: does this start with [axis::]IDENT[ ?
        # We check if current token is IDENT and there is a LBRACK after it,
        # OR if current token is IDENT and the next is COLONCOLON.
        if self._peek().type == TokenType.IDENT:
            # Peek further to decide if this is [axis::]Type[pred]
            saved_pos = self._pos

            # Check for axis:: prefix
            ident_tok = self._advance()  # consume IDENT
            if self._peek().type == TokenType.COLONCOLON:
                # This is axis::Type[pred]
                child_axis = ident_tok.value  # "desc" or "child"
                self._advance()  # consume ::
                type_tok = self._expect(TokenType.IDENT)
                child_type = type_tok.value
                self._expect(TokenType.LBRACK)
                inner = self._parse_or_expr()
                self._expect(TokenType.RBRACK)
            elif self._peek().type == TokenType.LBRACK:
                # This is Type[pred] (no axis prefix)
                child_type = ident_tok.value
                self._advance()  # consume [
                inner = self._parse_or_expr()
                self._expect(TokenType.RBRACK)
            else:
                # Not child-type pattern -- backtrack and parse as plain predicate
                self._pos = saved_pos
                inner = self._parse_or_expr()
        else:
            # Starts with atom/agg/not/( -- parse as plain predicate
            inner = self._parse_or_expr()

        self._expect(TokenType.RPAREN)

        if is_exists:
            return AggExistsPredicate(inner=inner, child_type=child_type, child_axis=child_axis)
        else:
            return AggPrevPredicate(inner=inner, child_type=child_type, child_axis=child_axis)


def parse_predicate(text: str) -> PredicateNode:
    """Convenience: tokenize + parse a predicate string."""
    tokens = tokenize(text)
    return PredicateParser(tokens).parse()


# =============================================================================
# XPath Query Parser (path-level parsing)
# =============================================================================

class QueryParser:
    """
    Parses Semantic XPath queries into structured steps.

    Paper Formalization - Query Q = s₁/s₂/.../sₘ where each step sᵢ = (axisᵢ, κᵢ, ψᵢ)

    Supports:
    - Axis selection: desc::POI or none (default: children)
    - Type matching: /Itinerary/Day/POI
    - Positional index: POI[2], POI[-1], POI[1:3]
    - Predicates: atom(), agg_exists(), agg_prev(), AND, OR, not()
    - Global indexing: (/Itinerary/Day/POI)[5]
    """

    def parse(self, query: str) -> Tuple[List[QueryStep], Optional[IndexRange]]:
        """
        Parse a query string into steps and optional global index.

        Returns:
            Tuple of (list of QueryStep, optional global IndexRange)
        """
        global_index = None
        inner_query = query

        # Check for global indexing: (/path)[-2:], (/path)[1:3], (/path)[n]
        global_to_end_match = re.match(r'^\((.+)\)\[(-?\d+):\]$', query)
        if global_to_end_match:
            inner_query = global_to_end_match.group(1)
            start = int(global_to_end_match.group(2))
            global_index = IndexRange(start=start, to_end=True)
        else:
            global_range_match = re.match(r'^\((.+)\)\[(-?\d+):(-?\d+)\]$', query)
            if global_range_match:
                inner_query = global_range_match.group(1)
                start = int(global_range_match.group(2))
                end = int(global_range_match.group(3))
                global_index = IndexRange(start=start, end=end)
            else:
                global_single_match = re.match(r'^\((.+)\)\[(-?\d+)\]$', query)
                if global_single_match:
                    inner_query = global_single_match.group(1)
                    idx = int(global_single_match.group(2))
                    global_index = IndexRange(start=idx)

        steps = self._parse_steps(inner_query)
        return steps, global_index

    def _parse_steps(self, query: str) -> List[QueryStep]:
        """Parse a query into steps."""
        if query.startswith("/"):
            query = query[1:]

        parts = self._split_path(query)
        steps: List[QueryStep] = []
        for part in parts:
            step = self._parse_step(part)
            if step:
                steps.append(step)
        return steps

    def _split_path(self, query: str) -> List[str]:
        """Split path by / while respecting brackets."""
        parts: List[str] = []
        current = ""
        bracket_depth = 0

        for char in query:
            if char == "[":
                bracket_depth += 1
                current += char
            elif char == "]":
                bracket_depth -= 1
                current += char
            elif char == "/" and bracket_depth == 0:
                if current:
                    parts.append(current)
                current = ""
            else:
                current += char

        if current:
            parts.append(current)
        return parts

    def _parse_step(self, step_str: str) -> Optional[QueryStep]:
        """
        Parse a single step like 'Day[2]', 'POI[atom(content =~ "museum")]',
        or 'desc::POI[...]'.
        """
        # Parse optional axis prefix + node type
        axis_match = re.match(r'^(?:(child|desc)::)?([A-Za-z][A-Za-z0-9_]*|\.)', step_str)
        if not axis_match:
            return None

        axis = axis_match.group(1) or "child"
        node_type = axis_match.group(2)
        remaining = step_str[axis_match.end():]

        predicate: Optional[PredicateNode] = None
        predicate_str: Optional[str] = None
        index: Optional[IndexRange] = None

        brackets = self._extract_brackets(remaining)

        for bracket_content in brackets:
            # If contains predicate keywords → parse as predicate via tokenizer
            if any(kw in bracket_content for kw in ['atom(', 'agg_exists(', 'agg_prev(', 'not(']):
                predicate = parse_predicate(bracket_content)
                predicate_str = bracket_content
                continue

            # Try to parse as numeric index
            parsed_index = self._parse_index(bracket_content)
            if parsed_index:
                index = parsed_index

        return QueryStep(
            node_type=node_type,
            predicate=predicate,
            index=index,
            axis=axis,
            predicate_str=predicate_str,
        )

    def _parse_index(self, index_str: str) -> Optional[IndexRange]:
        """Parse an index string like '2', '-1', '1:3', or '-2:'."""
        index_str = index_str.strip()

        if ':' in index_str:
            parts = index_str.split(':')
            if len(parts) == 2:
                start_str = parts[0].strip()
                end_str = parts[1].strip()
                try:
                    start = int(start_str)
                    if end_str == '':
                        return IndexRange(start=start, to_end=True)
                    else:
                        end = int(end_str)
                        return IndexRange(start=start, end=end)
                except ValueError:
                    return None
        else:
            try:
                return IndexRange(start=int(index_str))
            except ValueError:
                return None
        return None

    def _extract_brackets(self, s: str) -> List[str]:
        """Extract bracket contents, handling nested brackets."""
        brackets: List[str] = []
        i = 0
        while i < len(s):
            if s[i] == '[':
                depth = 1
                start = i + 1
                i += 1
                while i < len(s) and depth > 0:
                    if s[i] == '[':
                        depth += 1
                    elif s[i] == ']':
                        depth -= 1
                    i += 1
                brackets.append(s[start:i-1])
            else:
                i += 1
        return brackets


# Singleton instance
_parser_instance: Optional[QueryParser] = None


def get_parser() -> QueryParser:
    """Get singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = QueryParser()
    return _parser_instance
