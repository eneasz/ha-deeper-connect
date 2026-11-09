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

## Changing the address or password, and discovery
- **Reconfigure:** on the integration entry use the three-dot menu → *Reconfigure* to change host, username or password (leave the password
  empty to keep it). The address must belong to the same Deeper device; otherwise it is refused, so an entry can't end up pointing at another box.
- **Discovery:** Home Assistant offers the device automatically when it announces itself on the network with the DHCP hostname `dcn-mini`,
  and asks for the admin login. If it is a device you already added whose address changed, the existing entry's address is updated
  instead of creating a duplicate. Your saved password is never sent to a newly discovered address; you type it in.

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
By default this is read-only. Entity ids depend on your device name.

**Changing a client's routing from HA (opt-in).** Turn on *Configure → Clients to watch → Allow changing client routing* and each
watched client also gets a `select` **Client X routing** with the options Smart route, Disabled, Blackhole (cut off), and one
`full_<TUNNEL>` entry per tunnel (full tunnel through that exit). Choosing Blackhole stops that device's traffic, so it is off unless
you ask for it, and turning it off again removes the selects. The write re-reads the client's current record from the device and sends
it back with only the route changed. Verified on hardware only for re-sending a client's current route; actually switching modes (full tunnel, blackhole) is not yet tried (see Verification status).

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
the service call then fails with the device's reason. The table is refreshed about every 5 minutes and immediately after a change.

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

**Repairs:** if the whole device stays unreachable for 15 minutes (a reboot is much shorter), Home Assistant shows a *Deeper device not
reachable* issue under Settings → Repairs with the address it is trying and a pointer to *Reconfigure*; it disappears by itself when
the device answers again. A wrong password uses Home Assistant's own re-authentication card, and firmware updates appear on the Firmware
update entity, so neither is duplicated as a repair.

## Verification status
What has actually been exercised, as of v0.12.0, on a Deeper Connect Mini (firmware 2.0.6.h2) and a real Home Assistant. "No-op re-send" means the
current value was sent back unchanged: it proves the request shape is accepted, not that a different value behaves as hoped.

| Area | Proven on hardware | Only tested against the anonymised fixture / stubs |
|---|---|---|
| Login, all read-only sensors, tunnels, health | Yes | |
| Tunnel refresh button | Yes | |
| App relocation (set to a tunnel, clear) | Yes | Setting `direct` (UI's `LL` code) |
| Routing mode, node selection, reboot schedule, auto-update, UDP server | Accepted as no-op re-send | Switching to a *different* routing mode |
| Ad filter and SSL bypass switches | Accepted as no-op re-send | Real on/off change |
| Client routing select (opt-in) | The device accepted full tunnel, direct and blackhole on one client (each re-read showed only that client's route changed, 17 others untouched) and the switch back to smart. Tested through the API client, not yet through the HA select entity | Real traffic behaviour of each mode |
| Reboot request (`POST /api/admin/reboot`, off by default as a button) | The device restarted (about a minute offline; all 81 entities returned, none renamed). The request timed out with no response body because the device dropped the connection while restarting. **Known gap:** the Reboot button does not yet treat that as success, so pressing it may show an error in HA even though the device reboots | The HA button entity itself |
| Reconfigure flow | Form opens in HA with the current host and username | Saving a change, and the wrong-device refusal |
| DHCP discovery (`dcn-mini`) | Matcher accepted by hassfest | Discovery of a new or moved device |
| Repairs: device unreachable | | Yes (timer, once-only raise, cleanup on recovery) |
| Polling tiers and per-endpoint staleness | 12 requests per steady poll vs 18 before; all sections populated, read-only | Failure and recovery behaviour |
| Config-entry migration from 0.7.x | Yes (entities decreased as expected, then restored) | |
| Translations (English, Polish) | | Key and placeholder parity tests only |

Not built, on purpose: earnings (the device returns 403, and there is no credits endpoint) and a monthly sharing-traffic sensor (the device reports
a `monthly` number with no known unit, and a guessed unit would show wrong data). Reports and anonymised captures are welcome.

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
