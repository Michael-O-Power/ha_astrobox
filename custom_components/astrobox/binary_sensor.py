"""Support for AstroBox (AstroPrint) binary monitoring blocks."""
from __future__ import annotations
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up AstroBox binary sensors."""
    coordinator: AstroBoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        AstroBoxConnectivityBinarySensor(coordinator),
        AstroBoxFlagBinarySensor(coordinator, "AstroBox Printer Operational", "operational", "mdi:check-circle-outline"),
        AstroBoxFlagBinarySensor(coordinator, "AstroBox Printing Status", "printing", "mdi:printer-3d-nozzle"),
        AstroBoxFlagBinarySensor(coordinator, "AstroBox Print Paused", "paused", "mdi:pause-circle-outline"),
        AstroBoxFlagBinarySensor(coordinator, "AstroBox Printer Error", "error", device_class=BinarySensorDeviceClass.PROBLEM),
        AstroBoxFlagBinarySensor(coordinator, "AstroBox Printer SD Card Ready", "sdReady", "mdi:sd"),
        AstroBoxWebcamBinarySensor(coordinator),
    ]

    async_add_entities(entities)


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


class AstroBoxConnectivityBinarySensor(AstroBoxBaseEntity, BinarySensorEntity):
    """Tracks general gateway network accessibility."""
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_connectivity"

    @property
    def name(self) -> str: return "AstroBox Connection"

    @property
    def is_on(self) -> bool:
        try:
            text = self.coordinator.data["printer"].get("state", {}).get("text", "")
            if "closed" in text.lower() or "disconnected" in text.lower(): return False
            return bool(self.coordinator.data.get("printer"))
        except (KeyError, TypeError): return False


class AstroBoxFlagBinarySensor(AstroBoxBaseEntity, BinarySensorEntity):
    """Extracts true boolean operational status parameters."""

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, flag_key: str, icon: str | None = None, device_class=None) -> None:
        super().__init__(coordinator)
        self._name = name
        self._key = flag_key
        if icon: self._attr_icon = icon
        if device_class: self._attr_device_class = device_class
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_flag_{flag_key}"

    @property
    def name(self) -> str: return self._name

    @property
    def is_on(self) -> bool:
        try: return bool(self.coordinator.data["printer"]["state"]["flags"].get(self._key, False))
        except (KeyError, TypeError): return False


class AstroBoxWebcamBinarySensor(AstroBoxBaseEntity, BinarySensorEntity):
    """Tracks the physical connection state of the USB webcam."""
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:webcam"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_usb_webcam_status"

    @property
    def name(self) -> str:
        return "AstroBox Webcam Connected"

    @property
    def is_on(self) -> bool:
        """Return True if the USB camera is actively connected."""
        try:
            return bool(self.coordinator.data.get("camera", {}).get("isCameraConnected", False))
        except (KeyError, TypeError):
            return False

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Expose hardware model identity configurations directly."""
        try:
            camera_name = self.coordinator.data.get("camera", {}).get("cameraName")
            if camera_name:
                return {"hardware_model": camera_name}
        except (KeyError, TypeError):
            pass
        return None
