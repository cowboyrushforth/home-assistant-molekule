from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.util.percentage import (
    int_states_in_range,
    ranged_value_to_percentage,
    percentage_to_ranged_value,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN, CONF_SILENT_AUTO, CAPABILITY_AUTO, CAPABILITY_MAX_FAN_SPEED
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

# Device-specific capabilities
MODEL_CAPABILITIES = {
    "Molekule Air": {
        CAPABILITY_MAX_FAN_SPEED: 3,
        CAPABILITY_AUTO: False,
    },
    "Molekule Air Pro": {
        CAPABILITY_MAX_FAN_SPEED: 6,
        CAPABILITY_AUTO: True,
    }
}

DEFAULT_CAPABILITIES = {
    CAPABILITY_MAX_FAN_SPEED: 3,
    CAPABILITY_AUTO: False,
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    fans = []
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data or "content" not in coordinator.data:
        _LOGGER.error("No data received from the Molekule API")
        return

    for device in coordinator.data["content"]:
        fans.append(MolekuleFan(coordinator, device["serialNumber"], api))
    
    async_add_entities(fans, True)

class MolekuleFan(CoordinatorEntity, FanEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator)
        self._device_id = device_id
        self._api = api
        self._attr_unique_id = f"{device_id}_fan"
        
        # Get model capabilities
        model = self._get_model()
        capabilities = MODEL_CAPABILITIES.get(model, DEFAULT_CAPABILITIES)
        
        # Set up supported features based on model capabilities
        self._attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if capabilities[CAPABILITY_AUTO]:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
            self._attr_preset_modes = ["auto", "manual"]
        
        self._attr_device_info = coordinator.data[device_id]["device_info"]

    def _get_model(self):
        if not self._device:
            return "Unknown"
        return self._device.get('subProduct', {}).get('name', 'Unknown')

    @property
    def _device(self):
        return next((device for device in self.coordinator.data["content"] if device["serialNumber"] == self._device_id), None)

    @property
    def _speed_range(self):
        if not self._device:
            return (1, DEFAULT_CAPABILITIES[CAPABILITY_MAX_FAN_SPEED])
        model = self._get_model()
        capabilities = MODEL_CAPABILITIES.get(model, DEFAULT_CAPABILITIES)
        return (1, capabilities[CAPABILITY_MAX_FAN_SPEED])

    @property
    def name(self):
        return f"{self._device['name']} Fan" if self._device else None

    @property
    def is_on(self):
        return self._device['mode'] != "off" if self._device else None

    @property
    def percentage(self):
        if not self._device or self._device['mode'] == "off":
            return 0
        return ranged_value_to_percentage(self._speed_range, int(self._device['fanspeed']))

    @property
    def preset_mode(self):
        model = self._get_model()
        capabilities = MODEL_CAPABILITIES.get(model, DEFAULT_CAPABILITIES)
        if not capabilities[CAPABILITY_AUTO]:
            return None
        return "auto" if self._device and self._device['mode'] == "smart" else "manual"

    @property
    def speed_count(self):
        return int_states_in_range(self._speed_range)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = round(percentage_to_ranged_value(self._speed_range, percentage))
            await self._api.set_fan_speed(self._device_id, speed)
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        model = self._get_model()
        capabilities = MODEL_CAPABILITIES.get(model, DEFAULT_CAPABILITIES)
        if not capabilities[CAPABILITY_AUTO]:
            _LOGGER.warning(f"Auto mode not supported on {model}")
            return
            
        silent_auto = self.coordinator.config_entry.options.get(CONF_SILENT_AUTO, False)
        await self._api.set_auto_mode(self._device_id, preset_mode == "auto", silent_auto)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None:
        if not self.is_on:
            await self._api.set_power_status(self._device_id, True)
        
        model = self._get_model()
        capabilities = MODEL_CAPABILITIES.get(model, DEFAULT_CAPABILITIES)
        
        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None and capabilities[CAPABILITY_AUTO]:
            await self.async_set_preset_mode(preset_mode)
        else:
            # If no percentage or preset_mode is provided, set to the lowest speed
            await self.async_set_percentage(ranged_value_to_percentage(self._speed_range, self._speed_range[0]))
        
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self._api.set_power_status(self._device_id, False)
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
