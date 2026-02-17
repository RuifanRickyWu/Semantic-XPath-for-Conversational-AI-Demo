"""XML tree utilities for stores. Avoids circular imports with domain."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple


def find_by_path_segments(
    root: ET.Element,
    path_segments: List[Tuple[str, int]],
) -> Optional[ET.Element]:
    """Walk tree by (tag, index) segments. Index is 1-based among same-tag siblings."""
    current: Optional[ET.Element] = root
    for tag, idx in path_segments:
        if current is None:
            return None
        same_tag = [c for c in current if c.tag == tag]
        if idx < 1 or idx > len(same_tag):
            return None
        current = same_tag[idx - 1]
    return current
