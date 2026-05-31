"""Support for AstroBox (AstroPrint) action buttons."""
from __future__ import annotations
import asyncio
import logging
import socket
import aiohttp
import async_timeout

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .sensor import AstroBoxBaseEntity

from .const import DOMAIN
from .coordinator import AstroBoxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_send_post(coordinator: AstroBoxDataUpdateCoordinator, url: str, payload: dict) -> None:
    """Independent helper function to forward POST actions with clear structural logs."""
    headers = {"X-Api-Key": coordinator.api_key}
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    
    _LOGGER.warning("[AstroBox HTTP Outbound] POST URL: %s | Payload: %s", url, payload)
    
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with async_timeout.timeout(10):
                async with session.post(url, headers=headers, json=payload) as resp:
                    response_text = await resp.text()
                    
                    _LOGGER.warning(
                        "[AstroBox HTTP Inbound] Status: %s | Response Body: %s", 
                        resp.status, response_text
                    )
                    
                    if resp.status in (200, 204): 
                        # Give the Marlin board a brief moment to finish its background serial initialization
                        await asyncio.sleep(3)
                        await coordinator.async_request_refresh()
                    else:
                        _LOGGER.error(
                            "[AstroBox HTTP Inbound] Server rejected operation targeting %s. Status: %s", 
                            url, resp.status
                        )
                        
    except Exception as err: 
        _LOGGER.error("[AstroBox HTTP Error] Exception during network dispatch to %s: %s", url, err, exc_info=True)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AstroBox action triggers based on a config entry."""
    coordinator: AstroBoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        AstroBoxConnectButton(coordinator),
        AstroBoxDisconnectButton(coordinator),
        AstroBoxWakeupNudgeButton(coordinator),
        AstroBoxCooldownButton(coordinator, "AstroBox Nozzle Cooldown", "tool0"),
        AstroBoxCooldownButton(coordinator, "AstroBox Bed Cooldown", "bed"),
        AstroBoxJobButton(coordinator, "AstroBox Pause Print", "pause"),
        AstroBoxJobButton(coordinator, "AstroBox Resume Print", "resume"),
        AstroBoxJobButton(coordinator, "AstroBox Cancel Print", "cancel"),
    ]

    async_add_entities(entities)


class AstroBoxConnectButton(AstroBoxBaseEntity, ButtonEntity):
    """Spins connection handshakes alive by dynamically reading saved system profiles."""
    _attr_icon = "mdi:serial-port"
    
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_connect"
        
    @property
    def name(self) -> str:
        return "AstroBox Connect Printer"

    async def async_press(self) -> None:
        _LOGGER.warning("[AstroBox UI Action] Connect Button clicked.")
        
        if not self.coordinator.data:
            _LOGGER.error("[AstroBox Connect] Execution aborted: Coordinator cache data dictionary is empty.")
            return

        url = f"http://{self.coordinator.host}/api/connection"
        
        settings_data = self.coordinator.data.get("settings_printer") or {}
        serial_settings = settings_data.get("serial") or {}
        
        target_port = serial_settings.get("port")
        target_baud = serial_settings.get("baudrate")
        
        payload = {
            "command": "connect",
            "autoconnect": True
        }
        
        if target_port:
            payload["port"] = str(target_port)
        else:
            _LOGGER.error("[AstroBox Connect] Connection error: 'port' key missing from settings_printer cache data.")
            
        if target_baud:
            try:
                payload["baudrate"] = int(target_baud)
            except (ValueError, TypeError):
                _LOGGER.error("[AstroBox Connect] Connection error: Stored baudrate '%s' is not an integer.", target_baud)
        else:
            _LOGGER.error("[AstroBox Connect] Connection error: 'baudrate' key missing from settings_printer cache data.")

        await async_send_post(self.coordinator, url, payload)


class AstroBoxDisconnectButton(AstroBoxBaseEntity, ButtonEntity):
    """Severs serial streaming parameters cleanly."""
    _attr_icon = "mdi:serial-port-off"
    
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_disconnect"
        
    @property
    def name(self) -> str:
        return "AstroBox Disconnect Printer"

    async def async_press(self) -> None:
        _LOGGER.warning("[AstroBox UI Action] Disconnect Button clicked.")
        url = f"http://{self.coordinator.host}/api/connection"
        payload = {"command": "disconnect"}
        await async_send_post(self.coordinator, url, payload)


class AstroBoxWakeupNudgeButton(AstroBoxBaseEntity, ButtonEntity):
    """Micro-steps axes out and back to force state acknowledgement frames."""
    _attr_icon = "mdi:lightning-bolt"
    
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_nudge"
        
    @property
    def name(self) -> str:
        return "AstroBox Wakeup Nudge"

    async def async_press(self) -> None:
        _LOGGER.warning("[AstroBox UI Action] Wakeup Nudge Button clicked.")
        url = f"http://{self.coordinator.host}/api/printer/command"
        payload = {"commands": ["G91", "G1 X0.1 F200", "G1 X-0.1 F200", "G90"]}
        await async_send_post(self.coordinator, url, payload)


class AstroBoxCooldownButton(AstroBoxBaseEntity, ButtonEntity):
    """Forces thermal boundary profiles back to zero."""
    _attr_icon = "mdi:thermometer-minus"
    
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, temp_type: str) -> None:
        super().__init__(coordinator)
        self._name = name
        self._type = temp_type
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_cool_{temp_type}"
        
    @property
    def name(self) -> str:
        return self._name

    async def async_press(self) -> None:
        _LOGGER.warning("[AstroBox UI Action] Cooldown Button (%s) clicked.", self._type)
        if self._type == "tool0":
            url = f"http://{self.coordinator.host}/api/printer/tool"
            payload = {"command": "target", "targets": {"tool0": 0}}
        else:
            url = f"http://{self.coordinator.host}/api/printer/bed"
            payload = {"command": "target", "target": 0}
        await async_send_post(self.coordinator, url, payload)


class AstroBoxJobButton(AstroBoxBaseEntity, ButtonEntity):
    """Dispatches execution profile modifications (Pause, Resume, Abort)."""
    
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, action: str) -> None:
        super().__init__(coordinator)
        self._name = name
        self._action = action
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_job_{action}"
        if action == "pause":
            self._attr_icon = "mdi:pause"
        elif action == "resume":
            self._attr_icon = "mdi:play"
        else:
            self._attr_icon = "mdi:stop"
            
    @property
    def name(self) -> str:
        return self._name

    async def async_press(self) -> None:
        _LOGGER.warning("[AstroBox UI Action] Job Control Button (%s) clicked.", self._action)
        url = f"http://{self.coordinator.host}/api/job"
        if self._action == "pause":
            payload = {"command": "pause", "action": "pause"}
        elif self._action == "resume":
            payload = {"command": "pause", "action": "resume"}
        else:
            payload = {"command": "cancel"}
        await async_send_post(self.coordinator, url, payload)
