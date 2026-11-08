# Deeper Connect for Home Assistant

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eneasz&repository=ha-deeper-connect&category=integration)
[![Open your Home Assistant instance and start setting up Deeper Connect.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=deeper_connect)
[![Validate](https://github.com/eneasz/ha-deeper-connect/actions/workflows/validate.yml/badge.svg)](https://github.com/eneasz/ha-deeper-connect/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Local-polling integration for **Deeper Connect** devices (developed against a Deeper Connect Mini,
firmware 2.0.6.h2). No cloud. Monitors the device and its tunnels, and warns you when a tunnel needs maintenance.

## Install (two clicks)
1. Press the **HACS** button above → *Download* → restart Home Assistant.
   (Or: HACS → ⋮ → Custom repositories → add `https://github.com/eneasz/ha-deeper-connect`, category *Integration*.)
2. Press the **Add integration** button above (or *Settings → Devices & services → Add integration → Deeper Connect*).

The buttons use [My Home Assistant](https://my.home-assistant.io/); set your instance URL there once if asked.
Enter the device address (`34.34.34.34` in router mode, otherwise the IP Home Assistant can reach it on)
and the admin username/password. Reauth and polling interval (default 60 s) are handled in the UI.

## What you get
| | |
|---|---|
| **Health** | `Health` (ok / warning / problem, with reasons), `Health problem`, `Tunnel problem`, `WAN connected` |
| **Per tunnel** | Each tunnel is its **own sub-device** (e.g. *Tunnel AU (🇦🇺 Australia)*) grouping: location, active nodes, exit IP, problem flag, **Refresh exit node** button and (optional) a map position |
| **Resources** | CPU, memory, temperature, uptime, sessions (total / tunnel), clients online |
| **Traffic** | live up/down speed, local/client traffic totals, routed and saved traffic, blocked requests |
| **Network** | public IP, WAN status, connection mode, routing (DPN) mode, node load-balancing mode |
| **Firmware** | `update` entity (installed vs latest; installing is done in the Deeper UI) plus signature versions |
| **App relocation** | `Relocated apps` sensors (overall, and per tunnel), a **`deeper_connect.set_app_relocation` service**, and optional per-app dropdowns |
| **Config state** | auto-update, scheduled reboot, bandwidth sharing |
| **Controls** | Reboot button and Ad filter / SSL bypass switches — **disabled by default** (see below) |

A tunnel is *unhealthy* when it has no active node or no exit IP. `Health` goes to *problem* for WAN down,
unhealthy tunnels or temperature ≥ 85 °C, and to *warning* for CPU/memory ≥ 90 % (15-min average), temperature ≥ 75 °C,
a nearly full session table, or a pending firmware update.

## App relocation
The Deeper can send individual apps (Netflix, BBC iPlayer, ...) through a chosen tunnel. This integration exposes it
without cluttering HA with 100+ entities:

- **Sensors:** `Relocated apps` on the device (count + app → tunnel map) and on each tunnel (the apps using it).
- **Service `deeper_connect.set_app_relocation`:** works for *any* app. `tunnel` is a tunnel code (`US`),
  `direct` (direct access, no tunnel) or `not_set` (clear the relocation). `app` is the key or name shown in the Deeper UI.
- **Dropdowns (optional):** *Configure → Apps to control* adds a select entity per app you choose
  (options: `not_set`, `direct`, and your tunnels).

```yaml
# Example: send Netflix through the US tunnel in the evening, back to direct access overnight
automation:
  - alias: Netflix via US in the evening
    trigger: {platform: time, at: "17:00:00"}
    action:
      - service: deeper_connect.set_app_relocation
        data: {app: netflix, tunnel: US}
  - alias: Netflix direct overnight
    trigger: {platform: time, at: "23:30:00"}
    action:
      - service: deeper_connect.set_app_relocation
        data: {app: netflix, tunnel: direct}
```
The device refuses tunnels it can't use (for example one with no active nodes, or a country-locked app);
the service call then fails with the device's reason. The table is polled every 5 polls and refreshed immediately after a change.

## Tunnel locations
Every tunnel has a **Location** sensor showing where its exit node is (flag, country and the device's region code) —
this works offline from the tunnel's country code.

For **city-level location and a map pin** per tunnel, open the integration → *Configure* → enable
*Look up exit-node city and map position online*. This is **off by default** because it sends the tunnel
exit-node IP addresses (not your own, and no credentials) to [ipinfo.io](https://ipinfo.io), falling back to
[geojs.io](https://www.geojs.io). Results are cached until the exit node changes. Accuracy is city-level at best.
The map pins appear as `device_tracker` entities and work with the Map card.

## Verification status
Verified on hardware: login, all read-only sensors, per-tunnel refresh.
App relocation reads are verified; **changing** an app's relocation uses the web UI's own request bodies and is covered by unit tests but not yet confirmed on hardware.
**Unverified (disabled by default):** Reboot button, Ad filter and SSL bypass switches — request bodies are inferred from the
web UI. Reports welcome.

Unofficial; not affiliated with Deeper Network. The device API is undocumented and may change between firmware versions.

## Development
`pip install homeassistant pytest && pytest` — tests run against an anonymised capture in `tests/fixtures`.

## Contributing
Issues and PRs welcome, especially anonymised captures from other models/firmware. MIT licensed.
