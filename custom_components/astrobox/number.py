 
"""Support for AstroBox (AstroPrint) number inputs."""
import logging
import socket
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AstroBoxDataUpdateCoordinator
from .sensor import AstroBoxBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AstroBox numbers based on a config entry."""
    coordinator: AstroBoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        AstroBoxTargetTempNumber(coordinator, "Nozzle Target Temperature", "tool0", 0, 300),
        AstroBoxTargetTempNumber(coordinator, "Bed Target Temperature", "bed", 0, 120),
    ])


class AstroBoxTargetTempNumber(AstroBoxBaseEntity, NumberEntity):
    """Representation of an AstroBox target temperature control."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, temp_type: str, min_val: float, max_val: float) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._name = name
        self._type = temp_type
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = 1.0
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_target_{temp_type}_temp"

    @property
    def name(self) -> str:
        return self._name

    @property
    def native_value(self) -> float | None:
        """Return the current target temperature set on the machine."""
        try:
            return float(self.coordinator.data["printer"]["temperature"][self._type]["target"])
        except (KeyError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Send the target temperature change request to AstroBox."""
        headers = {"X-Api-Key": self.coordinator.api_key}
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        
        if self._type == "tool0":
            url = f"http://{self.coordinator.host}/api/printer/tool"
            payload = {"command": "target", "targets": {"tool0": int(value)}}
        else:
            url = f"http://{self.coordinator.host}/api/printer/bed"
            payload = {"command": "target", "target": int(value)}

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(10):
                    async with session.post(url, headers=headers, json=payload) as response:
                        if response.status in (200, 204):
                            await self.coordinator.async_request_refresh()
                        else:
                            _LOGGER.warning("AstroBox rejected temp change request with status: %s", response.status)
        except Exception as err:
            _LOGGER.error("Failed to update target temperature: %s", err)
