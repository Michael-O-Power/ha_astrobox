"""Support for AstroBox (AstroPrint) live webcam streaming and snapshots."""
from __future__ import annotations
import logging
import socket
import aiohttp
import async_timeout

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

from .const import DOMAIN
from .coordinator import AstroBoxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the AstroBox webcam stream based on a config entry."""
    coordinator: AstroBoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AstroBoxCameraEntity(coordinator)])


class AstroBoxBaseEntity(CoordinatorEntity[AstroBoxDataUpdateCoordinator]):
    """Base device tracking class shared across entities."""

    @property
    def device_info(self) -> DeviceInfo:
        """Link entity directly to centralized device configuration."""
        mac = self.coordinator.config_entry.data.get("mac")
        connections = {(CONNECTION_NETWORK_MAC, mac)} if mac else set()

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            connections=connections,
            name=f"AstroBox ({self.coordinator.host})",
            manufacturer="AstroPrint",
            model="AstroBox Gateway",
            sw_version="0.21(3)",
        )


class AstroBoxCameraEntity(AstroBoxBaseEntity, Camera):
    """Representation of the AstroBox webcam handling streams and snapshots cleanly."""

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        """Initialize the camera entity."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_live_webcam_feed"

    @property
    def name(self) -> str:
        """Return the name of this camera entity."""
        return "AstroBox Webcam Stream"

    @property
    def is_streaming(self) -> bool:
        """Return True if the web camera is reported as connected by the host."""
        try:
            return bool(self.coordinator.data.get("camera", {}).get("isCameraConnected", False))
        except (KeyError, TypeError):
            return False

    @property
    def mjpeg_source(self) -> str | None:
        """Return the streaming URL source for the live MJPEG engine."""
        return f"http://{self.coordinator.host}/video-stream"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch a single static JPEG frame for low-overhead dashboard previews."""
        url = f"http://{self.coordinator.host}/camera/snapshot?apikey={self.coordinator.api_key}"
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(5):
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.read()
                        _LOGGER.debug("Snapshot fetch failed with status code: %s", response.status)
        except Exception as err:
            _LOGGER.debug("Unable to fetch static camera frame from AstroBox: %s", err)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Expose physical camera traits directly as state properties."""
        try:
            camera_data = self.coordinator.data.get("camera", {})
            return {
                "friendly_hardware_name": camera_data.get("cameraName", "Unknown"),
                "stream_resolution": self.coordinator.data.get("profile", {}).get("camera", {}).get("size", "640x480")
            }
        except (KeyError, TypeError):
            return None
