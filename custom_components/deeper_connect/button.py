"""Buttons: tunnel refresh (dpn) and Reboot (system)."""
from __future__ import annotations

from .features.dpn import RefreshTunnel
from .features.system import RebootButton
from .features.loader import setup_features

__all__ = ['RebootButton', 'RefreshTunnel']


async def async_setup_entry(hass, entry, add):
    setup_features("button", entry, add)
