from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTime, PERCENTAGE, CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, CONCENTRATION_PARTS_PER_BILLION, CONCENTRATION_PARTS_PER_MILLION
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN
import logging
from enum import Enum

_LOGGER = logging.getLogger(__name__)

class AirQualityLevel(Enum):
    UNKNOWN = "unknown"
    GOOD = "good"
    MODERATE = "moderate"
    BAD = "bad"
    VERY_BAD = "very_bad"

AQI_MAPPING = {
    "good": AirQualityLevel.GOOD,
    "moderate": AirQualityLevel.MODERATE,
    "bad": AirQualityLevel.BAD,
    "very bad": AirQualityLevel.VERY_BAD,
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    
    sensors = []
    await coordinator.async_config_entry_first_refresh()
    
    if not coordinator.data or "content" not in coordinator.data:
        _LOGGER.error("No data received from the Molekule API")
        return

    for device in coordinator.data["content"]:
        if device.get('subProduct', {}).get('name') == 'Molekule Air Pro':
            device_sensors = [
                MolekuleAirQualitySensor(coordinator, device["serialNumber"], api),
                MolekuleHumiditySensor(coordinator, device["serialNumber"], api),
                MolekulePM25Sensor(coordinator, device["serialNumber"], api),
                MolekulePM10Sensor(coordinator, device["serialNumber"], api),
                MolekuleVOCSensor(coordinator, device["serialNumber"], api),
                MolekuleCO2Sensor(coordinator, device["serialNumber"], api),
                MolekulePECOFilterSensor(coordinator, device["serialNumber"], api),
            ]
            sensors.extend(device_sensors)
        else:
            _LOGGER.info(f"Device {device['name']} ({device['serialNumber']}) is not a Molekule Air Pro. Skipping sensor creation.")
    
    if not sensors:
        _LOGGER.warning("No compatible Molekule devices found. No sensors created.")
    else:
        _LOGGER.info(f"Created {len(sensors)} sensors for Molekule devices.")
    
    async_add_entities(sensors, True)

class MolekuleSensorBase(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api, sensor_type: str):
        super().__init__(coordinator)
        self._device_id = device_id
        self._api = api
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{device_id}_{sensor_type}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = coordinator.data[device_id]["device_info"]

    @property
    def _device(self):
        return next((device for device in self.coordinator.data["content"] if device["serialNumber"] == self._device_id), None)

    @property
    def name(self):
        return f"{self._device['name']} {self._sensor_type.replace('_', ' ').title()}" if self._device else None

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await self.coordinator.async_request_refresh()

    @property
    def available(self):
        """Return if entity is available."""
        return self._device is not None


class MolekuleAirQualitySensor(MolekuleSensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator, device_id, api, "air_quality")
        self._attr_device_class = None  
        self._attr_state_class = None  

    @property
    def native_value(self):
        aqi = self._device.get('aqi', '').lower() if self._device else None
        return AQI_MAPPING.get(aqi, AirQualityLevel.UNKNOWN).value

    @property
    def icon(self):
        return "mdi:air-filter"

    @property
    def extra_state_attributes(self):
        if not self._device:
            return {}
        return {
            "fan_speed": self._device.get("fanspeed"),
            "mode": self._device.get("mode"),
            "online": self._device.get("online"),
            "silent": self._device.get("silent"),
            "burst": self._device.get("burst"),
        }

class MolekulePECOFilterSensor(MolekuleSensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator, device_id, api, "peco_filter")
        self._attr_device_class = None
        self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        if not self._device or 'pecoFilter' not in self._device:
            return None
        try:
            return int(self._device['pecoFilter'])
        except ValueError:
            _LOGGER.error(f"Invalid pecoFilter value: {self._device['pecoFilter']}")
            return None

    @property
    def icon(self):
        if self.native_value is None:
            return "mdi:help-circle-outline"
        if self.native_value <= 10:
            return "mdi:alert-circle-outline"
        elif self.native_value <= 30:
            return "mdi:alert-outline"
        else:
            return "mdi:check-circle-outline"

class MolekuleHumiditySensor(MolekuleSensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator, device_id, api, "Humidity")
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        return self.coordinator.data.get(self._device_id, {}).get('RH')

class MolekulePM25Sensor(MolekuleSensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator, device_id, api, "PM2.5")
        self._attr_device_class = SensorDeviceClass.PM25
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    @property
    def native_value(self):
        return self.coordinator.data.get(self._device_id, {}).get('PM2_5')

class MolekulePM10Sensor(MolekuleSensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator, device_id, api, "PM10")
        self._attr_device_class = SensorDeviceClass.PM10
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    @property
    def native_value(self):
        return self.coordinator.data.get(self._device_id, {}).get('PM10')

class MolekuleVOCSensor(MolekuleSensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator, device_id, api, "VOC")
        self._attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
        self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

    @property
    def native_value(self):
        return self.coordinator.data.get(self._device_id, {}).get('TVOC')

class MolekuleCO2Sensor(MolekuleSensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_id: str, api):
        super().__init__(coordinator, device_id, api, "CO2")
        self._attr_device_class = SensorDeviceClass.CO2
        self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

    @property
    def native_value(self):
        return self.coordinator.data.get(self._device_id, {}).get('CO2')
