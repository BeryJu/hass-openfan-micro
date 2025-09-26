"""Low-level HTTP API client for OpenFAN Micro.

Handles:
- JSON parsing & logging
- Firmware compatibility (new/legacy endpoints)
- Status payload differences (top-level vs nested 'data')
- LED and 5V/12V endpoints (per official docs)
"""
from __future__ import annotations
from typing import Any, Tuple, Optional

import logging
import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)


class OpenFanApi:
    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        # Tunables populated from options in __init__.py
        self._poll_interval: int = 5
        self._min_pwm: int = 0
        self._failure_threshold: int = 3
        self._stall_consecutive: int = 3

    async def _get_json(self, path: str) -> dict:
        """HTTP GET -> JSON dict (logs raw on error)."""
        url = f"http://{self._host}{path}"
        async with async_timeout.timeout(5):
            async with self._session.get(url) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    _LOGGER.error("OpenFAN Micro %s HTTP %s on %s: %s",
                                  self._host, resp.status, path, text)
                    resp.raise_for_status()
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    _LOGGER.error("OpenFAN Micro %s non-JSON on %s: %s",
                                  self._host, path, text)
                    raise
        if not isinstance(data, dict):
            data = {}
        _LOGGER.debug("OpenFAN Micro %s GET %s -> %s", self._host, path, data)
        return data

    # ---------- FAN PWM / STATUS ----------
    def _parse_status_payload(self, data: dict) -> Tuple[int, int]:
        """Accept both top-level and nested ('data') formats. Returns (rpm, pwm%)."""
        container: dict = data or {}
        if not ("rpm" in container or "pwm_percent" in container):
            container = data.get("data", {}) or {}
        rpm_raw = container.get("rpm", 0)
        pwm_raw = container.get("pwm_percent", container.get("pwm", container.get("pwm_value", 0)))
        try:
            rpm = int(float(rpm_raw))
        except Exception:
            rpm = 0
        try:
            pwm = int(float(pwm_raw))
        except Exception:
            pwm = 0
        return max(0, rpm), max(0, min(100, pwm))

    async def set_pwm(self, value: int) -> dict[str, Any]:
        """Set PWM 0..100; tries new (fan/0/set) and old (fan/set) endpoints."""
        value = max(0, min(100, int(value)))
        last_exc: Optional[Exception] = None
        for p in (f"/api/v0/fan/0/set?value={value}", f"/api/v0/fan/set?value={value}"):
            try:
                data = await self._get_json(p)
                if str(data.get("status", "")).lower() in ("ok", "success", ""):
                    return data
                raise RuntimeError(f"API status != ok for {p}: {data}")
            except Exception as exc:
                last_exc = exc
                _LOGGER.debug("OpenFAN Micro %s: set_pwm via %s failed: %r", self._host, p, exc)
        assert last_exc is not None
        raise last_exc

    async def get_status(self) -> Tuple[int, int]:
        """Return (rpm, pwm_percent)."""
        last_exc: Optional[Exception] = None
        for p in ("/api/v0/fan/status", "/api/v0/fan/0/status"):
            try:
                data = await self._get_json(p)
                if str(data.get("status", "ok")).lower() not in ("ok", "success"):
                    raise RuntimeError(f"API status != ok for {p}: {data.get('message')}")
                return self._parse_status_payload(data)
            except Exception as exc:
                last_exc = exc
                _LOGGER.debug("OpenFAN Micro %s: get_status via %s failed: %r", self._host, p, exc)
        assert last_exc is not None
        raise last_exc

    # ---------- OPENFAN STATUS (LED & VOLTAGE) ----------
    async def get_openfan_status(self) -> Tuple[bool, bool]:
        """Return (led_enabled, is_12v) from /api/v0/openfan/status."""
        data = await self._get_json("/api/v0/openfan/status")
        if str(data.get("status", "ok")).lower() not in ("ok", "success"):
            raise RuntimeError(f"API status != ok: {data.get('message')}")
        d = data.get("data", {}) or {}
        led = str(d.get("act_led_enabled", "false")).lower() in ("true", "1", "yes", "on")
        is_12v = str(d.get("fan_is_12v", "false")).lower() in ("true", "1", "yes", "on")
        return led, is_12v

    async def led_set(self, enabled: bool) -> dict:
        """Enable/disable activity LED via official endpoints."""
        path = "/api/v0/led/enable" if enabled else "/api/v0/led/disable"
        return await self._get_json(path)

    async def set_voltage_12v(self, enabled: bool) -> dict:
        """Switch fan supply to 12V (True) or 5V (False). Requires confirm=true."""
        path = "/api/v0/fan/voltage/high?confirm=true" if enabled else "/api/v0/fan/voltage/low?confirm=true"
        return await self._get_json(path)
