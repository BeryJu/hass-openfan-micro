"""Stall detector binary sensor."""
from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add: AddEntitiesCallback) -> None:
    dev = getattr(entry, "runtime_data", None)
    if dev is None:
        _LOGGER.error("OpenFAN Micro: runtime_data is None (binary_sensor)")
        return
    async_add([OpenFanStallBinarySensor(dev)])


class OpenFanStallBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_icon = "mdi:alert"

    def __init__(self, device) -> None:
        super().__init__(device.coordinator)
        self._device = device
        self._host = getattr(device, "host", "unknown")
        self._attr_unique_id = f"openfan_micro_stall_{self._host}"
        self._attr_name = f"{getattr(device, 'name', 'OpenFAN Micro')} Stall"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        return bool(data.get("stalled", False))

    @property
    def available(self) -> bool:
        base = super().available
        forced = getattr(self.coordinator, "_forced_unavailable", False)
        return base and not forced

    @property
    def device_info(self):
        return self._device.device_info()
