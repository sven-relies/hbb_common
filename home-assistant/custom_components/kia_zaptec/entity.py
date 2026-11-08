"""Base entities and device info."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KiaCoordinator, ZaptecCoordinator


def zaptec_device(coordinator: ZaptecCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"zaptec_{coordinator.charger_id}")},
        manufacturer="Zaptec",
        model="Go 2",
        name="Zaptec Go 2",
    )


def kia_device(coordinator: KiaCoordinator) -> DeviceInfo:
    vehicle = coordinator.data.vehicle if coordinator.data else None
    return DeviceInfo(
        identifiers={(DOMAIN, f"kia_{coordinator.vehicle_id}")},
        manufacturer="Kia",
        model=(vehicle.model if vehicle else None) or "EV2",
        name=(vehicle.name if vehicle else None) or "Kia EV2",
    )


class ZaptecEntity(CoordinatorEntity[ZaptecCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZaptecCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"zaptec_{coordinator.charger_id}_{key}"
        self._attr_device_info = zaptec_device(coordinator)


class KiaEntity(CoordinatorEntity[KiaCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: KiaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"kia_{coordinator.vehicle_id}_{key}"
        self._attr_device_info = kia_device(coordinator)
