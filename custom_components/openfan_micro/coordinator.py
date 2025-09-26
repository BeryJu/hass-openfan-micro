"""Coordinator with availability gating and stall detection."""
from __future__ import annotations
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenFanApi

_LOGGER = logging.getLogger(__name__)


class OpenFanCoordinator(DataUpdateCoordinator[dict]):
    """Poll device: RPM/PWM + LED + 12V, and track failures & stall."""

    def __init__(self, hass: HomeAssistant, api: OpenFanApi) -> None:
        interval = int(getattr(api, "_poll_interval", 5))
        super().__init__(hass, _LOGGER, name="OpenFAN Micro",
                         update_interval=timedelta(seconds=interval))
        self.api = api
        self._consecutive_failures = 0
        self._forced_unavailable = False
        self._consecutive_stall = 0
        self._notified_stall = False
        self._last_error: str | None = None

    async def _async_update_data(self) -> dict:
        try:
            rpm, pwm = await self.api.get_status()
            self._consecutive_failures = 0
            self._forced_unavailable = False
            self._last_error = None

            led, is_12v = False, False
            try:
                led, is_12v = await self.api.get_openfan_status()
            except Exception as sub_err:
                _LOGGER.debug("OpenFAN Micro: openfan/status fetch failed: %r", sub_err)

            # Stall detection
            min_pwm = int(getattr(self.api, "_min_pwm", 0) or 0)
            need = int(getattr(self.api, "_stall_consecutive", 3) or 3)
            stalled_now = (pwm > max(0, min_pwm)) and int(rpm) == 0
            self._consecutive_stall = (self._consecutive_stall + 1) if stalled_now else 0
            stalled_flag = self._consecutive_stall >= need
            if stalled_flag and not self._notified_stall:
                self._notified_stall = True
                self.hass.bus.async_fire("openfan_micro_stall", {"host": getattr(self.api, "_host", "?")})
                self.hass.components.persistent_notification.async_create(
                    f"Fan looks stalled on {getattr(self.api, '_host', '?')} (PWM={pwm}%, RPM=0)",
                    title="OpenFAN Micro",
                    notification_id=f"openfan_micro_stall_{getattr(self.api,'_host','?')}",
                )
            if not stalled_flag:
                self._notified_stall = False

            data = {
                "rpm": int(max(0, rpm)),
                "pwm": int(max(0, min(100, pwm))),
                "led": bool(led),
                "is_12v": bool(is_12v),
                "stalled": stalled_flag,
            }
            _LOGGER.debug("OpenFAN Micro update OK (%s): %s", getattr(self.api, "_host", "?"), data)
            return data
        except Exception as err:
            # Availability gating after N consecutive failures
            self._last_error = str(err)
            self._consecutive_failures += 1
            fail_thresh = int(getattr(self.api, "_failure_threshold", 3) or 3)
            if self._consecutive_failures >= fail_thresh:
                self._forced_unavailable = True
            _LOGGER.error("OpenFAN Micro update failed (%s): %r", getattr(self.api, "_host", "?"), err)
            raise UpdateFailed(f"Failed to update OpenFAN Micro: {err}") from err
