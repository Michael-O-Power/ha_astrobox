"""Support for AstroBox (AstroPrint) action buttons."""
from __future__ import annotations
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AstroBox action triggers."""
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
        AstroBoxSystemButton(coordinator, "AstroBox Restart Server Service", "core/restart"),
        AstroBoxSystemButton(coordinator, "AstroBox Reboot Host OS", "system/reboot"),
        AstroBoxSystemButton(coordinator, "AstroBox Shutdown Host OS", "system/shutdown"),
    ]

    async_add_entities(entities)


class AstroBoxConnectButton(AstroBoxBaseEntity, ButtonEntity):
    """Spins connection handshakes alive."""
    _attr_icon = "mdi:serial-port"
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_connect"
    @property
    def name(self) -> str: return "AstroBox Connect Printer"

    async def async_press(self) -> None:
        url = f"http://{self.coordinator.host}/api/connection"
        payload = {"command": "connect", "port": "AUTO", "baudrate": "AUTO", "save": True, "autoconnect": True}
        await self._send_post(url, payload)


class AstroBoxDisconnectButton(AstroBoxBaseEntity, ButtonEntity):
    """Severs serial streaming parameters cleanly."""
    _attr_icon = "mdi:serial-port-off"
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_disconnect"
    @property
    def name(self) -> str: return "AstroBox Disconnect Printer"

    async def async_press(self) -> None:
        url = f"http://{self.coordinator.host}/api/connection"
        payload = {"command": "disconnect"}
        await self._send_post(url, payload)


class AstroBoxWakeupNudgeButton(AstroBoxBaseEntity, ButtonEntity):
    """Flushes frozen microcontroller state pipelines."""
    _attr_icon = "mdi:lightning-bolt"
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_nudge"
    @property
    def name(self) -> str: return "AstroBox Wakeup Nudge"

    async def async_press(self) -> None:
        url = f"http://{self.coordinator.host}/api/printer/command"
        payload = {"commands": ["M117 HA Connected", "M105"]}
        await self._send_post(url, payload)


class AstroBoxCooldownButton(AstroBoxBaseEntity, ButtonEntity):
    """Forces thermal boundary profiles back to zero."""
    _attr_icon = "mdi:thermometer-minus"
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, temp_type: str) -> None:
        super().__init__(coordinator)
        self._name = name
        self._type = temp_type
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_cool_{temp_type}"
    @property
    def name(self) -> str: return self._name

    async def async_press(self) -> None:
        if self._type == "tool0":
            url = f"http://{self.coordinator.host}/api/printer/tool"
            payload = {"command": "target", "targets": {"tool0": 0}}
        else:
            url = f"http://{self.coordinator.host}/api/printer/bed"
            payload = {"command": "target", "target": 0}
        await self._send_post(url, payload)


class AstroBoxJobButton(AstroBoxBaseEntity, ButtonEntity):
    """Dispatches execution profile modifications (Pause, Resume, Abort)."""
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, action: str) -> None:
        super().__init__(coordinator)
        self._name = name
        self._action = action
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_btn_job_{action}"
        if action == "pause": self._attr_icon = "mdi:pause"
        elif action == "resume": self._attr_icon = "mdi:play"
        else: self._attr_icon = "mdi:stop"
    @property
    def name(self) -> str: return self._name

    async def async_press(self) -> None:
        url = f"http://{self.coordinator.host}/api/job"
        if self._action == "pause": payload = {"command": "pause", "action": "pause"}
        elif self._action == "resume": payload = {"command": "pause", "action": "resume"}
        else: payload = {"command": "cancel"}
        await self._send_post(url, payload)


class AstroBoxSystemButton(AstroBoxBaseEntity, ButtonEntity):
    """Triggers host Operating System service line reboots directly."""
    _attr_visibility = "advanced" # Hides item from main casual view arrays implicitly
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, endpoint: str) -> None:
        super().__init__(coordinator)
        self._name = name
        self._endpoint = endpoint
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_sys_btn_{endpoint.replace('/', '_')}"
        self._attr_icon = "mdi:server-network"
    @property
    def name(self) -> str: return self._name

    async def async_press(self) -> None:
        url = f"http://{self.coordinator.host}/api/system/commands/{self._endpoint}"
        await self._send_post(url, {})


# Hidden standardized communication method sharing block
extension_method = lambda: None
async def _send_post(self, url: str, payload: dict) -> None:
    headers = {"X-Api-Key": self.coordinator.api_key}
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with async_timeout.timeout(10):
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status in (200, 204): await self.coordinator.async_request_refresh()
    except Exception as err: _LOGGER.error("Action execution failed for %s: %s", url, err)

AstroBoxBaseEntity._send_post = _send_post
