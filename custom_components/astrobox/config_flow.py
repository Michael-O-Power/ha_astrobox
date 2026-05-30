"""Config flow for AstroBox."""
from __future__ import annotations

import logging
import re
import socket
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, TESTED_API_VERSION, TESTED_SERVER_VERSION

_LOGGER = logging.getLogger(__name__)

API_KEY_REGEX = re.compile(r'var UI_API_KEY\s*=\s*["\']([^"\']+)["\']')
SERVER_VERSION_REGEX = re.compile(r'v(\d+)\.(\d+)(?:\((\d+)\))?')


def parse_api_version(api_str: str) -> tuple[int, ...]:
    try:
        return tuple(map(int, api_str.split(".")))
    except (ValueError, AttributeError):
        return (0, 0)


def parse_server_version(server_str: str) -> tuple[int, ...]:
    match = SERVER_VERSION_REGEX.search(server_str)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) else 0
        return (major, minor, patch)
    return (0, 0, 0)


async def async_extract_api_key(host: str) -> str | None:
    url = f"http://{host}/"
    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with async_timeout.timeout(10):
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    html_text = await response.text()
                    match = API_KEY_REGEX.search(html_text)
                    if match:
                        return match.group(1)
    except Exception as err:
        _LOGGER.error("[AstroBox Setup] Exception occurred while scraping API key: %s", err)
    return None


class AstroBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AstroBox."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step where the user provides host and optional MAC."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input["host"]
            raw_mac = user_input.get("mac", "").strip()
            
            # Normalize the MAC address format if provided
            formatted_mac = None
            if raw_mac:
                # Strip out common separators and reconstruct as aa:bb:cc:dd:ee:ff
                clean_mac = re.sub(r"[^a-fA-F0-9]", "", raw_mac)
                if len(clean_mac) == 12:
                    formatted_mac = ":".join(clean_mac[i:i+2].lower() for i in range(0, 12, 2))
                else:
                    errors["base"] = "invalid_mac"

            if not errors:
                api_key = await async_extract_api_key(host)
                
                if not api_key:
                    errors["base"] = "api_key_not_found"
                else:
                    test_url = f"http://{host}/api/version"
                    connector = aiohttp.TCPConnector(family=socket.AF_INET)
                    
                    try:
                        headers = {"X-Api-Key": api_key}
                        async with aiohttp.ClientSession(connector=connector) as session:
                            async with async_timeout.timeout(5):
                                async with session.get(test_url, headers=headers) as response:
                                    
                                    if response.status == 200:
                                        version_data = await response.json()
                                        raw_api = version_data.get("api", "")
                                        raw_server = version_data.get("server", "")
                                        
                                        current_api = parse_api_version(raw_api)
                                        current_server = parse_server_version(raw_server)
                                        
                                        if current_api > TESTED_API_VERSION or current_server > TESTED_SERVER_VERSION:
                                            _LOGGER.warning(
                                                "AstroBox at %s is running a newer firmware version than verified.",
                                                host
                                            )

                                        return self.async_create_entry(
                                            title=f"AstroBox ({host})",
                                            data={
                                                "host": host,
                                                "api_key": api_key,
                                                "mac": formatted_mac # Saved natively to the config entry
                                            }
                                        )
                                        
                                    errors["base"] = "invalid_auth"
                    except Exception as err:
                        _LOGGER.error("[AstroBox Setup] Exception during API verification: %s", err)
                        errors["base"] = "cannot_connect"

        # Form configuration layout
        DATA_SCHEMA = vol.Schema({
            vol.Required("host"): str,
            vol.Optional("mac"): str,
        })

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)
