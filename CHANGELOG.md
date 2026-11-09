# Changelog

## 0.13.0
- **New: shared traffic sensors.** *Shared traffic upload* and *Shared traffic download* show the data the device reports as `serverTraffic`,
  that is traffic from other Deeper users that went through your device while Bandwidth sharing is on. They are totals, so they stay at 0
  until someone uses your connection, and the device does not report a number of users. The values come from the traffic data the
  integration already fetches, so there are no extra requests to the device. English and Polish names included.

## 0.12.3
- **Fix: a device that is off or not answering is now reported as unreachable.** Requests to a silent device time out, and timeouts were not
  treated as connection failures. Setting up or reconfiguring with a dead address showed "Unexpected error" instead of "Cannot connect", and
  (more importantly) a switched-off device was not counted towards the 15-minute *Deeper device not reachable* Repairs issue. Timeouts
  now count like any other connection failure.
- README: the verification table records the reconfigure checks on a real Home Assistant (form defaults, saving unchanged values, refusing an
  unreachable address).

## 0.12.2
- **Fix: entities of clients and apps you stop watching are removed.** Taking a client off *Configure → Clients to watch* used to leave its
  route-mode and blackholed sensors behind as permanently "unavailable" entities, and taking an app off the app list did the same to its dropdown.
  They are now removed on the next reload. This only happens for a list you have saved; if you never changed a list, nothing is removed.
- README: the verification table now records that the client routing select (disabled, full tunnel, back to smart) and the Reboot button
  were exercised through Home Assistant on a real device.

## 0.12.1
- **Fix: the Reboot button no longer reports an error when the device reboots.** Checked on a real device: it restarts but drops the connection
  instead of answering, so the request timed out and Home Assistant showed a failure although the reboot worked. A timeout or dropped
  connection after the reboot request now counts as success. A failed login, an unreachable device, an HTTP error or an explicit refusal
  from the device still raise.
- README: the verification table now records the hardware checks of client routing (full tunnel, direct, blackhole on one client) and of the reboot request.

## 0.12.0
- **Repairs issue when the device stays unreachable.** After 15 minutes without an answer (a reboot is much shorter) a *Deeper device
  not reachable* issue appears under Settings → Repairs, naming the address and pointing to *Reconfigure*. It clears itself on the
  first successful poll and when the integration is unloaded. A rejected password still uses Home Assistant's own re-authentication
  card and firmware updates stay on the Firmware update entity; neither is duplicated as a repair.
- README: corrected the stale "every 5 polls" wording for the app table (the refresh is time based since 0.8.1).
- English and Polish texts for the new issue.

## 0.11.0
- **Reconfigure** from the integration menu: change host, username or password without removing and re-adding the device. The new address
  must be the same Deeper device (checked by its device id), and a blank password keeps the saved one.
- **Discovery by DHCP hostname** (`dcn-mini`): the device is offered to you automatically. A device you already have that moved to a new
  address gets its address updated instead of a duplicate entry. The saved password is never sent to a discovered address.
- English and Polish texts for the new screens.

## 0.10.0
- **New (opt-in): change a client's routing from HA.** *Configure → Clients to watch → Allow changing client routing* adds a
  `select` per watched client (Smart route, Disabled, Blackhole, or full tunnel through any listed tunnel). Off by default because
  Blackhole cuts a device off the network; switching it off removes the selects. The write re-reads the client's record from the
  device just before sending it back with only the route changed. Verified on hardware by re-sending a client's current route (accepted, nothing else changed); switching to another mode has not been tried yet.
- Polish and English translations for the new option and entity.

## 0.9.0
- **Polish translation** (`pl`) for the setup/options screens, services and every entity name and state. Home Assistant picks it
  automatically when its language is Polish; other languages keep using English.
- Entity names now come from translation keys instead of hard-coded strings, so more languages can be added by contributing a
  `translations/<lang>.json`. English names are unchanged, as are all entity ids and unique ids, so history, dashboards and
  automations are not affected. (Entities already registered keep their current entity ids when the language changes.)
- Per-client and per-app entity names are translated with placeholders (`Client {client} route mode`, `App {app} relocation`).
  Client names still follow a rename in the Deeper app.
- Tests check that every entity has a translation key, that English names match the previous release exactly, and that every
  language file has the same keys and placeholders as English.

## 0.8.1
- **Fixed: polling tiers now follow time, not poll count.** In 0.8.0 settings-like data was refreshed every 5th poll and slow data every
  30th, so with a long polling interval (for example 360 s) settings, the public IP and the routing/node-selection state could lag by
  30 minutes or more. Medium data (settings, public IP, app table) is now refreshed about every 5 minutes and slow data (versions,
  device settings) about every 30 minutes, whatever the polling interval, and never less often than the poll itself. With the default
  60 s interval nothing changes.

## 0.8.0
- **Feature groups now follow the Deeper UI sections.** `tunnels` + the routing/node selects became **`dpn`**, `app_relocation` became
  **`app_relocator`**, the ad/SSL/UDP switches became **`ads_security`**, and auto-update, scheduled reboot and Reboot became **`system`**.
  `access_control` is unchanged. The old `controls` group is split across `dpn`, `ads_security` and `system`.
- **Automatic migration** (config entry version 1 → 2): saved feature choices are converted, entity ids and history are unchanged, and
  entries that never saved a choice keep exactly what they had. If you had `controls` on without `tunnels`, you now also get the `dpn`
  tunnel devices; switch `dpn` off if you don't want them (note: that also removes the routing and node-selection selects).
- The `set_routing_mode` service now needs the `dpn` feature (the routing data is only polled when it is on) and says so.
- Internally, a single registry (`features.SPECS`) declares each feature's endpoints and entities. It replaces the per-id regex and the
  hard-coded control endpoint lists, so a disabled group no longer polls the routing, node-selection, ad/SSL/UDP, auto-update and reboot-schedule endpoints.
- Code is now organised by feature: `features/{dpn,app_relocator,access_control,ads_security,system}.py` each hold their own entities and
  the per-platform setup, and the platform files (`sensor.py`, `switch.py`, ...) only keep the always-on core. No entity changed: all
  entities (class, unique id, name, icon, device, state) were compared against 0.7.0 for every equivalent feature combination.
- **Smarter polling.** Endpoints now run in three tiers: fast data every poll, settings-like data (routing mode, node selection,
  ad/SSL/UDP settings, public IP) and the app table every 5th poll, and versions and device settings every 30th. Control actions
  refresh the slower tiers immediately. A normal poll makes 12 requests instead of 18 (about 26% fewer on average).
- **Failures are handled per endpoint.** One failing endpoint no longer blanks its entities until the next slow refresh: it keeps its last
  value for two polls, is retried every poll, and then the entities that read it become **unavailable** (not "unknown"). A warning is
  logged once when it starts failing and when it turns stale, an info line when it recovers, and the diagnostics download now lists
  failing endpoints (`endpoint_failures`).
- Tests: 23 → 197, now covering the config and options flows, coordinator tiers and failure handling, entity availability, migration,
  and feature clean-up.

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
