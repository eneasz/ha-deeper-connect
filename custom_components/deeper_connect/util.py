"""Pure helpers (no Home Assistant imports, so they are unit-testable)."""
from __future__ import annotations

import re
from typing import Any

_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}

CPU_WARN = 90
MEM_WARN = 90
TEMP_WARN = 75
TEMP_CRIT = 85
SESSION_WARN_RATIO = 0.9


def parse_size(value: Any) -> int | None:
    """'89.0 MB' -> bytes."""
    m = re.fullmatch(r"\s*([\d.]+)\s*([KMGT]?B)\s*", str(value), re.I)
    return int(float(m[1]) * _UNITS[m[2].upper()]) if m else None


def parse_uptime(value: Any) -> int | None:
    """'0d2h10m' -> seconds."""
    m = re.fullmatch(r"\s*(?:(\d+)d)?\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*", str(value))
    if not m or not any(m.groups()):
        return None
    d, h, mi = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def last(series: Any) -> float | None:
    return to_float(series[-1]) if isinstance(series, list) and series else None


def avg_last(series: Any, n: int = 3) -> float | None:
    vals = [v for v in (to_float(x) for x in (series or [])[-n:]) if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def tunnel_unhealthy(t: dict) -> bool:
    """Unhealthy = no active node or no exit IP (observed fields: activeNum, activeIp)."""
    return not t.get("activeNum") or not t.get("activeIp")


def compute_health(data: dict) -> tuple[str, list[str]]:
    """Return ('ok'|'warning'|'problem', reasons)."""
    problems: list[str] = []
    warnings: list[str] = []

    wan = (data.get("wifi") or {}).get("wanStatus")
    if wan is not None and wan != "connected":
        problems.append(f"WAN {wan}")
    bad = [c for c, t in (data.get("tunnels") or {}).items() if tunnel_unhealthy(t)]
    if bad:
        problems.append("tunnel down: " + ", ".join(sorted(bad)))

    temp = to_float((data.get("hardware") or {}).get("tempInCelsius"))
    if temp is not None:
        if temp >= TEMP_CRIT:
            problems.append(f"temperature {temp:.0f}°C")
        elif temp >= TEMP_WARN:
            warnings.append(f"temperature {temp:.0f}°C")

    usage = data.get("usage") or {}
    cpu, mem = avg_last(usage.get("cpuUsageData")), avg_last(usage.get("memUsageData"))
    if cpu is not None and cpu >= CPU_WARN:
        warnings.append(f"CPU {cpu:.0f}%")
    if mem is not None and mem >= MEM_WARN:
        warnings.append(f"memory {mem:.0f}%")

    s = data.get("sessions") or {}
    cur, mx = to_float(s.get("currSessionNum")), to_float(s.get("maxSessionNum"))
    if cur is not None and mx and cur / mx >= SESSION_WARN_RATIO:
        warnings.append("session table nearly full")

    sw, latest = data.get("software") or {}, data.get("latest") or {}
    if latest.get("latestVersion") and sw.get("softwareVersion") and latest["latestVersion"] != sw["softwareVersion"]:
        warnings.append("firmware update available")

    if problems:
        return "problem", problems + warnings
    return ("warning", warnings) if warnings else ("ok", [])


# --- app relocation -------------------------------------------------------------------------------
NOT_SET = "ZZ"  # device code: app is not relocated
DIRECT = "LL"  # device code: app uses direct access (no tunnel)
OPT_NOT_SET = "not_set"
OPT_DIRECT = "direct"


def app_title(key: str) -> str:
    """'disneyPlus' -> 'Disney Plus'."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", key)
    return spaced[:1].upper() + spaced[1:]


def code_to_option(code: str | None) -> str:
    if code in (None, "", NOT_SET):
        return OPT_NOT_SET
    return OPT_DIRECT if code == DIRECT else code


def option_to_code(option: str) -> str:
    o = (option or "").strip()
    if o.lower() in (OPT_NOT_SET, "none", "unset", "off"):
        return NOT_SET
    if o.lower() in (OPT_DIRECT, "local"):
        return DIRECT
    return o.upper()


def relocated_apps(apps: dict) -> dict[str, str]:
    """App -> tunnel option for every app that has a tunnel (or direct access) configured."""
    return {k: code_to_option(a.get("tunnel")) for k, a in (apps or {}).items()
            if a.get("tunnel") not in (None, "", NOT_SET)}


def apps_for_tunnel(apps: dict, code: str) -> list[str]:
    return sorted(k for k, a in (apps or {}).items() if a.get("tunnel") == code)


def find_app(apps: dict, name: str) -> str | None:
    """Case-insensitive match on the app key or its display title."""
    n = (name or "").strip().lower().replace(" ", "")
    for k in apps or {}:
        if k.lower() == n or app_title(k).lower().replace(" ", "") == n:
            return k
    return None


def customised_apps(apps: dict) -> list[str]:
    """Apps whose tunnel was changed from the device default (the ones a user evidently cares about)."""
    return sorted(k for k, a in (apps or {}).items()
                  if a.get("tunnel") not in (None, "", NOT_SET) and a.get("tunnel") != a.get("defaultTunnel"))


# --- routing mode -----------------------------------------------------------------------------------
ROUTING_MODES = ("smart", "full", "disabled")


def routing_request(mode: str, tunnel: str | None, dpn: dict | None, tunnels) -> dict:
    """Body for /api/smartRoute/setDpnMode (shapes taken from the device web UI).

    smart -> tunnelCode 'ZZ'; disabled -> ''; full -> a real tunnel (given, else the remembered full-mode tunnel).
    The device does not report its kill-switch state, so this always sends killSwitch=False.
    """
    m = (mode or "").strip().lower()
    if m == "smart":
        return {"dpnMode": "smart", "tunnelCode": NOT_SET, "killSwitch": False}
    if m == "disabled":
        return {"dpnMode": "disabled", "tunnelCode": "", "killSwitch": False}
    if m == "full":
        code = (tunnel or "").strip().upper() or (dpn or {}).get("fullTunnel") or ""
        if code not in tunnels:
            raise ValueError(f"Full mode needs one of your tunnels ({', '.join(sorted(tunnels))}); got '{code or 'none'}'")
        return {"dpnMode": "full", "tunnelCode": code, "killSwitch": False}
    raise ValueError(f"Unknown routing mode '{mode}' (use {', '.join(ROUTING_MODES)})")
