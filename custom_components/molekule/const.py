from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
)

DOMAIN = "molekule"
MANUFACTURER = "Molekule"

# API settings
API_CLIENT_ID = "1ec4fa3oriciupg94ugoi84kkk"
API_POOL_ID = "us-west-2_KqrEZKC6r"
API_URL = "https://api.molekule.com/users/me/devices/"
API_REGION = "us-west-2" 

# Device capabilities
CAPABILITY_AUTO = "AutoFunctionality"
CAPABILITY_AQI = "AirQualityMonitor"
CAPABILITY_MAX_FAN_SPEED = "MaxFanSpeed"

# Entity keys
KEY_AIR_QUALITY = "air_quality"
KEY_HUMIDITY = "humidity"
KEY_FAN = "fan"
KEY_MODE = "mode"

# Options
CONF_REFRESH_RATE = "conf_refresh_rate"
CONF_REFRESH_RATE_DEFAULT = 300
CONF_SILENT_AUTO = "conf_silent_auto"
