"""Optional feature groups, named after the sections of the Deeper web UI.

Each group is a FeatureSpec: which endpoints it needs polled and which entity unique ids it owns. The coordinator,
the options flow and the clean-up of switched-off features all read this one registry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..const import (ALL_FEATURES, CONF_FEATURES, DEFAULT_FEATURES, FEATURE_ACCESS, FEATURE_ADS, FEATURE_APPS,
                    FEATURE_DPN, FEATURE_SYSTEM, LEGACY_FEATURES)

_TUNNEL_RE = re.compile(r"^[A-Z0-9]{1,4}_(location|nodes|ip|problem|refresh|tracker|apps)$")  # tunnel codes are upper case
CLIENT_SELECT_RE = re.compile(r"^client_([0-9a-f]{2}:){5}[0-9a-f]{2}_route_select$")
CLIENT_ENTITY_RE = re.compile(r"^client_(?P<mac>([0-9a-f]{2}:){5}[0-9a-f]{2})_(route|route_select|blackholed)$")
_CLIENT_RE = re.compile(r"^client_([0-9a-f]{2}:){5}[0-9a-f]{2}_(route|route_select|blackholed)$")


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    ids: frozenset[str] = frozenset()  # exact unique ids (without the '<entry id>_' prefix) this feature owns
    patterns: tuple[re.Pattern, ...] = ()  # unique-id patterns it owns
    medium: tuple[str, ...] = ()  # coordinator MEDIUM endpoint keys polled only while the feature is on
    slow: tuple[str, ...] = ()  # coordinator SLOW endpoint keys polled only while the feature is on

    def owns(self, rest: str) -> bool:
        return rest in self.ids or any(p.match(rest) for p in self.patterns)


SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(FEATURE_DPN, ids=frozenset({"routing_mode", "node_selection"}), patterns=(_TUNNEL_RE,),
                medium=("dpn", "lb")),
    FeatureSpec(FEATURE_APPS, ids=frozenset({"relocated_apps"}), medium=("apps",)),  # plus app_<key>, see features_owning
    FeatureSpec(FEATURE_ACCESS, ids=frozenset({"blackholed_clients"}), patterns=(_CLIENT_RE,)),
    FeatureSpec(FEATURE_ADS, ids=frozenset({"ads_filter", "ssl_bypass", "udp_server"}), medium=("ads", "ssl", "udp")),
    FeatureSpec(FEATURE_SYSTEM, ids=frozenset({"auto_update", "auto_reboot", "reboot_time", "reboot"}),
                slow=("autoupdate", "autoreboot")),
)
assert tuple(s.key for s in SPECS) == ALL_FEATURES


def enabled_features(options: dict) -> frozenset[str]:
    """Feature groups switched on in the options (entries that never saved the option keep the old behaviour)."""
    chosen = options.get(CONF_FEATURES)
    return frozenset(DEFAULT_FEATURES if chosen is None else (f for f in chosen if f in ALL_FEATURES))


def migrate_features(old: list[str]) -> list[str]:
    """Config entry v1 feature keys -> v2 keys (ordered, unique; unknown keys are dropped)."""
    out: set[str] = set()
    for key in old:
        out.update(LEGACY_FEATURES.get(key, (key,) if key in ALL_FEATURES else ()))
    return [f for f in ALL_FEATURES if f in out]


def features_owning(rest: str) -> set[str]:
    """Which feature groups an entity needs, from its unique id without the leading '<entry id>_'.

    An empty set means the entity is always created. Used to clean up entities of features that were turned off.
    """
    if rest.startswith("app_") and rest != "app_sig":
        return {FEATURE_APPS}
    if (m := _TUNNEL_RE.match(rest)) and m.group(1) == "apps":
        return {FEATURE_DPN, FEATURE_APPS}
    return {s.key for s in SPECS if s.owns(rest)}


def polled(keys, features, kind: str) -> list[str]:
    """The endpoint keys to poll: those no feature owns, plus those owned by an enabled feature (kind: medium|slow)."""
    owned = {k for s in SPECS for k in getattr(s, kind)}
    on = {k for s in SPECS if s.key in features for k in getattr(s, kind)}
    return [k for k in keys if k not in owned or k in on]
