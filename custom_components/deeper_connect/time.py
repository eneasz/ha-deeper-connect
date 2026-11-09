"""Scheduled-reboot time (system)."""
from __future__ import annotations

from .features.system import RebootTime
from .features.loader import setup_features

__all__ = ['RebootTime']


async def async_setup_entry(hass, entry, add):
    setup_features("time", entry, add)
