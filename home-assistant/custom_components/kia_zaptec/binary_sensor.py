"""Binary sensors: is the car charging / plugged in."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KiaZaptecConfigEntry
from .coordinator import KiaCoordinator
from .entity import KiaEntity


@dataclass(frozen=True, kw_only=True)
class KiaBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[Vehicle], bool | None]


KIA_BINARY_SENSORS = (
    KiaBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda v: v.ev_battery_is_charging,
    ),
    KiaBinaryDescription(
        key="plugged_in",
        translation_key="plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda v: v.ev_battery_is_plugged_in,
    ),
)


class KiaBinarySensor(KiaEntity, BinarySensorEntity):
    entity_description: KiaBinaryDescription

    def __init__(self, coordinator: KiaCoordinator, description: KiaBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        value = self.entity_description.value_fn(self.coordinator.data.vehicle)
        return None if value is None else bool(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KiaZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    kia = entry.runtime_data.kia
    async_add_entities(KiaBinarySensor(kia, d) for d in KIA_BINARY_SENSORS)
