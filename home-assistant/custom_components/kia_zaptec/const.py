"""Constants for the Kia + Zaptec integration."""

from __future__ import annotations

DOMAIN = "kia_zaptec"

# Config entry keys
CONF_ZAPTEC_USERNAME = "zaptec_username"
CONF_ZAPTEC_PASSWORD = "zaptec_password"
CONF_ZAPTEC_CHARGER_ID = "zaptec_charger_id"
CONF_KIA_USERNAME = "kia_username"
CONF_KIA_PASSWORD = "kia_password"  # In Europe: the Kia Connect *refresh token*
CONF_KIA_PIN = "kia_pin"
CONF_KIA_REGION = "kia_region"
CONF_KIA_VEHICLE_ID = "kia_vehicle_id"

# Options
CONF_BATTERY_CAPACITY = "battery_capacity"
CONF_ZAPTEC_SCAN_INTERVAL = "zaptec_scan_interval"
CONF_KIA_SCAN_INTERVAL = "kia_scan_interval"
CONF_KIA_FORCE_REFRESH = "kia_force_refresh"

DEFAULT_BATTERY_CAPACITY = 61.0  # kWh, Kia EV2 long range (standard range: 42.2)
DEFAULT_ZAPTEC_SCAN_INTERVAL = 15  # seconds
DEFAULT_KIA_SCAN_INTERVAL = 5  # minutes (cached state from Kia cloud)
DEFAULT_KIA_FORCE_REFRESH = 0  # minutes, 0 = never wake the car

# hyundai_kia_connect_api ids
KIA_BRAND = 1
KIA_REGIONS = {1: "Europe", 2: "Canada", 3: "USA", 5: "Australia", 7: "New Zealand"}

# Zaptec API
ZAPTEC_API = "https://api.zaptec.com"

# Zaptec observation (state) ids
ZAPTEC_VOLTAGE_PHASES = (501, 502, 503)
ZAPTEC_CURRENT_PHASES = (507, 508, 509)
ZAPTEC_MAX_CURRENT = 510
ZAPTEC_MIN_CURRENT = 511
ZAPTEC_TOTAL_POWER = 513  # W
ZAPTEC_SESSION_ENERGY = 553  # kWh
ZAPTEC_CHARGE_CURRENT_SET = 708  # A, current the charger offers the car
ZAPTEC_OPERATION_MODE = 710

ZAPTEC_OPERATION_MODES = {
    0: "unknown",
    1: "disconnected",
    2: "connected_requesting",
    3: "connected_charging",
    5: "connected_finished",
}
