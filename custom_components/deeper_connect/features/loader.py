"""Lets every enabled feature add its entities to a platform (static imports: no imports inside the event loop)."""
from __future__ import annotations

from . import access_control, ads_security, app_relocator, dpn, system
from ..const import ALL_FEATURES

MODULES = {"dpn": dpn, "app_relocator": app_relocator, "access_control": access_control, "ads_security": ads_security,
           "system": system}
assert tuple(MODULES) == ALL_FEATURES


def setup_features(platform: str, entry, add) -> None:
    """Call setup_<platform>(entry, add) of each enabled feature that provides one."""
    for key in ALL_FEATURES:
        if key in entry.runtime_data.features and (hook := getattr(MODULES[key], f"setup_{platform}", None)):
            hook(entry, add)
