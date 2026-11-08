# Changelog

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
