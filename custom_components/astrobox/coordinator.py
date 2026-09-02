import logging
import asyncio
import socket
import async_timeout
import aiohttp
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class AstroBoxDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching AstroBox data concurrently across all verified endpoints."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self.host = entry.data["host"]
        self.api_key = entry.data["api_key"]
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from AstroBox endpoints concurrently over IPv4."""
        headers = {"X-Api-Key": self.api_key}
        endpoints = {
            "printer": f"http://{self.host}/api/printer",
            "job": f"http://{self.host}/api/job",
            "settings_printer": f"http://{self.host}/api/settings/printer",
            "storage": f"http://{self.host}/api/settings/software/storage",
            "profile": f"http://{self.host}/api/printer-profile",
            "camera": f"http://{self.host}/api/camera/connected"
        }
        
        data = {}
        success_count = 0
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        
        async def fetch_endpoint(key: str, url: str) -> tuple[str, dict]:
            nonlocal success_count
            try:
                async with async_timeout.timeout(5):
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            success_count += 1
                            return key, await response.json()
                            
                        elif response.status == 409:
                            success_count += 1
                            if key == "printer":
                                return key, {
                                    "state": {"text": "Offline", "flags": {"printing": False, "operational": False, "ready": False}},
                                    "temperature": {}
                                }
                            if key == "job":
                                return key, {"state": "Offline", "progress": {"completion": None}}
                            if key == "camera":
                                return key, {"isCameraConnected": False, "cameraName": "None"}
                            return key, {}
                        elif response.status in (401, 403):
                            # Raise this immediately so it isn't caught by the generic Exception handler
                            raise ConfigEntryAuthFailed("AstroBox API key rejected")
                        else:
                            return key, {}
                            
            except ConfigEntryAuthFailed:
                # Bubble this up to Home Assistant to trigger the Reauth flow
                raise
                
            except Exception as err:
                _LOGGER.debug("Optional AstroBox endpoint %s temporarily unavailable: %s", key, err)
                if key == "printer":
                    return key, {
                        "state": {"text": "Offline", "flags": {"printing": False, "operational": False, "ready": False}},
                        "temperature": {}
                    }
                if key == "job":
                    return key, {"state": "Offline", "progress": {"completion": None}}
                if key == "camera":
                    return key, {"isCameraConnected": False, "cameraName": "None"}
                return key, {}

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [fetch_endpoint(key, url) for key, url in endpoints.items()]
            results = await asyncio.gather(*tasks)
            for key, res in results:
                data[key] = res
                
        if success_count == 0:
            raise UpdateFailed("Unable to communicate with the AstroBox server host.")
                        
        return data
