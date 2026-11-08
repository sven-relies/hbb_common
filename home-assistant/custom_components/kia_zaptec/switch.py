"""Switches: pause/resume charging on the Zaptec, start/stop charging in the Kia."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KiaZaptecConfigEntry
from .const import (
    ZAPTEC_CMD_RESUME_CHARGING,
    ZAPTEC_CMD_STOP_CHARGING_FINAL,
    ZAPTEC_FINAL_STOP_ACTIVE,
    ZAPTEC_OPERATION_MODE,
)
from .coordinator import KiaCoordinator, ZaptecCoordinator
from .entity import KiaEntity, ZaptecEntity


class ZaptecChargingSwitch(ZaptecEntity, SwitchEntity):
    """On = charging allowed, off = paused (Zaptec 'stop charging final')."""

    _attr_translation_key = "zaptec_charging"

    def __init__(self, coordinator: ZaptecCoordinator) -> None:
        super().__init__(coordinator, "charging_allowed")

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        return data.get(ZAPTEC_FINAL_STOP_ACTIVE) not in ("1", "true", "True")

    @property
    def available(self) -> bool:
        # Pausing only makes sense while a car is connected.
        data = self.coordinator.data or {}
        return super().available and data.get(ZAPTEC_OPERATION_MODE) not in (None, "0", "1")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(ZAPTEC_CMD_RESUME_CHARGING)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(ZAPTEC_CMD_STOP_CHARGING_FINAL)


class KiaChargingSwitch(KiaEntity, SwitchEntity):
    """Start/stop charging via Kia Connect."""

    _attr_translation_key = "kia_charging"

    def __init__(self, coordinator: KiaCoordinator) -> None:
        super().__init__(coordinator, "charging_switch")

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.vehicle.ev_battery_is_charging
        return None if value is None else bool(value)

    async def _set(self, on: bool) -> None:
        client = self.coordinator.client
        await self.coordinator.async_command(client.start_charge if on else client.stop_charge)
        # Kia's cloud state lags behind; show the requested state right away.
        self.coordinator.data.vehicle.ev_battery_is_charging = on
        self.coordinator.async_update_listeners()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KiaZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities([ZaptecChargingSwitch(data.zaptec), KiaChargingSwitch(data.kia)])
