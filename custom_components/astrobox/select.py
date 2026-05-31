"""Support for AstroBox dynamic preheat selectors."""
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AstroBox selector options."""
    coordinator: AstroBoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AstroBoxPreheatSelect(coordinator)])


class AstroBoxPreheatSelect(AstroBoxBaseEntity, SelectEntity):
    """Dropdown configuration matrix powered by native profile endpoints."""
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_dynamic_preheat_selector"
        self._current_option = "Cooldown"

    @property
    def name(self) -> str:
        return "AstroBox Dynamic Preheat Profile"

    @property
    def options(self) -> list[str]:
        """Dynamically compile selection lists from actual profile dictionaries."""
        options_list = ["Cooldown"]
        presets = self.coordinator.data.get("profile", {}).get("temp_presets", {})
        for preset_id, preset_info in presets.items():
            if "name" in preset_info:
                options_list.append(str(preset_info["name"]))
        return options_list

    @property
    def current_option(self) -> str:
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Locate values for selected profile strings and fire hotend updates."""
        self._current_option = option
        target_nozzle = 0
        target_bed = 0

        # Look up match targets if the user didn't pick "Cooldown"
        if option != "Cooldown":
            presets = self.coordinator.data.get("profile", {}).get("temp_presets", {})
            for preset_id, preset_info in presets.items():
                if preset_info.get("name") == option:
                    target_nozzle = preset_info.get("nozzle_temp", 0)
                    target_bed = preset_info.get("bed_temp", 0)
                    break

        headers = {"X-Api-Key": self.coordinator.api_key}
        connector = aiohttp.TCPConnector(family=socket.AF_INET)

        url_tool = f"http://{self.coordinator.host}/api/printer/tool"
        payload_tool = {"command": "target", "targets": {"tool0": int(target_nozzle)}}
        
        url_bed = f"http://{self.coordinator.host}/api/printer/bed"
        payload_bed = {"command": "target", "target": int(target_bed)}

        _LOGGER.warning("[AstroBox Preheat] Setting targets -> Nozzle: %s°C, Bed: %s°C", target_nozzle, target_bed)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(10):
                    await session.post(url_tool, headers=headers, json=payload_tool)
                    await session.post(url_bed, headers=headers, json=payload_bed)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to cycle dynamic preheat targets: %s", err)
