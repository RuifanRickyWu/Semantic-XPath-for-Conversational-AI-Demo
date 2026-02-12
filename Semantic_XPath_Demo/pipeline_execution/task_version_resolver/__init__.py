"""
Global Info Resolver module.
"""

from .task_version_resolver import GlobalInfoResolver, TaskVersionResolver
from .version_selector_model import ResolvedVersion, VersionSelector, CRUDOperation

__all__ = [
    "GlobalInfoResolver",
    "TaskVersionResolver",
    "ResolvedVersion",
    "VersionSelector",
    "CRUDOperation",
]
