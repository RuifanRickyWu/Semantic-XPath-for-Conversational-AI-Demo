"""
Pytest configuration - ensures the BE root is on sys.path.
"""

import sys
from pathlib import Path

BE_ROOT = Path(__file__).resolve().parents[1]
if str(BE_ROOT) not in sys.path:
    sys.path.insert(0, str(BE_ROOT))
