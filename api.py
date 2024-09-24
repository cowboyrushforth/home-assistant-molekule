import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor
from warrant import Cognito
from .const import API_CLIENT_ID, API_POOL_ID, API_URL, API_REGION
import logging
import time

_LOGGER = logging.getLogger(__name__)

def clean_none_values(d):
    """Recursively remove all None values from dictionaries and lists, and convert to empty string"""
    if isinstance(d, dict):
        return {k: clean_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [clean_none_values(v) for v in d if v is not None]
    elif d is None:
        return ""
    else:
        return d

class MolekuleApi:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.cognito = None
        self.session = None
        self.token = None
        self.executor = ThreadPoolExecutor(max_workers=1)

    async def authenticate(self):
        loop = asyncio.get_running_loop()
        self.cognito = await loop.run_in_executor(self.executor, self._create_and_authenticate_cognito)
        self.token = self.cognito.id_token
        self.session = aiohttp.ClientSession()

    def _create_and_authenticate_cognito(self):
        cognito = Cognito(API_POOL_ID, API_CLIENT_ID, username=self.email, user_pool_region=API_REGION)
        cognito.authenticate(password=self.password)
        return cognito

    async def get_devices(self):
        if not self.session:
            await self.authenticate()
        try:
            async with self.session.get(API_URL, headers=self._headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"API request failed with status code {response.status}")
                    return None
                data = await response.json()
                _LOGGER.warn(f"Raw API response: {data}")
                cleaned_data = clean_none_values(data)
                _LOGGER.warn(f"Cleaned API response: {cleaned_data}")
                return cleaned_data
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error communicating with API: {e}")
            return None

    async def get_sensor_data(self, serial: str):
        if not self.session:
            await self.authenticate()
        
        end_time = int(time.time() * 1000)
        start_time = end_time - 3600000  # 1 hour ago
        
        url = f"{API_URL}{serial}/sensordata?aggregation=false&fromDate={start_time}&resolution=5&toDate={end_time}"
        
        try:
            async with self.session.get(url, headers=self._headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"Sensor data API request failed with status code {response.status}")
                    return None
                data = await response.json()
                return self._process_sensor_data(data)
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error fetching sensor data: {e}")
            return None

    def _process_sensor_data(self, data):
        if not data or 'sensorData' not in data:
            return None

        processed_data = {
            "PM2_5": 0,
            "PM10": 0,
            "RH": 0,
            "TVOC": 0,
            "CO2": 0,
        }

        for pollutant in data['sensorData']:
            pollutant_type = pollutant['type']
            if pollutant_type in processed_data:
                for value in reversed(pollutant['sensorDataValue']):
                    if value['v'] != -1:
                        processed_data[pollutant_type] = value['v']
                        break

        return processed_data

    async def set_power_status(self, serial: str, status: bool):
        url = f"{API_URL}{serial}/actions/set-power-status"
        data = {"status": "on" if status else "off"}
        try:
            async with self.session.post(url, headers=self._headers, json=data) as response:
                return response.status == 204
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error setting power status: {e}")
            return False

    async def set_fan_speed(self, serial: str, speed: int):
        url = f"{API_URL}{serial}/actions/set-fan-speed"
        data = {"fanSpeed": speed}
        try:
            async with self.session.post(url, headers=self._headers, json=data) as response:
                return response.status == 204
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error setting fan speed: {e}")
            return False

    async def set_auto_mode(self, serial: str, auto: bool, silent: bool = False):
        if auto:
            url = f"{API_URL}{serial}/actions/enable-smart-mode"
            data = {"silent": str(int(silent))}
            try:
                async with self.session.post(url, headers=self._headers, json=data) as response:
                    return response.status in (200, 204)
            except aiohttp.ClientError as e:
                _LOGGER.error(f"Error setting auto mode: {e}")
                return False
        else:
            return await self.set_fan_speed(serial, 1)  # Set to manual mode with lowest speed

    async def get_aqi(self, serial: str):
        url = f"{API_URL}{serial}/air-quality-index"
        try:
            async with self.session.get(url, headers=self._headers) as response:
                if response.status != 200:
                    _LOGGER.error(f"API request failed with status code {response.status}")
                    return None
                data = await response.json()
                return clean_none_values(data)
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error getting AQI: {e}")
            return None

    @property
    def _headers(self):
        return {
            "Authorization": self.token,
            "x-api-version": "1.0",
            "Content-Type": "application/json",
        }

    async def close(self):
        if self.session:
            await self.session.close()
        self.executor.shutdown(wait=True)