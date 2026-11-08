"""Constants for Deeper Connect."""
DOMAIN = "deeper_connect"
DEFAULT_HOST = "34.34.34.34"  # Deeper's default LAN address in router mode
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
SLOW_EVERY = 30  # slow endpoints (versions, settings) refresh every N polls
PLATFORMS = ["sensor", "binary_sensor", "button", "switch", "update"]
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
    "ads_filter": "mdi:advertisements-off", "ssl_bypass": "mdi:lock-open-variant",
}
TUNNEL_ICONS = {"nodes": "mdi:server-network", "ip": "mdi:ip", "problem": "mdi:tunnel", "refresh": "mdi:refresh-circle"}
