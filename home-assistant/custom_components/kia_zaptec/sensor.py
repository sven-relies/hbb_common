"""Sensors for the Zaptec Go 2, the Kia EV2 and combined charging insight."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from typing import Any

from hyundai_kia_connect_api import Vehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KiaZaptecConfigEntry
from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_ENERGY_PRICE,
    CONF_PRICE_ENTITY,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_ENERGY_PRICE,
    ZAPTEC_COMPLETED_SESSION,
    ZAPTEC_SIGNED_METER_VALUE,
    ZAPTEC_CHARGE_CURRENT_SET,
    ZAPTEC_CURRENT_PHASES,
    ZAPTEC_MAX_CURRENT,
    ZAPTEC_OPERATION_MODE,
    ZAPTEC_OPERATION_MODES,
    ZAPTEC_SESSION_ENERGY,
    ZAPTEC_TOTAL_POWER,
    ZAPTEC_VOLTAGE_PHASES,
)
from .coordinator import KiaCoordinator, ZaptecCoordinator
from .entity import KiaEntity, ZaptecEntity, kia_device


def _float(state: dict[int, str], state_id: int) -> float | None:
    raw = state.get(state_id)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


_LOGGER = logging.getLogger(__name__)


def _ocmf_reading(data: str | None) -> float | None:
    """Largest meter reading (kWh) in an OCMF string 'OCMF|{json}|{signature}'."""
    if not data or not isinstance(data, str):
        return None
    parts = data.split("|")
    if len(parts) not in (2, 3) or parts[0] != "OCMF":
        return None
    try:
        readings = json.loads(parts[1]).get("RD", [])
        values = [float(r["RV"]) for r in readings if "RV" in r]
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    return max(values) if values else None


def zaptec_meter_total(state: dict[int, str]) -> float | None:
    """Lifetime energy (kWh) from the signed meter value / last completed session."""
    values = [_ocmf_reading(state.get(ZAPTEC_SIGNED_METER_VALUE))]
    session = state.get(ZAPTEC_COMPLETED_SESSION)
    if session:
        try:
            values.append(_ocmf_reading(json.loads(session).get("SignedSession")))
        except (ValueError, TypeError, AttributeError):
            pass
    values = [v for v in values if v is not None]
    return round(max(values), 3) if values else None


def zaptec_offered_power(state: dict[int, str]) -> float | None:
    """Max power (W) the charger currently offers the car: set current x live phases."""
    current = _float(state, ZAPTEC_CHARGE_CURRENT_SET)
    if current is None:
        return None
    volts = [v for sid in ZAPTEC_VOLTAGE_PHASES if (v := _float(state, sid)) and v > 100]
    if not volts:
        return None
    return round(current * sum(volts))


def _operation_mode(state: dict[int, str]) -> str | None:
    mode = _float(state, ZAPTEC_OPERATION_MODE)
    return None if mode is None else ZAPTEC_OPERATION_MODES.get(int(mode), "unknown")


# --------------------------------------------------------------------------- Zaptec
@dataclass(frozen=True, kw_only=True)
class ZaptecSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[int, str]], Any]


ZAPTEC_SENSORS: tuple[ZaptecSensorDescription, ...] = (
    ZaptecSensorDescription(
        key="charge_power",
        translation_key="charge_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: _float(s, ZAPTEC_TOTAL_POWER),
    ),
    ZaptecSensorDescription(
        key="offered_power",
        translation_key="offered_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=zaptec_offered_power,
    ),
    ZaptecSensorDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda s: _float(s, ZAPTEC_SESSION_ENERGY),
    ),
    ZaptecSensorDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=zaptec_meter_total,
    ),
    ZaptecSensorDescription(
        key="charge_current_set",
        translation_key="charge_current_set",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda s: _float(s, ZAPTEC_CHARGE_CURRENT_SET),
    ),
    ZaptecSensorDescription(
        key="max_current",
        translation_key="max_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: _float(s, ZAPTEC_MAX_CURRENT),
    ),
    ZaptecSensorDescription(
        key="operation_mode",
        translation_key="operation_mode",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(ZAPTEC_OPERATION_MODES.values())),
        value_fn=_operation_mode,
    ),
    *(
        ZaptecSensorDescription(
            key=f"current_l{i}",
            translation_key=f"current_l{i}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=1,
            value_fn=lambda s, sid=sid: _float(s, sid),
        )
        for i, sid in enumerate(ZAPTEC_CURRENT_PHASES, start=1)
    ),
    *(
        ZaptecSensorDescription(
            key=f"voltage_l{i}",
            translation_key=f"voltage_l{i}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda s, sid=sid: _float(s, sid),
        )
        for i, sid in enumerate(ZAPTEC_VOLTAGE_PHASES, start=1)
    ),
)


class ZaptecSensor(ZaptecEntity, SensorEntity):
    entity_description: ZaptecSensorDescription

    def __init__(self, coordinator: ZaptecCoordinator, description: ZaptecSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})


# --------------------------------------------------------------------------- Kia
@dataclass(frozen=True, kw_only=True)
class KiaSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Vehicle], Any]


KIA_SENSORS: tuple[KiaSensorDescription, ...] = (
    KiaSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda v: v.ev_battery_percentage,
    ),
    KiaSensorDescription(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda v: v.ev_driving_range,
    ),
    KiaSensorDescription(
        key="time_to_full",
        translation_key="time_to_full",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda v: v.ev_estimated_current_charge_duration,
    ),
    KiaSensorDescription(
        key="car_charging_power",
        translation_key="car_charging_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda v: getattr(v, "ev_charging_power", None),
    ),
    KiaSensorDescription(
        key="battery_soh",
        translation_key="battery_soh",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: getattr(v, "ev_battery_soh_percentage", None),
    ),
    KiaSensorDescription(
        key="last_updated",
        translation_key="last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: v.last_updated_at if isinstance(v.last_updated_at, datetime) else None,
    ),
)


class KiaSensor(KiaEntity, SensorEntity):
    entity_description: KiaSensorDescription

    def __init__(self, coordinator: KiaCoordinator, description: KiaSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data.vehicle)


# --------------------------------------------------------------------------- combined
class CombinedSensor(SensorEntity):
    """Sensor fed by both coordinators (car state + live charger power)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        kia: KiaCoordinator,
        zaptec: ZaptecCoordinator,
        capacity_kwh: float,
        description: SensorEntityDescription,
    ) -> None:
        self._kia = kia
        self._zaptec = zaptec
        self._capacity = capacity_kwh
        self.entity_description = description
        self._attr_unique_id = f"kia_{kia.vehicle_id}_{description.key}"
        self._attr_device_info = kia_device(kia)

    async def async_added_to_hass(self) -> None:
        for coordinator in (self._kia, self._zaptec):
            self.async_on_remove(coordinator.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._kia.last_update_success

    def _energy_to(self, target: float | None) -> float | None:
        if not self._kia.data:
            return None
        soc = self._kia.data.vehicle.ev_battery_percentage
        if soc is None or target is None:
            return None
        return round(max(0.0, (target - soc) / 100 * self._capacity), 2)

    def energy_to_limit(self) -> float | None:
        if not self._kia.data:
            return None
        return self._energy_to(self._kia.data.vehicle.ev_charge_limits_ac)

    @property
    def native_value(self) -> float | int | None:
        key = self.entity_description.key
        if key == "energy_to_limit":
            return self.energy_to_limit()
        if key == "energy_to_full":
            return self._energy_to(100)
        if key == "time_to_limit_live":
            needed = self.energy_to_limit()
            power_w = _float(self._zaptec.data or {}, ZAPTEC_TOTAL_POWER)
            if needed is None or not power_w or power_w < 100:
                return None
            return round(needed / (power_w / 1000) * 60)
        return None


COMBINED_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="energy_to_limit",
        translation_key="energy_to_limit",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="energy_to_full",
        translation_key="energy_to_full",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="time_to_limit_live",
        translation_key="time_to_limit_live",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)


# --------------------------------------------------------------------------- costs
class ChargingCostSensor(ZaptecEntity, RestoreSensor):
    """Charging cost, accumulated from session energy x (dynamic) price.

    Every Zaptec update the newly charged energy is multiplied by the price at
    that moment, so a dynamic tariff sensor gives a correct cost.
    """

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: ZaptecCoordinator, key: str, per_session: bool,
        price: float, price_entity: str | None, currency: str,
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._attr_native_unit_of_measurement = currency
        self._per_session = per_session
        self._price = price
        self._price_entity = price_entity
        self._last_energy: float | None = None
        self._attr_native_value = 0.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            try:
                self._attr_native_value = float(last.native_value or 0)
            except (TypeError, ValueError):
                self._attr_native_value = 0.0
        self._accumulate()

    def _current_price(self) -> float:
        if self._price_entity:
            state: State | None = self.hass.states.get(self._price_entity)
            try:
                return float(state.state)  # type: ignore[union-attr]
            except (AttributeError, TypeError, ValueError):
                _LOGGER.debug("Price entity %s unavailable, using fixed price", self._price_entity)
        return self._price

    def _accumulate(self) -> None:
        energy = _float(self.coordinator.data or {}, ZAPTEC_SESSION_ENERGY)
        if energy is None:
            return
        if self._last_energy is None:
            # First reading after (re)start: only set the baseline.
            self._last_energy = energy
            return
        if energy < self._last_energy:
            # A new session started.
            if self._per_session:
                self._attr_native_value = 0.0
            delta = energy
        else:
            delta = energy - self._last_energy
        self._last_energy = energy
        if delta > 0:
            self._attr_native_value = round(
                float(self._attr_native_value or 0) + delta * self._current_price(), 4
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._accumulate()
        super()._handle_coordinator_update()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KiaZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = entry.runtime_data
    capacity = float(entry.options.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY))
    entities: list[SensorEntity] = [ZaptecSensor(data.zaptec, d) for d in ZAPTEC_SENSORS]
    entities += [KiaSensor(data.kia, d) for d in KIA_SENSORS]
    entities += [CombinedSensor(data.kia, data.zaptec, capacity, d) for d in COMBINED_SENSORS]
    price = float(entry.options.get(CONF_ENERGY_PRICE, DEFAULT_ENERGY_PRICE))
    price_entity = entry.options.get(CONF_PRICE_ENTITY) or None
    currency = hass.config.currency
    entities += [
        ChargingCostSensor(data.zaptec, "session_cost", True, price, price_entity, currency),
        ChargingCostSensor(data.zaptec, "total_cost", False, price, price_entity, currency),
    ]
    async_add_entities(entities)
