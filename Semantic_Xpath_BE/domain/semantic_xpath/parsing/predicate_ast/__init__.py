"""
Predicate AST package - typed node hierarchy and tokenizer for semantic XPath predicates.
"""

from .nodes import (
    PredicateNode,
    AtomPredicate,
    IdEqPredicate,
    AggPredicate,
    AggExistsPredicate,
    AggPrevPredicate,
    AndPredicate,
    OrPredicate,
    AvgPredicate,
    NotPredicate,
)
from .tokenizer import Token, TokenType, tokenize, TokenizeError

__all__ = [
    # AST nodes
    "PredicateNode",
    "AtomPredicate",
    "IdEqPredicate",
    "AggPredicate",
    "AggExistsPredicate",
    "AggPrevPredicate",
    "AndPredicate",
    "OrPredicate",
    "AvgPredicate",
    "NotPredicate",
    # Tokenizer
    "Token",
    "TokenType",
    "tokenize",
    "TokenizeError",
]
