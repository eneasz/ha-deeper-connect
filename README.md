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
| **Network** | public IP, WAN status, connection mode |
| **Firmware** | `update` entity (installed vs latest; installing is done in the Deeper UI) plus signature versions |
| **App relocation** | `Relocated apps` sensors (overall, and per tunnel), a **`deeper_connect.set_app_relocation` service**, and optional per-app dropdowns |
| **Access list** | opt-in: `Blackholed clients` count plus a route-mode and a *blackholed* problem sensor per chosen client |
| **Settings (read-only)** | bandwidth sharing |
| **Controls** | see *Controls* below |

A tunnel is *unhealthy* when it has no active node or no exit IP. `Health` goes to *problem* for WAN down,
unhealthy tunnels or temperature ≥ 85 °C, and to *warning* for CPU/memory ≥ 90 % (15-min average), temperature ≥ 75 °C,
a nearly full session table, or a pending firmware update.

## Features (keep the entity count down)
Everything beyond the core health/resources/traffic sensors lives in a feature group you switch on under
*Configure → Features*. The groups are named after the sections of the Deeper web UI. A disabled group creates no
entities and its API calls are not made.

| Feature (Deeper UI section) | Adds | Default |
|---|---|---|
| `dpn` (DPN) | per-tunnel sub-devices (location, nodes, exit IP, problem, refresh button, map), routing mode and node selection | on |
| `app_relocator` (App Relocator) | relocated-apps sensors, app dropdowns, the app table polling | on |
| `access_control` (Access Control) | Blackholed-clients sensor, per-client route mode + blackholed sensors | **off** |
| `ads_security` (Ads Blocker, Security) | YouTube ad blocking, SSL bypass and UDP server switches | on |
| `system` (Settings, Device) | auto-update and scheduled-reboot switches, reboot time, Reboot button | on |

Turning a group off removes its entities from the registry. Tunnel health still feeds `Health` and `Tunnel problem` either way.
Upgrading from 0.7.x: your saved choices are converted automatically (the old `controls` group became `dpn`, `ads_security` and `system`);
entity ids and history are unchanged.

## Access list
The Deeper routes every client in one of several modes: `smart`, `disabled` (direct), a full-tunnel region, or `blackHole`
(all its traffic is dropped). A device ending up blackholed looks exactly like a dead network from the client's side, so this
makes it visible to HA:

- `sensor` **Blackholed clients**: how many clients are blackholed (online or not); attributes list them and count clients per mode.
- Per chosen client (*Configure → Clients to watch*, default: the clients pinned in the Deeper app):
  `sensor` **Client X route mode** and `binary_sensor` **Client X blackholed** (problem class).

```yaml
automation:
  - alias: Deeper blackholed a client
    trigger:
      - platform: numeric_state
        entity_id: sensor.deeper_connect_blackholed_clients
        above: 0
    action:
      - service: notify.notify
        data: {message: "Blackholed on the Deeper: {{ state_attr('sensor.deeper_connect_blackholed_clients', 'clients') | join(', ') }}"}
```
This is read-only: changing a client's route mode is done in the Deeper app. Entity ids depend on your device name.

## Controls
These belong to the `dpn`, `ads_security` and `system` features (see above).

| Entity | What it does | Enabled by default |
|---|---|---|
| `switch` YouTube ad blocking, SSL bypass, UDP server, Auto-update | toggle those device settings | yes |
| `select` Routing mode (smart / full / disabled) | switch the device routing mode | **no** (see note) |
| `select` Node selection mode (regular / random / domain-aware / round-robin) | how connections spread over a tunnel's nodes | yes |
| `switch` Scheduled reboot + `time` Scheduled reboot time | the device's automatic reboot | yes |
| `select` per app | app relocation (see below) | yes, for apps you customised |
| `button` Reboot, Refresh exit node | reboot / pick a new exit node | Reboot: **no** |
| services `set_routing_mode`, `set_app_relocation` | the same from automations | n/a |

Routing mode and Reboot are off by default (enable them under the device's entities).
**Routing mode note:** the device does not report its kill-switch state, so changing the mode from HA sends *kill switch = off*.
Full mode uses the device's remembered full-mode tunnel; if that isn't one of your tunnels use the `set_routing_mode` service with `tunnel`.
Bandwidth sharing and WAN access are deliberately **read-only**: opening your connection to other people's traffic or to the
internet should be a conscious action in the Deeper app.

## App relocation
The Deeper can send individual apps (Netflix, BBC iPlayer, ...) through a chosen tunnel. This integration exposes it
without cluttering HA with 100+ entities:

- **Sensors:** `Relocated apps` on the device (count + app → tunnel map) and on each tunnel (the apps using it).
- **Service `deeper_connect.set_app_relocation`:** works for *any* app. `tunnel` is a tunnel code (`US`),
  `direct` (direct access, no tunnel) or `not_set` (clear the relocation). `app` is the key or name shown in the Deeper UI.
- **Dropdowns:** a select entity per app (options: `not_set`, `direct`, and your tunnels). Out of the box you get the apps whose
  tunnel differs from the device default; change the list under *Configure → Apps to control*.

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
*Look up exit-node city and map position online* (needs the `dpn` feature). This is **off by default** because it sends the tunnel
exit-node IP addresses (not your own, and no credentials) to [ipinfo.io](https://ipinfo.io), falling back to
[geojs.io](https://www.geojs.io). Results are cached until the exit node changes. Accuracy is city-level at best.
The map pins appear as `device_tracker` entities and work with the Map card.

## Polling and availability
Everything is read from the device every 60 s (configurable): live data (health, resources, traffic, clients, tunnels) each poll;
settings, public IP and the app table about every 5 minutes; firmware and device settings about every 30 minutes (never less often than the poll itself). Changing something from HA refreshes the slower
data straight away. If one endpoint fails, its entities keep the last value for two polls, then show **unavailable** until it works
again (the rest keep updating); the log has one warning when that starts and an info line when it recovers, and the diagnostics
download lists failing endpoints.

## Verification status
Verified on hardware: login, all read-only sensors, per-tunnel refresh.
The settings controls use the web UI's own request bodies; the device accepted each of them (ad blocking, SSL bypass, UDP, auto-update, node selection, reboot schedule)
when the current value was re-sent. Changing routing mode and rebooting have not been exercised on hardware.
App relocation is verified on hardware: setting an app to a tunnel and clearing it again. Setting `direct` uses the same call and the UI's `LL` code but has not been tried on hardware.
**Unverified (disabled by default):** Reboot button, Ad filter and SSL bypass switches — request bodies are inferred from the
web UI. Reports welcome.

Unofficial; not affiliated with Deeper Network. The device API is undocumented and may change between firmware versions.

## Development
Layout: `sensor.py`, `binary_sensor.py`, ... hold only the always-on core. Each optional feature is one module in
`custom_components/deeper_connect/features/` (`dpn`, `app_relocator`, `access_control`, `ads_security`, `system`) with its entities and a
`setup_<platform>` hook; `features/__init__.py` is the registry (which endpoints and entity ids each feature owns) and
`features/loader.py` wires the enabled ones into the platforms. To add an entity: put it in its feature module, add its unique id to the
spec's `ids`/`patterns`, and the ownership tests will tell you if you forgot.

Translations: entity names are translation keys (never hard-coded), defined in `strings.json` and `translations/en.json` (kept identical) and
translated in `translations/<lang>.json` (English and Polish ship today). To add a language, copy `en.json`, translate the values and keep the
`{app}` / `{client}` placeholders; the tests fail if a language has different keys or placeholders from English.

`pip install homeassistant pytest && pytest` — tests run against an anonymised capture in `tests/fixtures`.

## Contributing
Issues and PRs welcome, especially anonymised captures from other models/firmware. MIT licensed.
