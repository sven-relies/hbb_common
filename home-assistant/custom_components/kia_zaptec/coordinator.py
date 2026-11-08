"""Data update coordinators for Zaptec (fast) and Kia (slow)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from hyundai_kia_connect_api import Vehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_KIA_FORCE_REFRESH,
    CONF_KIA_SCAN_INTERVAL,
    CONF_KIA_VEHICLE_ID,
    CONF_ZAPTEC_CHARGER_ID,
    CONF_ZAPTEC_SCAN_INTERVAL,
    DEFAULT_KIA_FORCE_REFRESH,
    DEFAULT_KIA_SCAN_INTERVAL,
    DEFAULT_ZAPTEC_SCAN_INTERVAL,
    DOMAIN,
    ZAPTEC_MAX_CURRENT,
)
from .kia_api import KiaAuthError, KiaClient, KiaError
from .zaptec_api import ZaptecApi, ZaptecAuthError, ZaptecError

_LOGGER = logging.getLogger(__name__)


class ZaptecCoordinator(DataUpdateCoordinator[dict[int, str]]):
    """Polls the Zaptec Go 2 live state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ZaptecApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_zaptec",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_ZAPTEC_SCAN_INTERVAL, DEFAULT_ZAPTEC_SCAN_INTERVAL)
            ),
        )
        self.api = api
        self.charger_id: str = entry.data[CONF_ZAPTEC_CHARGER_ID]

    async def async_command(self, command_id: int) -> None:
        """Send a charger command and refresh."""
        try:
            await self.api.send_command(self.charger_id, command_id)
        except ZaptecError as err:
            raise HomeAssistantError(f"Zaptec command failed: {err}") from err
        await self.async_request_refresh()

    async def async_set_max_current(self, current: float) -> None:
        try:
            await self.api.set_max_current(self.charger_id, current)
        except ZaptecError as err:
            raise HomeAssistantError(f"Setting Zaptec current failed: {err}") from err
        if self.data is not None:
            self.data[ZAPTEC_MAX_CURRENT] = str(current)
            self.async_update_listeners()
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[int, str]:
        try:
            return await self.api.get_charger_state(self.charger_id)
        except ZaptecAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZaptecError as err:
            raise UpdateFailed(str(err)) from err


@dataclass
class KiaData:
    """Snapshot of the vehicle."""

    vehicle: Vehicle


class KiaCoordinator(DataUpdateCoordinator[KiaData]):
    """Polls the Kia EV2 via Kia Connect."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: KiaClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_kia",
            update_interval=timedelta(
                minutes=entry.options.get(CONF_KIA_SCAN_INTERVAL, DEFAULT_KIA_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.vehicle_id: str = entry.data[CONF_KIA_VEHICLE_ID]
        self._force_refresh_seconds = 60 * int(
            entry.options.get(CONF_KIA_FORCE_REFRESH, DEFAULT_KIA_FORCE_REFRESH)
        )

    async def async_command(self, func: Callable[..., Any], *args: Any) -> None:
        """Run a blocking Kia command in the executor."""
        try:
            await self.hass.async_add_executor_job(func, self.vehicle_id, *args)
        except KiaAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Kia Connect login expired: {err}") from err
        except KiaError as err:
            raise HomeAssistantError(f"Kia command failed: {err}") from err

    async def _async_update_data(self) -> KiaData:
        try:
            vehicle = await self.hass.async_add_executor_job(
                self.client.update, self.vehicle_id, self._force_refresh_seconds
            )
        except KiaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KiaError as err:
            raise UpdateFailed(str(err)) from err
        return KiaData(vehicle=vehicle)
