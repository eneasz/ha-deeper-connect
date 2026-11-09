"""Optional feature groups (access control, tunnels, app relocation, controls)."""
from __future__ import annotations

import re

from .const import ALL_FEATURES, CONF_FEATURES, DEFAULT_FEATURES


def enabled_features(options: dict) -> frozenset[str]:
    """Feature groups switched on in the options (entries that never saved the option keep the old behaviour)."""
    chosen = options.get(CONF_FEATURES)
    return frozenset(DEFAULT_FEATURES if chosen is None else (f for f in chosen if f in ALL_FEATURES))


_CONTROL_IDS = {"ads_filter", "ssl_bypass", "udp_server", "auto_update", "auto_reboot", "routing_mode",
                "node_selection", "reboot_time", "reboot"}
_TUNNEL_RE = re.compile(r"^[A-Z0-9]{1,4}_(location|nodes|ip|problem|refresh|tracker|apps)$")  # tunnel codes are upper case
_CLIENT_RE = re.compile(r"^client_([0-9a-f]{2}:){5}[0-9a-f]{2}_(route|blackholed)$")


def features_owning(rest: str) -> set[str]:
    """Which feature groups an entity needs, from its unique id without the leading '<entry id>_'.

    An empty set means the entity is always created. Used to clean up entities of features that were turned off.
    """
    if rest in _CONTROL_IDS:
        return {"controls"}
    if rest == "relocated_apps" or (rest.startswith("app_") and rest != "app_sig"):
        return {"app_relocation"}
    if rest == "blackholed_clients" or _CLIENT_RE.match(rest):
        return {"access_control"}
    if m := _TUNNEL_RE.match(rest):
        return {"tunnels", "app_relocation"} if m.group(1) == "apps" else {"tunnels"}
    return set()
