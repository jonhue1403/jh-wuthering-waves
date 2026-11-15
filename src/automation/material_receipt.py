"""Verify material-specific inventory gains from existing OK-WW OCR readers.

This module does NOT capture frames or recognize text: RoutineObserver,
CultivationTask and BoundedRouteTask already use the installed OK Script OCR
engine. Their validated before/after item-detail readings are consumed here
only to distinguish target receipts from unrelated inventory changes.

An observed OCR delta is NOT an independently reviewed live farming permit.
"""
from dataclasses import dataclass
import unicodedata

from src.automation.resource_policy import UncertainReceipt, verify_inventory


MAX_QUANTITY = 9_999_999


def _identity(text):
    if type(text) is not str or not text.strip() or len(text) > 160:
        raise UncertainReceipt("Exact material name required for inventory receipt")
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


@dataclass(frozen=True)
class MaterialReceiptDelta:
    material: str
    before: int
    after: int
    received: int

    @property
    def target_gained(self) -> bool:
        return self.received > 0


def verify_selected_inventory_receipt(before, after, target_materials):
    """Return immutable deltas only after the *selected* material gained.

    The caller must have obtained fresh, same-session item-detail observations
    through existing OCR, game identity and capture guards. This numeric check
    cannot establish capture authenticity or permit another game action.
    """
    if type(before) is not dict or type(after) is not dict:
        raise UncertainReceipt("Material inventory snapshots must be dictionaries")
    if not before or set(before) != set(after):
        raise UncertainReceipt("Before/after inventory must contain identical material names")
    names = tuple(before)
    identities = [_identity(name) for name in names]
    if len(set(identities)) != len(identities):
        raise UncertainReceipt("Ambiguous duplicate material names in OCR inventory")
    if any(type(value) is not int or not 0 <= value <= MAX_QUANTITY
           for value in (*before.values(), *after.values())):
        raise UncertainReceipt("Unusable material inventory quantities")
    if not isinstance(target_materials, (set, frozenset, tuple, list)):
        raise UncertainReceipt("Target material names must be explicitly selected")
    selected = tuple(target_materials)
    if (not selected or any(type(name) is not str or name not in before
                            for name in selected)
            or len(set(selected)) != len(selected)):
        raise UncertainReceipt("Receipt targets do not match observed inventory")
    # Preserve the existing cross-item non-decrease requirement, but tighten
    # positive gain to the chosen pending targets, not some unrelated item.
    verify_inventory(before, after)
    deltas = tuple(
        MaterialReceiptDelta(name, before[name], after[name],
                             after[name] - before[name])
        for name in sorted(selected)
    )
    if not any(delta.target_gained for delta in deltas):
        raise UncertainReceipt(
            "Selected material receipt unverified: no actual target inventory increase (only unrelated items changed)"
        )
    return deltas
