"""The AstroBox integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AstroBoxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# List of platforms supported by this integration
PLATFORMS: list[str] = ["sensor", "binary_sensor", "button", "select", "number", "camera"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AstroBox from a config entry."""
    _LOGGER.info("Setting up AstroBox integration entry for %s", entry.data.get("host"))

    # Initialize the data update coordinator with just 'hass' and 'entry'
    coordinator = AstroBoxDataUpdateCoordinator(hass, entry)

    # Fetch initial data so we fail entry configuration early if things are wrong
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator instance so individual platforms can access it
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up the platforms (creates your sensors and binary sensors)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an AstroBox config entry."""
    # Gracefully remove all entities from the configured platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up data tracking to prevent memory leaks
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
    