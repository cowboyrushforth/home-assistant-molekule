from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.util.percentage import (
    int_states_in_range,
    ranged_value_to_percentage,
    percentage_to_ranged_value,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN
import logging


_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 6) 

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
        self._attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
        self._attr_preset_modes = ["auto", "manual"]
        self._attr_device_info = coordinator.data[device_id]["device_info"]

    @property
    def _device(self):
        return next((device for device in self.coordinator.data["content"] if device["serialNumber"] == self._device_id), None)

    @property
    def name(self):
        return f"{self._device['name']} Fan" if self._device else None

    @property
    def is_on(self):
        return self._device['fanspeed'] != "0" if self._device else None

    @property
    def percentage(self):
        if not self._device or self._device['fanspeed'] == "0":
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, int(self._device['fanspeed']))

    @property
    def preset_mode(self):
        return "auto" if self._device and self._device['mode'] == "smart" else "manual"

    @property
    def speed_count(self):
        return int_states_in_range(SPEED_RANGE)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = round(percentage_to_ranged_value(SPEED_RANGE, percentage))
            await self._api.set_fan_speed(self._device_id, speed)
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        silent_auto = self.coordinator.config_entry.options.get('silent_auto', False)
        await self._api.set_auto_mode(self._device_id, preset_mode == "auto", silent_auto)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None:
        if not self.is_on:
            await self._api.set_power_status(self._device_id, True)
        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        else:
            # If no percentage or preset_mode is provided, set to the lowest speed
            await self.async_set_percentage(ranged_value_to_percentage(SPEED_RANGE, SPEED_RANGE[0]))
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self._api.set_power_status(self._device_id, False)
        await self.coordinator.async_request_refresh()