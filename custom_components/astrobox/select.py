 
"""Support for AstroBox (AstroPrint) preheat preset selectors."""
from __future__ import annotations
import logging
import socket
import aiohttp
import async_timeout

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .sensor import AstroBoxBaseEntity

from .const import DOMAIN
from .coordinator import AstroBoxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Preset configuration dictionary maps
PRESETS = {
    "None / Cooldown": {"tool0": 0, "bed": 0},
    "PLA Preheat (200°C / 60°C)": {"tool0": 200, "bed": 60},
    "PETG Preheat (240°C / 80°C)": {"tool0": 240, "bed": 80},
    "ABS Preheat (250°C / 100°C)": {"tool0": 250, "bed": 100},
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AstroBox selector wheels."""
    coordinator: AstroBoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AstroBoxPreheatSelect(coordinator)])


class AstroBoxPreheatSelect(AstroBoxBaseEntity, SelectEntity):
    """Dropdown configuration matrix selector tool."""
    _attr_icon = "mdi:fire"
    _attr_options = list(PRESETS.keys())

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_preheat_selector"
        self._attr_current_option = "None / Cooldown"

    @property
    def name(self) -> str: return "AstroBox Filament Preheat Profile"

    async def async_select_option(self, option: str) -> None:
        """Run programmatic sequence to adjust multiple target values concurrently."""
        if option not in PRESETS: return
        self._attr_current_option = option
        
        target_set = PRESETS[option]
        headers = {"X-Api-Key": self.coordinator.api_key}
        connector = aiohttp.TCPConnector(family=socket.AF_INET)

        # 1. Dispatch Nozzle Target Value
        url_tool = f"http://{self.coordinator.host}/api/printer/tool"
        payload_tool = {"command": "target", "targets": {"tool0": target_set["tool0"]}}
        
        # 2. Dispatch Bed Target Value
        url_bed = f"http://{self.coordinator.host}/api/printer/bed"
        payload_bed = {"command": "target", "target": target_set["bed"]}

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(10):
                    # Fire both HTTP updates outward
                    await session.post(url_tool, headers=headers, json=payload_tool)
                    await session.post(url_bed, headers=headers, json=payload_bed)
                    
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to cycle target preheat values: %s", err)
