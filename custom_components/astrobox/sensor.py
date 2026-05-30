"""Support for AstroBox (AstroPrint) telemetry sensors."""
from __future__ import annotations
from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import AstroBoxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AstroBox sensors based on config entry."""
    coordinator: AstroBoxDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        AstroBoxTemperatureSensor(coordinator, "Extruder Temperature", "tool0"),
        AstroBoxTemperatureSensor(coordinator, "Bed Temperature", "bed"),
        AstroBoxProgressSensor(coordinator),
        AstroBoxStateSensor(coordinator),
        AstroBoxTimeSensor(coordinator, "Print Time Elapsed", "printTime"),
        AstroBoxTimeSensor(coordinator, "Print Time Remaining", "printTimeLeft"),
        AstroBoxTimeSensor(coordinator, "Estimated Total Print Time", "estimatedPrintTime", is_job_root=True),
        AstroBoxETASensor(coordinator),
        AstroBoxTextJobSensor(coordinator, "Current File Name", "name"),
        AstroBoxNumericJobSensor(coordinator, "Current File Size", "size", "MB", SensorDeviceClass.DATA_SIZE, divisor=1024*1024),
        AstroBoxNumericJobSensor(coordinator, "Filament Length Required", "length", "mm", structural_key="filament"),
        AstroBoxNumericJobSensor(coordinator, "Filament Volume Required", "volume", "cm³", structural_key="filament"),
        AstroBoxDiskUsageSensor(coordinator),
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


class AstroBoxTemperatureSensor(AstroBoxBaseEntity, SensorEntity):
    """Tracks nozzle or bed temperatures."""
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, temp_type: str) -> None:
        super().__init__(coordinator)
        self._name = name
        self._type = temp_type
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{temp_type}_temp"

    @property
    def name(self) -> str: return self._name

    @property
    def native_value(self) -> float | None:
        try: return self.coordinator.data["printer"]["temperature"][self._type]["actual"]
        except (KeyError, TypeError): return None

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        try: return {"target_temperature": self.coordinator.data["printer"]["temperature"][self._type]["target"]}
        except (KeyError, TypeError): return None


class AstroBoxProgressSensor(AstroBoxBaseEntity, SensorEntity):
    """Tracks active execution percentage maps."""
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:progress-clock"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_print_progress"

    @property
    def name(self) -> str: return "AstroBox Print Progress"

    @property
    def native_value(self) -> float | None:
        try:
            progress = self.coordinator.data["job"]["progress"]["completion"]
            return round(float(progress), 1) if progress is not None else 0.0
        except (KeyError, TypeError): return None


class AstroBoxStateSensor(AstroBoxBaseEntity, SensorEntity):
    """Tracks generic engine state words."""
    _attr_icon = "mdi:printer-3d"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_printer_state"

    @property
    def name(self) -> str: return "AstroBox Printer State"

    @property
    def native_value(self) -> str:
        try:
            state = self.coordinator.data["job"].get("state")
            return str(state) if state else str(self.coordinator.data["printer"]["state"]["text"])
        except (KeyError, TypeError): return "Unknown"


class AstroBoxTimeSensor(AstroBoxBaseEntity, SensorEntity):
    """Tracks duration attributes (Elapsed, Remaining, Estimations)."""
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, key: str, is_job_root: bool = False) -> None:
        super().__init__(coordinator)
        self._name = name
        self._key = key
        self._is_job_root = is_job_root
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_time_{key}"

    @property
    def name(self) -> str: return self._name

    @property
    def native_value(self) -> int | None:
        try:
            if self._is_job_root:
                return self.coordinator.data["job"].get(self._key)
            return self.coordinator.data["job"]["progress"].get(self._key)
        except (KeyError, TypeError): return None


class AstroBoxETASensor(AstroBoxBaseEntity, SensorEntity):
    """Calculates absolute clock targeted completion timeline."""
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_print_eta"

    @property
    def name(self) -> str: return "AstroBox Print ETA"

    @property
    def native_value(self) -> datetime | None:
        try:
            seconds_left = self.coordinator.data["job"]["progress"].get("printTimeLeft")
            if seconds_left and int(seconds_left) > 0:
                return dt_util.now() + timedelta(seconds=int(seconds_left))
        except (KeyError, TypeError): pass
        return None


class AstroBoxTextJobSensor(AstroBoxBaseEntity, SensorEntity):
    """Tracks textual file identification tokens."""
    _attr_icon = "mdi:file-code-outline"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, key: str) -> None:
        super().__init__(coordinator)
        self._name = name
        self._key = key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_file_{key}"

    @property
    def name(self) -> str: return self._name

    @property
    def native_value(self) -> str | None:
        try: return self.coordinator.data["job"]["file"].get(self._key)
        except (KeyError, TypeError): return None


class AstroBoxNumericJobSensor(AstroBoxBaseEntity, SensorEntity):
    """Tracks file capacity matrices and filament scaling boundaries."""
    
    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator, name: str, key: str, unit: str, device_class=None, structural_key="file", divisor=1) -> None:
        super().__init__(coordinator)
        self._name = name
        self._key = key
        self._structural_key = structural_key
        self._divisor = divisor
        self._attr_native_unit_of_measurement = unit
        if device_class: self._attr_device_class = device_class
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_job_metric_{structural_key}_{key}"

    @property
    def name(self) -> str: return self._name

    @property
    def native_value(self) -> float | None:
        try:
            val = self.coordinator.data["job"][self._structural_key].get(self._key)
            return round(float(val) / self._divisor, 2) if val is not None else None
        except (KeyError, TypeError): return None


class AstroBoxDiskUsageSensor(AstroBoxBaseEntity, SensorEntity):
    """Tracks host memory disk allocations safely."""
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:micro-sd"

    def __init__(self, coordinator: AstroBoxDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_system_disk_usage"

    @property
    def name(self) -> str: return "AstroBox Storage Disk Usage"

    @property
    def native_value(self) -> float | None:
        try:
            # Fallback metrics extraction safety loops
            usage = self.coordinator.data.get("server", {}).get("diskspace", {}).get("usage")
            return float(usage) if usage else 0.0
        except (KeyError, TypeError): return None
