"""Numbers: Zaptec max charging current, Kia AC/DC charge limits."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KiaZaptecConfigEntry
from .const import ZAPTEC_INSTALLATION_MAX_CURRENT, ZAPTEC_MAX_CURRENT
from .coordinator import KiaCoordinator, ZaptecCoordinator
from .entity import KiaEntity, ZaptecEntity


def _f(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


class ZaptecMaxCurrent(ZaptecEntity, NumberEntity):
    """Maximum current the Zaptec offers the car (6-32 A)."""

    _attr_translation_key = "zaptec_max_current"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = 6
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: ZaptecCoordinator) -> None:
        super().__init__(coordinator, "max_current_set")

    @property
    def native_max_value(self) -> float:
        limit = _f((self.coordinator.data or {}).get(ZAPTEC_INSTALLATION_MAX_CURRENT))
        return limit if limit and limit >= 6 else 32

    @property
    def native_value(self) -> float | None:
        return _f((self.coordinator.data or {}).get(ZAPTEC_MAX_CURRENT))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_max_current(value)


class KiaChargeLimit(KiaEntity, NumberEntity):
    """AC or DC charge limit of the car (50-100 %, steps of 10)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 10
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: KiaCoordinator, kind: str) -> None:
        super().__init__(coordinator, f"charge_limit_{kind}_set")
        self._kind = kind
        self._attr_translation_key = f"kia_charge_limit_{kind}"

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return getattr(self.coordinator.data.vehicle, f"ev_charge_limits_{self._kind}")

    async def async_set_native_value(self, value: float) -> None:
        vehicle = self.coordinator.data.vehicle
        ac = int(value) if self._kind == "ac" else int(vehicle.ev_charge_limits_ac or 100)
        dc = int(value) if self._kind == "dc" else int(vehicle.ev_charge_limits_dc or 100)
        await self.coordinator.async_command(self.coordinator.client.set_charge_limits, ac, dc)
        vehicle.ev_charge_limits_ac = ac
        vehicle.ev_charge_limits_dc = dc
        self.coordinator.async_update_listeners()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KiaZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [ZaptecMaxCurrent(data.zaptec), KiaChargeLimit(data.kia, "ac"), KiaChargeLimit(data.kia, "dc")]
    )
