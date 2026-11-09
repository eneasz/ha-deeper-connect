"""Map position of each tunnel's exit node (dpn, only when geo lookup is enabled)."""
from __future__ import annotations

from .features.dpn import TunnelTracker
from .features.loader import setup_features

__all__ = ['TunnelTracker']


async def async_setup_entry(hass, entry, add):
    setup_features("device_tracker", entry, add)
