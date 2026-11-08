"""Kia + Zaptec charging integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_KIA_PASSWORD,
    CONF_KIA_PIN,
    CONF_KIA_REGION,
    CONF_KIA_USERNAME,
    CONF_ZAPTEC_PASSWORD,
    CONF_ZAPTEC_USERNAME,
)
from .coordinator import KiaCoordinator, ZaptecCoordinator
from .kia_api import KiaAuthError, KiaClient, KiaError
from .zaptec_api import ZaptecApi

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class RuntimeData:
    """Objects shared by the platforms."""

    zaptec: ZaptecCoordinator
    kia: KiaCoordinator


type KiaZaptecConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: KiaZaptecConfigEntry) -> bool:
    """Set up from a config entry."""
    zaptec_api = ZaptecApi(
        async_get_clientsession(hass),
        entry.data[CONF_ZAPTEC_USERNAME],
        entry.data[CONF_ZAPTEC_PASSWORD],
    )
    kia_client = KiaClient(
        entry.data[CONF_KIA_REGION],
        entry.data[CONF_KIA_USERNAME],
        entry.data[CONF_KIA_PASSWORD],
        entry.data.get(CONF_KIA_PIN, ""),
    )
    try:
        await hass.async_add_executor_job(kia_client.login)
    except KiaAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except KiaError as err:
        raise ConfigEntryNotReady(str(err)) from err

    zaptec = ZaptecCoordinator(hass, entry, zaptec_api)
    kia = KiaCoordinator(hass, entry, kia_client)
    await zaptec.async_config_entry_first_refresh()
    await kia.async_config_entry_first_refresh()

    entry.runtime_data = RuntimeData(zaptec=zaptec, kia=kia)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: KiaZaptecConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: KiaZaptecConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
