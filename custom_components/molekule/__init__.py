from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import CONF_MODEL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, MANUFACTURER, CONF_EMAIL, CONF_PASSWORD
from .api import MolekuleApi

PLATFORMS: list[str] = ["fan", "sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Molekule from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = MolekuleApi(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    
    try:
        await api.authenticate()
    except Exception as err:
        await api.close()
        raise ConfigEntryNotReady from err

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            devices_data = await api.get_devices()
            if devices_data is None:
                raise UpdateFailed("No data received from API")
            
            # Fetch sensor data for each device
            for device in devices_data["content"]:
                serial = device["serialNumber"]
                mac_address = device.get("macAddress")
                sensor_data = await api.get_sensor_data(serial)
                if sensor_data:
                    devices_data[serial] = sensor_data
                
                # Create DeviceInfo for each device
                device_info = DeviceInfo(
                    identifiers={
                        (DOMAIN, serial),
                        (DOMAIN, mac_address)
                    } if mac_address else {(DOMAIN, serial)},
                    name=device["name"],
                    serial_number=serial,
                    manufacturer=MANUFACTURER,
                    model=device.get("subProduct", {}).get("name", "Unknown Model"),
                    sw_version=device.get("firmwareVersion"),
                    connections={("mac", mac_address)} if mac_address else set(),
                )
                devices_data[serial]["device_info"] = device_info
            
            return devices_data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="molekule_devices",
        update_method=async_update_data,
        update_interval=timedelta(seconds=entry.options.get("sync_interval", 300)),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        api = data["api"]
        await api.close()

    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)