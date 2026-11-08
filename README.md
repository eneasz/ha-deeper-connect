# Deeper Connect for Home Assistant

Monitor a Deeper Connect device and its tunnels (local polling, no cloud).

Install via HACS (custom repository) → add integration → enter the device address
(default `34.34.34.34` in router mode, otherwise its LAN IP) and admin credentials.

**Status: 0.2.0, tested against real hardware (login, tunnel list, network info). The per-tunnel refresh button is verified (returns success and rotates the exit node).
Unofficial; not affiliated with Deeper Network.

## Contributing
Issues and PRs welcome — especially captured (password-free) `listTunnels`
responses from different firmware versions. Licensed under MIT.
