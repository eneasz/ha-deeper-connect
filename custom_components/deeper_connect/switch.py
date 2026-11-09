"""Switches for device settings: ad/SSL/UDP (ads_security) and auto-update/scheduled reboot (system)."""
from __future__ import annotations

from .bases import DeeperSwitch, DeeperSwitchDescription
from .features import ads_security, system
from .features.loader import setup_features

__all__ = ["DeeperSwitch", "DeeperSwitchDescription", "SWITCHES"]

SWITCHES: tuple[DeeperSwitchDescription, ...] = (*ads_security.SWITCHES, *system.SWITCHES)  # every switch, for tests and docs


async def async_setup_entry(hass, entry, add):
    setup_features("switch", entry, add)
