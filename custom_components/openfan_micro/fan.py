"""Fan entity for OpenFAN Micro."""
from __future__ import annotations
from typing import Any, Optional
import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
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
        _LOGGER.error("OpenFAN Micro: runtime_data is None")
        return
    async_add_entities([OpenFanMicroFan(device)])


class OpenFanMicroFan(CoordinatorEntity, FanEntity):
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )

    def __init__(self, device) -> None:
        super().__init__(device.coordinator)
        self._device = device
        self._host = getattr(device, "host", "unknown")
        name = getattr(device, "name", None) or f"OpenFAN Micro {self._host}"
        self._attr_name = name
        self._attr_unique_id = f"openfan_micro_fan_{self._host}"
        self._last_pct = 50

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
    def percentage(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("pwm")

    @property
    def is_on(self) -> bool | None:
        pct = self.percentage or 0
        return pct > 0

    async def async_set_percentage(self, percentage: int) -> None:
        # Enforce global min_pwm if >0 (except when turning off)
        min_pwm = int(getattr(self._device.api, "_min_pwm", 0) or 0)
        pct = int(percentage)
        if pct > 0:
            pct = max(min_pwm, pct)
        pct = max(0, min(100, pct))
        self._last_pct = pct
        await self._device.api.set_pwm(pct)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        pct = int(percentage) if percentage is not None else (self._last_pct or 50)
        await self.async_set_percentage(pct)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_set_percentage(0)
