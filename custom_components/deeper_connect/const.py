"""Constants for Deeper Connect."""
DOMAIN = "deeper_connect"
DEFAULT_HOST = "34.34.34.34"  # Deeper's default LAN address in router mode
CONF_SCAN_INTERVAL = "scan_interval"
CONF_GEO_LOOKUP = "geo_lookup"
CONF_APPS = "apps"  # app keys that get their own select entity
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
CONF_FEATURES = "features"  # optional feature groups the user enabled
CONF_CLIENTS = "access_clients"  # client MACs that get their own route-mode entities
CONF_CLIENT_CONTROL = "client_control"  # also give those clients a routing select (a write action; off by default)
CONFIG_VERSION = 2  # 1 -> 2: feature groups renamed to follow the Deeper UI sections (see features.migrate_features)
# Feature groups, named after the sections of the Deeper web UI.
FEATURE_DPN = "dpn"  # DPN: tunnels (sub-devices, refresh, map), routing mode, node selection
FEATURE_APPS = "app_relocator"  # App Relocator: relocated-apps sensors, per-app dropdowns, the app table polling
FEATURE_ACCESS = "access_control"  # Access Control: per-client routing (smart / direct / blackhole ...) visibility
FEATURE_ADS = "ads_security"  # Ads Blocker + Security: YouTube ad blocking, SSL bypass, internal UDP server
FEATURE_SYSTEM = "system"  # Settings/Device: auto-update, scheduled reboot, Reboot button
ALL_FEATURES = (FEATURE_DPN, FEATURE_APPS, FEATURE_ACCESS, FEATURE_ADS, FEATURE_SYSTEM)
# Entries that never saved the option keep what was always on before feature flags existed.
DEFAULT_FEATURES = (FEATURE_DPN, FEATURE_APPS, FEATURE_ADS, FEATURE_SYSTEM)
# Feature keys of config entry version 1 -> the groups that replace them.
LEGACY_FEATURES = {
    "tunnels": (FEATURE_DPN,),
    "app_relocation": (FEATURE_APPS,),
    "access_control": (FEATURE_ACCESS,),
    "controls": (FEATURE_DPN, FEATURE_ADS, FEATURE_SYSTEM),  # routing/node selects, ad/SSL/UDP switches, reboot controls
}
# Polling tiers (in seconds, so they do not depend on the polling interval): fast data every poll, settings-like "medium"
# data (and the app table) about every MEDIUM_SECONDS, rarely changing "slow" data (versions, device settings) about every
# SLOW_SECONDS. A tier is never polled less often than the poll itself. Control actions refresh medium + slow at once.
MEDIUM_SECONDS = 300
SLOW_SECONDS = 1800
UNREACHABLE_AFTER = 900  # seconds the device must stay unreachable before a Repairs issue is raised (a reboot takes far less)
STALE_AFTER = 3  # failed polls in a row before an endpoint's last known value is dropped (its entities go unavailable)
PLATFORMS = ["sensor", "binary_sensor", "button", "switch", "update", "device_tracker", "select", "time"]
# Public key shipped in the device's own web UI (used to encrypt the login password).
LOGIN_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxZ9YwQ1CVM4zNHVNPxoD
Sz6uFGEcyHUOFkoA2hnijjJccCNRGnYlQmnCmaKPtCPiJ26ibXcL9BpfputJpE7Q
cJcJx8CN0Pr/MceYQraFS3UG+zNdI6tGzLDGrBoB+5WFSbK6aOdHFJfcoBfdULHb
g2eGp2IJwSPal3lFNwE/oTL3K1z7EiwbDq0LrY7FcwMGmG3EFaGtMxRy/cq3r0xR
M1V7WIu1I6gw463luLs6NFCdrY/fiXoSrXRf6sOTZClXeRhKjA6c0wLIxizgw6ll
4EeffYVBQSKlEjJJR2y7cxxbp1XkC19evxe0DYbnsemogDcSkmDCj75hsgwuzoTM
FwIDAQAB
-----END PUBLIC KEY-----"""

# Entity icons for things Home Assistant has no device-class icon for (keyed by description key).
ICONS = {
    "relocated_apps": "mdi:application-export",
    "health": "mdi:heart-pulse", "cpu": "mdi:cpu-64-bit", "memory": "mdi:memory",
    "sessions": "mdi:swap-horizontal", "tunnel_sessions": "mdi:tunnel", "clients_online": "mdi:lan-connect",
    "local_upload": "mdi:upload-network", "local_download": "mdi:download-network",
    "client_upload": "mdi:upload-network-outline", "client_download": "mdi:download-network-outline",
    "server_upload": "mdi:cloud-upload-outline", "server_download": "mdi:cloud-download-outline",
    "routed_traffic": "mdi:routes", "saved_traffic": "mdi:piggy-bank-outline", "blocked_total": "mdi:shield-check",
    "public_ip": "mdi:ip-network", "wan_status": "mdi:wan", "connection_mode": "mdi:router-network",
    "dpn_mode": "mdi:map-marker-path", "lb_mode": "mdi:scale-balance", "tunnel_count": "mdi:tunnel-outline",
    "app_sig": "mdi:fingerprint", "rule_version": "mdi:format-list-checks", "url_sig": "mdi:link-variant",
    "health_problem": "mdi:heart-broken", "tunnel_problem": "mdi:tunnel", "auto_update": "mdi:update",
    "auto_reboot": "mdi:restart-alert", "sharing": "mdi:share-variant",
    "ads_filter": "mdi:youtube", "ssl_bypass": "mdi:lock-open-variant", "udp_server": "mdi:lan-pending",
    "blackholed_clients": "mdi:cancel", "client_route": "mdi:router-network", "client_route_select": "mdi:router-wireless-settings", "client_blackholed": "mdi:cancel",
    "routing_mode": "mdi:map-marker-path", "node_selection": "mdi:scale-balance", "reboot_time": "mdi:clock-outline",
}
TUNNEL_ICONS = {"apps": "mdi:application-export", "location": "mdi:map-marker", "nodes": "mdi:server-network", "ip": "mdi:ip", "problem": "mdi:tunnel", "refresh": "mdi:refresh-circle"}
