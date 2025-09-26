"""RPM sensor for OpenFAN Micro."""
from __future__ import annotations
from typing import Any
import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device = getattr(entry, "runtime_data", None)
    if device is None:
        _LOGGER.error("OpenFAN Micro: runtime_data is None (sensor)")
        return
    async_add_entities([OpenFanRpmSensor(device)])


class OpenFanRpmSensor(CoordinatorEntity, SensorEntity):
    _attr_native_unit_of_measurement = "rpm"
    _attr_icon = "mdi:fan"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, device) -> None:
        super().__init__(device.coordinator)
        self._device = device
        self._host = getattr(device, "host", "unknown")
        name = getattr(device, "name", None) or f"OpenFAN Micro {self._host}"
        self._attr_name = f"{name} RPM"
        self._attr_unique_id = f"openfan_micro_rpm_{self._host}"

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

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return int(data.get("rpm") or 0)
