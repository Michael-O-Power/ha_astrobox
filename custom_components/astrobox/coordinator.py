import logging
import asyncio
import socket
import async_timeout
import aiohttp
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class AstroBoxDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching AstroBox data from the local REST API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator using the config entry configuration."""
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
            "job": f"http://{self.host}/api/job"
        }
        
        data = {}
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            for key, url in endpoints.items():
                try:
                    async with async_timeout.timeout(10):
                        async with session.get(url, headers=headers) as response:
                            
                            if response.status == 200:
                                data[key] = await response.json()
                                
                            elif response.status == 409:
                                _LOGGER.debug("AstroBox reports printer is not operational (409) for %s", key)
                                if key == "printer":
                                    data["printer"] = {
                                        "state": {
                                            "text": "Offline", 
                                            "flags": {"printing": False, "operational": False, "ready": False}
                                        },
                                        "temperature": {}
                                    }
                                elif key == "job":
                                    data["job"] = {
                                        "state": "Offline",
                                        "progress": {"completion": None}
                                    }
                            else:
                                raise UpdateFailed(f"Unexpected API status: {response.status}")
                                
                except (aiohttp.ClientConnectorError, asyncio.TimeoutError) as err:
                    raise UpdateFailed(f"Cannot reach AstroBox server: {err}")
                except Exception as err:
                    raise UpdateFailed(f"Unexpected error communicating with AstroBox: {err}")
                    
        return data
