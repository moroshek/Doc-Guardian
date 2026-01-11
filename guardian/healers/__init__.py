"""
Doc Guardian Healers

Collection of universal healers for maintaining documentation quality.
"""

from .manage_collapsed import ManageCollapsedHealer
from .fix_broken_links import FixBrokenLinksHealer
from .detect_staleness import DetectStalenessHealer
from .resolve_duplicates import ResolveDuplicatesHealer
from .balance_references import BalanceReferencesHealer
from .sync_canonical import SyncCanonicalHealer
from .enforce_disclosure import EnforceDisclosureHealer

__all__ = [
    'ManageCollapsedHealer',
    'FixBrokenLinksHealer',
    'DetectStalenessHealer',
    'ResolveDuplicatesHealer',
    'BalanceReferencesHealer',
    'SyncCanonicalHealer',
    'EnforceDisclosureHealer',
]
