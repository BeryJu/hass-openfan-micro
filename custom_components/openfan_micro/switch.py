"""LED and 12V switches for OpenFAN Micro."""
from __future__ import annotations
from typing import Any
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    device = getattr(entry, "runtime_data", None)
    if device is None:
        _LOGGER.error("OpenFAN Micro: runtime_data is None (switch)")
        return
    async_add_entities([OpenFanLedSwitch(device), OpenFanVoltageSwitch(device)])


class _BaseSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, device) -> None:
        super().__init__(device.coordinator)
        self._device = device
        self._host = getattr(device, "host", "unknown")

    @property
    def device_info(self) -> dict[str, Any] | None:
        try:
            return self._device.device_info()
        except Exception:
            return None

    @property
    def available(self) -> bool:
        base = super().available
        forced = getattr(self.coordinator, "_forced_unavailable", False)
        return base and not forced


class OpenFanLedSwitch(_BaseSwitch):
    """Activity LED on/off."""
    _attr_icon = "mdi:led-on"

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_name = f"{getattr(device, 'name', 'OpenFAN Micro')} LED"
        self._attr_unique_id = f"openfan_micro_led_{self._host}"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        return bool(data.get("led"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.api.led_set(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.api.led_set(False)
        await self.coordinator.async_request_refresh()


class OpenFanVoltageSwitch(_BaseSwitch):
    """12V mode on/off (on=12V, off=5V)."""
    _attr_icon = "mdi:flash"

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_name = f"{getattr(device, 'name', 'OpenFAN Micro')} 12V Mode"
        self._attr_unique_id = f"openfan_micro_12v_{self._host}"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        return bool(data.get("is_12v"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.api.set_voltage_12v(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.api.set_voltage_12v(False)
        await self.coordinator.async_request_refresh()
