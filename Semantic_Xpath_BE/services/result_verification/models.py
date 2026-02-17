"""Models for result verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VerificationResult:
    """Output of the semantic XPath result verifier."""

    verified_nodes: List[Dict[str, Any]] = field(default_factory=list)
    """Per-node entries that passed verification (subset of input per_node)."""

    rejected_nodes: List[Dict[str, Any]] = field(default_factory=list)
    """Per-node entries that were rejected. Each may include a 'reject_reason' key."""
