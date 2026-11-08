# Deeper Connect for Home Assistant

Local-polling integration for **Deeper Connect** devices (developed against a Deeper Connect Mini,
firmware 2.0.6.h2). No cloud. Monitors the device and its tunnels, and warns you when a tunnel needs maintenance.

## Install
HACS → Custom repositories → add this repo (category *Integration*) → install → restart HA →
*Settings → Devices & services → Add integration → Deeper Connect*.
Enter the device address (`34.34.34.34` in router mode, otherwise the IP Home Assistant can reach it on)
and the admin username/password. Reauth and polling interval (default 60 s) are handled in the UI.

## What you get
| | |
|---|---|
| **Health** | `Health` (ok / warning / problem, with reasons), `Health problem`, `Tunnel problem`, `WAN connected` |
| **Per tunnel** | active nodes, exit IP, problem flag, **Refresh tunnel** button (picks a new exit node) |
| **Resources** | CPU, memory, temperature, uptime, sessions (total / tunnel), clients online |
| **Traffic** | live up/down speed, local/client traffic totals, routed and saved traffic, blocked requests |
| **Network** | public IP, WAN status, connection mode, routing (DPN) mode, node load-balancing mode |
| **Firmware** | `update` entity (installed vs latest; installing is done in the Deeper UI) plus signature versions |
| **Config state** | auto-update, scheduled reboot, bandwidth sharing |
| **Controls** | Reboot button and Ad filter / SSL bypass switches — **disabled by default** (see below) |

A tunnel is *unhealthy* when it has no active node or no exit IP. `Health` goes to *problem* for WAN down,
unhealthy tunnels or temperature ≥ 85 °C, and to *warning* for CPU/memory ≥ 90 % (15-min average), temperature ≥ 75 °C,
a nearly full session table, or a pending firmware update.

## Verification status
Verified on hardware: login, all read-only sensors, per-tunnel refresh.
**Unverified (disabled by default):** Reboot button, Ad filter and SSL bypass switches — request bodies are inferred from the
web UI. Reports welcome.

Unofficial; not affiliated with Deeper Network. The device API is undocumented and may change between firmware versions.

## Development
`pip install homeassistant pytest && pytest` — tests run against an anonymised capture in `tests/fixtures`.

## Contributing
Issues and PRs welcome, especially anonymised captures from other models/firmware. MIT licensed.
