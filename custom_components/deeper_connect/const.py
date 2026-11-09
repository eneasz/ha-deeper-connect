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
FEATURE_ACCESS = "access_control"  # per-client routing (smart / direct / blackhole ...) visibility
FEATURE_TUNNELS = "tunnels"  # per-tunnel sub-devices, refresh buttons, map positions
FEATURE_APPS = "app_relocation"  # app relocation sensors, selects and polling
FEATURE_CONTROLS = "controls"  # switches / selects / reboot controls and the settings they poll
ALL_FEATURES = (FEATURE_ACCESS, FEATURE_TUNNELS, FEATURE_APPS, FEATURE_CONTROLS)
# Features that were always on before flags existed stay on for entries that never saved the option.
DEFAULT_FEATURES = (FEATURE_TUNNELS, FEATURE_APPS, FEATURE_CONTROLS)
APPS_EVERY = 5  # app-relocation table refreshes every N polls
SLOW_EVERY = 30  # slow endpoints (versions, settings) refresh every N polls
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
    "routed_traffic": "mdi:routes", "saved_traffic": "mdi:piggy-bank-outline", "blocked_total": "mdi:shield-check",
    "public_ip": "mdi:ip-network", "wan_status": "mdi:wan", "connection_mode": "mdi:router-network",
    "dpn_mode": "mdi:map-marker-path", "lb_mode": "mdi:scale-balance", "tunnel_count": "mdi:tunnel-outline",
    "app_sig": "mdi:fingerprint", "rule_version": "mdi:format-list-checks", "url_sig": "mdi:link-variant",
    "health_problem": "mdi:heart-broken", "tunnel_problem": "mdi:tunnel", "auto_update": "mdi:update",
    "auto_reboot": "mdi:restart-alert", "sharing": "mdi:share-variant",
    "ads_filter": "mdi:youtube", "ssl_bypass": "mdi:lock-open-variant", "udp_server": "mdi:lan-pending",
    "blackholed_clients": "mdi:cancel", "client_route": "mdi:router-network", "client_blackholed": "mdi:cancel",
    "routing_mode": "mdi:map-marker-path", "node_selection": "mdi:scale-balance", "reboot_time": "mdi:clock-outline",
}
TUNNEL_ICONS = {"apps": "mdi:application-export", "location": "mdi:map-marker", "nodes": "mdi:server-network", "ip": "mdi:ip", "problem": "mdi:tunnel", "refresh": "mdi:refresh-circle"}
