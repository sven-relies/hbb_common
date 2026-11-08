"""Tests for the Kia + Zaptec integration (APIs mocked)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

import custom_components.kia_zaptec.kia_api  # noqa: F401
import custom_components.kia_zaptec.zaptec_api  # noqa: F401
from custom_components.kia_zaptec.sensor import _ocmf_reading, zaptec_meter_total

ZAP = "custom_components.kia_zaptec.zaptec_api.ZaptecApi"
KIA = "custom_components.kia_zaptec.kia_api.KiaClient"
OCMF = 'OCMF|{"FV":"1.0","RD":[{"TM":"x","RV":1234.5,"RI":"1-0:1.8.0","RU":"kWh"}]}|{"SA":"x"}'


def make_state(session_kwh: str = "4.2") -> dict[int, str]:
    return {708: "16", 501: "231", 502: "230", 503: "229", 513: "11000", 710: "3",
            553: session_kwh, 554: OCMF, 510: "16", 707: "25", 718: "0"}


def make_vehicle() -> SimpleNamespace:
    return SimpleNamespace(
        ev_battery_percentage=40, ev_charge_limits_ac=80, ev_charge_limits_dc=90,
        ev_driving_range=150, ev_estimated_current_charge_duration=130, ev_charging_power=10.8,
        ev_battery_soh_percentage=100, last_updated_at=datetime.now(UTC),
        ev_battery_is_charging=True, ev_battery_is_plugged_in=1, name="EV2", model="EV2",
    )


def test_ocmf_parsing():
    assert _ocmf_reading(OCMF) == 1234.5
    assert _ocmf_reading("garbage") is None
    assert zaptec_meter_total({554: OCMF, 723: '{"SignedSession": "OCMF|{\\"RD\\":[{\\"RV\\":1240.0}]}"}'}) == 1240.0


@pytest.fixture
def mocks():
    state = make_state()
    vehicle = make_vehicle()
    m = SimpleNamespace(
        state=state, vehicle=vehicle,
        get_state=AsyncMock(side_effect=lambda *_: dict(m.state)),
        send_command=AsyncMock(), set_max_current=AsyncMock(),
        start_charge=MagicMock(), stop_charge=MagicMock(),
        set_charge_limits=MagicMock(), force_refresh=MagicMock(),
    )
    with patch(f"{ZAP}.get_chargers", AsyncMock(return_value=[{"Id": "c1", "Name": "Go", "DeviceId": "ZAP1"}])), \
         patch(f"{ZAP}.get_charger_state", m.get_state), \
         patch(f"{ZAP}.send_command", m.send_command), \
         patch(f"{ZAP}.set_max_current", m.set_max_current), \
         patch(f"{KIA}.__init__", return_value=None), \
         patch(f"{KIA}.login", return_value={"v1": "EV2 (EV2)"}), \
         patch(f"{KIA}.update", return_value=vehicle), \
         patch(f"{KIA}.start_charge", m.start_charge), \
         patch(f"{KIA}.stop_charge", m.stop_charge), \
         patch(f"{KIA}.set_charge_limits", m.set_charge_limits), \
         patch(f"{KIA}.force_refresh", m.force_refresh):
        yield m


async def _setup(hass):
    r = await hass.config_entries.flow.async_init("kia_zaptec", context={"source": config_entries.SOURCE_USER})
    assert r["type"] == FlowResultType.FORM and r["step_id"] == "user"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"zaptec_username": "a", "zaptec_password": "b"})
    assert r["step_id"] == "kia", r
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"kia_region": "1", "kia_username": "x", "kia_password": "y"})
    assert r["type"] == FlowResultType.CREATE_ENTRY, r
    await hass.async_block_till_done()
    return r["result"]


async def test_setup_and_sensors(hass, mocks):
    await _setup(hass)
    st = lambda e: hass.states.get(e).state  # noqa: E731
    assert st("sensor.ev2_energy_to_charge_limit") == "24.4"
    assert st("sensor.ev2_time_to_charge_limit_live") == "133"
    assert st("sensor.zaptec_go_2_power_offered_to_car") == "11040"
    assert st("sensor.zaptec_go_2_total_energy_charged") == "1234.5"
    assert st("switch.zaptec_go_2_charging_allowed") == "on"
    assert st("number.zaptec_go_2_max_charging_current") == "16.0"
    assert hass.states.get("number.zaptec_go_2_max_charging_current").attributes["max"] == 25
    assert st("number.ev2_charge_limit_ac") == "80"


async def test_controls(hass, mocks):
    entry = await _setup(hass)
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.zaptec_go_2_charging_allowed"}, blocking=True)
    mocks.send_command.assert_awaited_with("c1", 506)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.zaptec_go_2_max_charging_current", "value": 10}, blocking=True)
    mocks.set_max_current.assert_awaited_with("c1", 10.0)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.ev2_charge_limit_ac", "value": 70}, blocking=True)
    mocks.set_charge_limits.assert_called_with("v1", 70, 90)
    assert hass.states.get("number.ev2_charge_limit_ac").state == "70"
    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.ev2_charging_car"}, blocking=True)
    mocks.stop_charge.assert_called_once_with("v1")
    assert hass.states.get("switch.ev2_charging_car").state == "off"
    await hass.services.async_call("button", "press", {"entity_id": "button.ev2_refresh_car_now"}, blocking=True)
    mocks.force_refresh.assert_called_once_with("v1")
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_cost_accumulates(hass, mocks):
    entry = await _setup(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "energy_price": 0.25})
    await hass.async_block_till_done()  # reload with new price
    coord = entry.runtime_data.zaptec
    mocks.state[553] = "6.2"  # +2 kWh
    await coord.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.zaptec_go_2_session_cost").state == "0.5"
    mocks.state[553] = "1.0"  # new session: 1 kWh
    await coord.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.zaptec_go_2_session_cost").state == "0.25"
    assert hass.states.get("sensor.zaptec_go_2_total_charging_cost").state == "0.75"


async def test_reauth(hass, mocks):
    entry = await _setup(hass)
    r = await hass.config_entries.flow.async_init(
        "kia_zaptec", context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data
    )
    assert r["step_id"] == "reauth_confirm"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"zaptec_password": "new", "kia_password": "newtoken"})
    assert r["type"] == FlowResultType.ABORT and r["reason"] == "reauth_successful"
    assert entry.data["kia_password"] == "newtoken"
