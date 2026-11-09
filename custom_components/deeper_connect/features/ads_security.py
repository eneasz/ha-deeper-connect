"""Ads Blocker and Security: YouTube ad blocking, SSL bypass, internal UDP server (request bodies from the web UI)."""
from __future__ import annotations

from ..bases import DeeperSwitch, DeeperSwitchDescription, flag

SWITCHES: tuple[DeeperSwitchDescription, ...] = (
    DeeperSwitchDescription(key="ads_filter", requires=("ads",), is_on_fn=flag("ads", "enable"),
                            set_fn=lambda c, v, d: c.set_youtube_ads(v)),
    DeeperSwitchDescription(key="ssl_bypass", requires=("ssl",), is_on_fn=flag("ssl", "enable"),
                            set_fn=lambda c, v, d: c.set_ssl_bypass(v)),
    DeeperSwitchDescription(key="udp_server", requires=("udp",), is_on_fn=flag("udp", "enabled"),
                            set_fn=lambda c, v, d: c.set_udp_server(v)),
)


def setup_switch(entry, add) -> None:
    add([DeeperSwitch(entry.runtime_data, entry.entry_id, d) for d in SWITCHES])
