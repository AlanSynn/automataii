"""Canonical mechanism type aliases for Mechanism Foundry application services."""

from __future__ import annotations

MECHANISM_TYPE_ALIASES: dict[str, str] = {
    "fourbar": "four_bar",
    "four_bar": "four_bar",
    "four_bar_linkage": "four_bar",
    "4_bar_linkage": "four_bar",
    "cam": "cam_follower",
    "cam_follower": "cam_follower",
    "gear": "gear_train",
    "gear_train": "gear_train",
    "gear_linkage": "gear_linkage",
    "gear+linkage": "gear_linkage",
    "gear_linkage_train": "gear_linkage",
    "planetary_gear": "gear_train",
    "slider_crank": "slider_crank",
    "slider-crank": "slider_crank",
    "slidercrank": "slider_crank",
}

VISIBLE_FOUNDRY_MECHANISM_TYPES: frozenset[str] = frozenset(
    {"four_bar", "cam_follower", "gear_train", "gear_linkage"}
)


def normalize_mechanism_type_key(mechanism_type: object) -> str:
    """Return a lowercase, whitespace-trimmed mechanism type key."""
    return str(mechanism_type or "").strip().lower()


def canonical_mechanism_type(mechanism_type: object) -> str:
    """Map known Foundry/catalog/runtime aliases to controller configuration keys.

    Unknown values intentionally pass through in normalized form so callers can
    decide whether to skip, display, or handle custom mechanism families.
    """
    key = normalize_mechanism_type_key(mechanism_type)
    return MECHANISM_TYPE_ALIASES.get(key, key)


def is_visible_foundry_mechanism_type(mechanism_type: object) -> bool:
    """Return whether a mechanism should be exposed in the Foundry gallery/selector."""
    return canonical_mechanism_type(mechanism_type) in VISIBLE_FOUNDRY_MECHANISM_TYPES
