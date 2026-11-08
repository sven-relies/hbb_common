"""Button: wake the Kia and fetch fresh data."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KiaZaptecConfigEntry
from .coordinator import KiaCoordinator
from .entity import KiaEntity


class KiaForceRefreshButton(KiaEntity, ButtonEntity):
    """Ask the car for fresh data. Uses the 12V battery: don't automate this often."""

    _attr_translation_key = "kia_force_refresh"

    def __init__(self, coordinator: KiaCoordinator) -> None:
        super().__init__(coordinator, "force_refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.force_refresh)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KiaZaptecConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([KiaForceRefreshButton(entry.runtime_data.kia)])
