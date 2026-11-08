"""Config flow: Zaptec account -> charger -> Kia account -> vehicle."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_ENERGY_PRICE,
    CONF_PRICE_ENTITY,
    CONF_KIA_FORCE_REFRESH,
    CONF_KIA_PASSWORD,
    CONF_KIA_PIN,
    CONF_KIA_REGION,
    CONF_KIA_SCAN_INTERVAL,
    CONF_KIA_USERNAME,
    CONF_KIA_VEHICLE_ID,
    CONF_ZAPTEC_CHARGER_ID,
    CONF_ZAPTEC_PASSWORD,
    CONF_ZAPTEC_SCAN_INTERVAL,
    CONF_ZAPTEC_USERNAME,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_ENERGY_PRICE,
    DEFAULT_KIA_FORCE_REFRESH,
    DEFAULT_KIA_SCAN_INTERVAL,
    DEFAULT_ZAPTEC_SCAN_INTERVAL,
    DOMAIN,
    KIA_REGIONS,
)
from .kia_api import KiaAuthError, KiaClient, KiaError, KiaOtpRequired
from .zaptec_api import ZaptecApi, ZaptecAuthError, ZaptecError

_LOGGER = logging.getLogger(__name__)

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _select(options: dict[str, str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=k, label=v) for k, v in options.items()]
        )
    )


class KiaZaptecConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._chargers: dict[str, str] = {}
        self._vehicles: dict[str, str] = {}

    # --- Zaptec -------------------------------------------------------------
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = ZaptecApi(
                async_get_clientsession(self.hass),
                user_input[CONF_ZAPTEC_USERNAME],
                user_input[CONF_ZAPTEC_PASSWORD],
            )
            try:
                chargers = await api.get_chargers()
            except ZaptecAuthError:
                errors["base"] = "zaptec_auth"
            except ZaptecError:
                errors["base"] = "zaptec_connect"
            else:
                self._chargers = {
                    c["Id"]: f"{c.get('Name') or 'Zaptec'} ({c.get('DeviceId', c['Id'])})"
                    for c in chargers
                }
                if not self._chargers:
                    errors["base"] = "no_chargers"
                else:
                    self._data.update(user_input)
                    if len(self._chargers) == 1:
                        self._data[CONF_ZAPTEC_CHARGER_ID] = next(iter(self._chargers))
                        return await self.async_step_kia()
                    return await self.async_step_charger()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZAPTEC_USERNAME): str,
                    vol.Required(CONF_ZAPTEC_PASSWORD): PASSWORD,
                }
            ),
            errors=errors,
        )

    async def async_step_charger(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data[CONF_ZAPTEC_CHARGER_ID] = user_input[CONF_ZAPTEC_CHARGER_ID]
            return await self.async_step_kia()
        return self.async_show_form(
            step_id="charger",
            data_schema=vol.Schema({vol.Required(CONF_ZAPTEC_CHARGER_ID): _select(self._chargers)}),
        )

    # --- Kia ----------------------------------------------------------------
    async def async_step_kia(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            region = int(user_input[CONF_KIA_REGION])
            client = KiaClient(
                region,
                user_input[CONF_KIA_USERNAME],
                user_input[CONF_KIA_PASSWORD],
                user_input.get(CONF_KIA_PIN, ""),
            )
            try:
                self._vehicles = await self.hass.async_add_executor_job(client.login)
            except KiaOtpRequired:
                errors["base"] = "kia_otp"
            except KiaAuthError:
                errors["base"] = "kia_auth"
            except KiaError:
                _LOGGER.exception("Kia Connect login failed")
                errors["base"] = "kia_connect"
            else:
                if not self._vehicles:
                    errors["base"] = "no_vehicles"
                else:
                    self._data.update(user_input)
                    self._data[CONF_KIA_REGION] = region
                    if len(self._vehicles) == 1:
                        return await self._create(next(iter(self._vehicles)))
                    return await self.async_step_vehicle()

        return self.async_show_form(
            step_id="kia",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_KIA_REGION, default="1"): _select(
                        {str(k): v for k, v in KIA_REGIONS.items()}
                    ),
                    vol.Required(CONF_KIA_USERNAME): str,
                    vol.Required(CONF_KIA_PASSWORD): PASSWORD,
                    vol.Optional(CONF_KIA_PIN, default=""): PASSWORD,
                }
            ),
            errors=errors,
        )

    async def async_step_vehicle(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input[CONF_KIA_VEHICLE_ID])
        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema({vol.Required(CONF_KIA_VEHICLE_ID): _select(self._vehicles)}),
        )

    async def _create(self, vehicle_id: str) -> ConfigFlowResult:
        self._data[CONF_KIA_VEHICLE_ID] = vehicle_id
        await self.async_set_unique_id(f"{self._data[CONF_ZAPTEC_CHARGER_ID]}_{vehicle_id}")
        self._abort_if_unique_id_configured()
        title = f"{self._vehicles[vehicle_id]} + {self._chargers[self._data[CONF_ZAPTEC_CHARGER_ID]]}"
        return self.async_create_entry(title=title, data=self._data)

    # --- Re-authentication ----------------------------------------------------
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            api = ZaptecApi(
                async_get_clientsession(self.hass),
                data[CONF_ZAPTEC_USERNAME],
                data[CONF_ZAPTEC_PASSWORD],
            )
            client = KiaClient(
                data[CONF_KIA_REGION], data[CONF_KIA_USERNAME],
                data[CONF_KIA_PASSWORD], data.get(CONF_KIA_PIN, ""),
            )
            try:
                await api.get_chargers()
            except ZaptecAuthError:
                errors["base"] = "zaptec_auth"
            except ZaptecError:
                errors["base"] = "zaptec_connect"
            if not errors:
                try:
                    await self.hass.async_add_executor_job(client.login)
                except KiaOtpRequired:
                    errors["base"] = "kia_otp"
                except KiaAuthError:
                    errors["base"] = "kia_auth"
                except KiaError:
                    errors["base"] = "kia_connect"
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZAPTEC_PASSWORD): PASSWORD,
                    vol.Required(CONF_KIA_PASSWORD): PASSWORD,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return KiaZaptecOptionsFlow()


class KiaZaptecOptionsFlow(OptionsFlow):
    """Battery capacity and polling intervals."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options

        def num(minimum: float, maximum: float, step: float, unit: str) -> NumberSelector:
            return NumberSelector(
                NumberSelectorConfig(
                    min=minimum, max=maximum, step=step, unit_of_measurement=unit,
                    mode=NumberSelectorMode.BOX,
                )
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_CAPACITY,
    CONF_ENERGY_PRICE,
    CONF_PRICE_ENTITY,
                        default=opts.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
                    ): num(10, 150, 0.1, "kWh"),
                    vol.Required(
                        CONF_ZAPTEC_SCAN_INTERVAL,
                        default=opts.get(CONF_ZAPTEC_SCAN_INTERVAL, DEFAULT_ZAPTEC_SCAN_INTERVAL),
                    ): num(5, 600, 1, "s"),
                    vol.Required(
                        CONF_KIA_SCAN_INTERVAL,
                        default=opts.get(CONF_KIA_SCAN_INTERVAL, DEFAULT_KIA_SCAN_INTERVAL),
                    ): num(1, 120, 1, "min"),
                    vol.Required(
                        CONF_KIA_FORCE_REFRESH,
                        default=opts.get(CONF_KIA_FORCE_REFRESH, DEFAULT_KIA_FORCE_REFRESH),
                    ): num(0, 1440, 1, "min"),
                    vol.Required(
                        CONF_ENERGY_PRICE,
                        default=opts.get(CONF_ENERGY_PRICE, DEFAULT_ENERGY_PRICE),
                    ): num(0, 5, 0.001, f"{self.hass.config.currency}/kWh"),
                    vol.Optional(
                        CONF_PRICE_ENTITY,
                        description={"suggested_value": opts.get(CONF_PRICE_ENTITY)},
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                }
            ),
        )
