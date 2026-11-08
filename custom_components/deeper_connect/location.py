"""Tunnel location helpers (pure)."""
from __future__ import annotations

from .countries import country_name, flag


def tunnel_location(tunnel: dict, geo: dict | None) -> dict:
    """Best-known location of a tunnel's current exit node.

    Offline baseline: the tunnel's own country code. With geo lookup enabled, the exit IP's real
    city/country/coordinates take precedence.
    """
    g = (geo or {}).get(tunnel.get("activeIp")) or {}
    cc = g.get("country_code") or tunnel.get("countryCode")
    country = country_name(cc) or cc
    city = g.get("city")
    label = ", ".join(x for x in (city, country) if x) or tunnel.get("tunnelCode", "unknown")
    return {"label": label, "city": city, "region": g.get("region"), "country_code": cc, "country": country,
            "flag": flag(cc), "latitude": g.get("latitude"), "longitude": g.get("longitude"), "org": g.get("org")}


def tunnel_title(tunnel: dict) -> str:
    """Stable device name from the tunnel's configured country (no network lookups)."""
    code = tunnel.get("tunnelCode", "?")
    name = country_name(tunnel.get("countryCode"))
    if not name:
        return f"Tunnel {code}"
    return f"Tunnel {code} ({' '.join(x for x in (flag(tunnel.get('countryCode')), name) if x)})"
