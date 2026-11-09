"""Selects: routing mode and node selection (dpn), per-app relocation (app_relocator)."""
from __future__ import annotations

from .features.access_control import ClientRouteSelect
from .features.app_relocator import AppRelocationSelect
from .features.dpn import NODE_MODES, NodeSelectionSelect, RoutingModeSelect
from .features.loader import setup_features

__all__ = ['AppRelocationSelect', 'ClientRouteSelect', 'NODE_MODES', 'NodeSelectionSelect', 'RoutingModeSelect']


async def async_setup_entry(hass, entry, add):
    setup_features("select", entry, add)
