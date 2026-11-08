"""Minimal async client for the Zaptec cloud API (api.zaptec.com)."""

from __future__ import annotations

import time
from typing import Any

import aiohttp

from .const import ZAPTEC_API


class ZaptecError(Exception):
    """Generic Zaptec API error."""


class ZaptecAuthError(ZaptecError):
    """Wrong Zaptec credentials."""


class ZaptecApi:
    """Talks to the Zaptec Portal API with a username/password grant."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_expires = 0.0

    async def _authenticate(self) -> None:
        try:
            async with self._session.post(
                f"{ZAPTEC_API}/oauth/token",
                data={
                    "grant_type": "password",
                    "username": self._username,
                    "password": self._password,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise ZaptecAuthError("Invalid Zaptec username or password")
                resp.raise_for_status()
                data = await resp.json()
        except aiohttp.ClientError as err:
            raise ZaptecError(f"Cannot reach Zaptec: {err}") from err
        self._token = data["access_token"]
        # Renew a minute before it actually expires.
        self._token_expires = time.monotonic() + int(data.get("expires_in", 3600)) - 60

    async def _get(self, path: str) -> Any:
        if self._token is None or time.monotonic() >= self._token_expires:
            await self._authenticate()
        for attempt in range(2):
            try:
                async with self._session.get(
                    f"{ZAPTEC_API}{path}",
                    headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        await self._authenticate()
                        continue
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as err:
                raise ZaptecError(f"Zaptec request {path} failed: {err.status}") from err
            except aiohttp.ClientError as err:
                raise ZaptecError(f"Cannot reach Zaptec: {err}") from err
        raise ZaptecAuthError("Zaptec rejected the access token")

    async def get_chargers(self) -> list[dict[str, Any]]:
        """Return the chargers on this account (Id, Name, DeviceId, ...)."""
        data = await self._get("/api/chargers")
        return data.get("Data", []) if isinstance(data, dict) else data

    async def get_charger_state(self, charger_id: str) -> dict[int, str]:
        """Return the charger's live observations as {state_id: value_as_string}."""
        data = await self._get(f"/api/chargers/{charger_id}/state")
        return {
            int(item["StateId"]): item.get("ValueAsString")
            for item in data
            if "StateId" in item
        }
