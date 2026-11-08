# Deeper Connect for Home Assistant

Monitor a Deeper Connect device and its tunnels (local polling, no cloud).

Install via HACS (custom repository) → add integration → enter the device address
(default `34.34.34.34` in router mode, otherwise its LAN IP) and admin credentials.

**Status: 0.1.0 scaffold.** Login (RSA-encrypted password) and endpoint paths come from the device's
web UI. Response shapes for tunnels/speed are not yet verified against hardware — see TODOs in
`entity.py`, `binary_sensor.py`, `button.py`. HA must be able to route to the device.
Unofficial; not affiliated with Deeper Network.

## Contributing
Issues and PRs welcome — especially captured (password-free) `listTunnels` / `speedometer`
responses from different firmware versions. Licensed under MIT.
