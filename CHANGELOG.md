# Changelog

## 0.7.0
- **Access list (new, opt-in):** the device's per-client routing (`smart`, `disabled`, `blackHole`, ...) is now visible.
  A **Blackholed clients** sensor counts clients whose traffic is dropped (attributes: which, and a count per route mode), and every
  client you pick gets a **route mode** sensor and a **blackholed** problem sensor to alert on. Defaults to the clients pinned in the Deeper app.
- **Feature flags:** *Configure → Features* switches whole groups on or off: `access_control`, `tunnels`, `app_relocation`, `controls`.
  A disabled group creates no entities and its endpoints are no longer polled (controls: ad/SSL/UDP/reboot-schedule settings;
  app relocation: the app table). Existing installs keep tunnels, app relocation and controls on; access control is off until enabled.
  Entities (and tunnel sub-devices) of a group you turn off are removed automatically.
- The options flow is now multi-step: general options, then app and client pickers for the features that are enabled.

## 0.6.0
- Controls for device settings: switches (YouTube ad blocking, SSL bypass, UDP server, auto-update, scheduled reboot),
  selects (routing mode, node selection mode), scheduled-reboot time, and a `set_routing_mode` service.
  Routing mode and Reboot are disabled by default; the rest are enabled and were confirmed to be accepted by a real device.
- App relocation dropdowns now appear by default for apps whose tunnel differs from the device default.
- **Changed:** the read-only *Routing mode*, *Node load-balancing*, *Auto-update* and *Scheduled reboot* entities were replaced by
  the controls above (old entities are removed automatically).
- **Fixed:** the ad-filter switch now sends the `type: youtube` the device expects.

## 0.5.0
- App relocation: `Relocated apps` sensors (device and per tunnel), `deeper_connect.set_app_relocation` service,
  and optional per-app relocation dropdowns chosen in the integration options.

## 0.4.1
- Location sensor now reports whether the city lookup is enabled (`city_lookup` attribute).
- Releases are published automatically from the matching changelog section when a `v*` tag is pushed.

## 0.4.0
- Each tunnel is its own sub-device grouping its location, nodes, exit IP, problem flag and refresh button.
- Tunnel *Location* sensor (country, offline); optional city lookup and map pin per tunnel (opt-in, ipinfo.io / geojs.io).

## 0.3.1
- Icons for all entities, brand icon, README install buttons, CI validation (HACS, hassfest, tests).

## 0.3.0
- Full device coverage: health checks, CPU/memory/temperature/uptime, sessions, traffic, blocked requests,
  routing mode, firmware update entity, diagnostics, reauth and options flow.

## 0.2.0
- Real API shapes: per-tunnel sensors, problem flags and refresh buttons.

## 0.1.0
- Initial scaffold.
