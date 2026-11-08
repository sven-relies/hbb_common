"""Thin wrapper around hyundai_kia_connect_api (blocking; run in executor)."""

from __future__ import annotations

from hyundai_kia_connect_api import Vehicle, VehicleManager
from hyundai_kia_connect_api.exceptions import AuthenticationError

from .const import KIA_BRAND


class KiaError(Exception):
    """Generic Kia Connect error."""


class KiaAuthError(KiaError):
    """Wrong Kia credentials / expired refresh token."""


class KiaOtpRequired(KiaAuthError):
    """Kia asks for a one-time password, which this integration does not support."""


class KiaClient:
    """Blocking Kia Connect client. Every method must run in an executor."""

    def __init__(self, region: int, username: str, password: str, pin: str) -> None:
        self._manager = VehicleManager(
            region=region,
            brand=KIA_BRAND,
            username=username,
            password=password,
            pin=pin or "",
            language="nl",
        )

    def login(self) -> dict[str, str]:
        """Log in and return {vehicle_id: display name}."""
        try:
            result = self._manager.login()
        except AuthenticationError as err:
            raise KiaAuthError(str(err)) from err
        except Exception as err:  # noqa: BLE001 - library raises many types
            raise KiaError(str(err)) from err
        if result is False:
            raise KiaAuthError("Kia Connect login failed")
        if result is not True:
            raise KiaOtpRequired("Kia Connect requires an OTP code")
        return {
            vid: f"{v.name or 'Kia'} ({v.model or vid})"
            for vid, v in self._manager.vehicles.items()
        }

    def update(self, vehicle_id: str, force_refresh_seconds: int) -> Vehicle:
        """Fetch the latest vehicle state.

        force_refresh_seconds == 0: only read the state cached in the Kia cloud
        (does not wake the car). Otherwise wake the car when the cached state is
        older than that many seconds.
        """
        try:
            self._manager.check_and_refresh_token()
            if force_refresh_seconds > 0:
                self._manager.check_and_force_update_vehicle(force_refresh_seconds, vehicle_id)
            else:
                self._manager.update_vehicle_with_cached_state(vehicle_id)
            return self._manager.get_vehicle(vehicle_id)
        except AuthenticationError as err:
            raise KiaAuthError(str(err)) from err
        except KeyError as err:
            raise KiaError(f"Vehicle {vehicle_id} not found on this account") from err
        except Exception as err:  # noqa: BLE001
            raise KiaError(str(err)) from err
