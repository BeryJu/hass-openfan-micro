"""Setup & services for OpenFAN Micro (pro pack with temp smoothing)."""
from __future__ import annotations
import logging, asyncio, time
from typing import Any
from collections import deque

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN
from ._device import Device
from .options_flow import OptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data.get("host"); name = entry.data.get("name"); mac = entry.data.get("mac")
    if not host:
        _LOGGER.error("%s: missing 'host' in config entry", DOMAIN)
        return False

    dev = Device(hass, host, name, mac=mac)

    # --- apply options to API/coordinator ---
    opts = entry.options or {}
    dev.api._poll_interval      = int(opts.get("poll_interval", 5))
    dev.api._min_pwm            = int(opts.get("min_pwm", 0))
    dev.api._failure_threshold  = int(opts.get("failure_threshold", 3))
    dev.api._stall_consecutive  = int(opts.get("stall_consecutive", 3))

    await dev.async_first_refresh()
    entry.runtime_data = dev

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # --- temperature controller: piecewise-linear + smoothing (gated by calibration) ---
    temp_entity = (opts.get("temp_entity") or "").strip()
    temp_curve  = (opts.get("temp_curve") or "").strip()
    integrate_s = int(opts.get("temp_integrate_seconds", 30))
    min_interval_s = int(opts.get("temp_update_min_interval", 10))
    deadband = int(opts.get("temp_deadband_pct", 3))

    # buffer of (timestamp_monotonic, temp_value)
    temp_buf: deque[tuple[float, float]] = deque(maxlen=512)
    last_set_ts: float = 0.0
    last_set_pwm: int | None = None

    def parse_curve(txt: str):
        pts = []
        for part in [p.strip() for p in txt.split(",") if p.strip()]:
            if "=" in part:
                t, pct = part.split("=", 1)
                try:
                    pts.append((float(t.strip()), max(0, min(100, int(pct.strip())))))
                except Exception:
                    continue
        pts.sort(key=lambda x: x[0])
        return pts

    def averaged_temp(now: float) -> float | None:
        # prune old samples
        cutoff = now - max(5, integrate_s)
        while temp_buf and temp_buf[0][0] < cutoff:
            temp_buf.popleft()
        if not temp_buf:
            return None
        # simple arithmetic mean over window
        return sum(val for _, val in temp_buf) / len(temp_buf)

    async def apply_from_temp(raw_temp: float):
        nonlocal last_set_ts, last_set_pwm
        # Gate by calibration
        min_cal_ok = bool(entry.options.get("min_pwm_calibrated", False)) and int(entry.options.get("min_pwm", 0)) > 0
        if not min_cal_ok:
            _LOGGER.debug("OpenFAN Micro %s: temp control ignored (not calibrated yet)", host)
            return

        pts = parse_curve(entry.options.get("temp_curve", temp_curve))
        if not pts:
            return

        now = time.monotonic()
        temp_avg = averaged_temp(now)
        if temp_avg is None:
            # not enough samples yet
            return

        # piecewise linear interpolation on averaged temperature
        temp = temp_avg
        if temp <= pts[0][0]:
            target = pts[0][1]
        elif temp >= pts[-1][0]:
            target = pts[-1][1]
        else:
            target = pts[0][1]
            for (t1, p1), (t2, p2) in zip(pts, pts[1:]):
                if t1 <= temp <= t2:
                    if t2 == t1:
                        target = max(p1, p2)
                    else:
                        ratio = (temp - t1) / (t2 - t1)
                        target = int(round(p1 + (p2 - p1) * ratio))
                    break

        min_pwm = int(entry.options.get("min_pwm", 0))
        # never drive below min (except allow 0 to turn off)
        target = 0 if target == 0 else max(min_pwm, int(target))
        target = max(0, min(100, int(target)))

        # debounce & deadband against last set OR current coordinator value
        if last_set_pwm is None:
            cur = dev.coordinator.data.get("pwm") if dev.coordinator.data else None
            last_set_pwm = int(cur) if isinstance(cur, int) else target

        if abs(int(target) - int(last_set_pwm)) < max(0, deadband):
            return  # within deadband

        if (now - last_set_ts) < max(1, min_interval_s):
            return  # too soon to change again

        await dev.api.set_pwm(int(target))
        await dev.coordinator.async_request_refresh()
        last_set_pwm = int(target)
        last_set_ts = now

    unsub = None
    if temp_entity:
        @callback
        def _on_temp(ev):
            new = ev.data.get("new_state")
            if not new or new.state in (None, "", "unknown", "unavailable"):
                return
            try:
                val = float(new.state)
            except Exception:
                return
            # buffer the sample and try apply with smoothing
            temp_buf.append((time.monotonic(), val))
            hass.async_create_task(apply_from_temp(val))

        unsub = async_track_state_change_event(hass, [temp_entity], _on_temp)
        entry.async_on_unload(unsub)

    # --- services: led_set, set_voltage, calibrate_min ---
    async def _resolve_dev(entity_id: str) -> Device | None:
        er = await hass.helpers.entity_registry.async_get_registry()
        ent = er.async_get(entity_id)
        if not ent or ent.config_entry_id != entry.entry_id:
            return None
        return entry.runtime_data

    async def svc_led_set(call):
        dev = await _resolve_dev(call.data["entity_id"])
        if not dev: return
        await dev.api.led_set(bool(call.data["enabled"]))

    async def svc_set_voltage(call):
        dev = await _resolve_dev(call.data["entity_id"])
        if not dev: return
        volts = int(call.data["volts"])
        await dev.api.set_voltage_12v(True if volts == 12 else False)

    async def svc_calibrate_min(call):
        dev = await _resolve_dev(call.data["entity_id"])
        if not dev: return
        from_pct = int(call.data.get("from_pct", 10))
        to_pct   = int(call.data.get("to_pct", 40))
        step     = int(call.data.get("step", 5))
        rpm_thr  = int(call.data.get("rpm_threshold", 100))
        margin   = int(call.data.get("margin", 5))

        found = None
        for pct in range(from_pct, to_pct + 1, step):
            await dev.api.set_pwm(pct)
            # wait ~1 polling interval for RPM to settle
            await asyncio.sleep(max(1, int(dev.api._poll_interval)))
            await dev.coordinator.async_request_refresh()
            data = dev.coordinator.data or {}
            rpm = int(data.get("rpm") or 0)
            if rpm >= rpm_thr:
                found = pct
                break

        if found is not None:
            new_min = max(0, min(100, found + margin))
            new_opts = dict(entry.options or {})
            new_opts["min_pwm"] = new_min
            new_opts["min_pwm_calibrated"] = True
            hass.config_entries.async_update_entry(entry, options=new_opts)
            _LOGGER.info("Calibrated min_pwm=%s for %s (marked calibrated)", new_min, entry.title)
        else:
            _LOGGER.warning("Calibration did not reach RPM threshold; leaving min_pwm unchanged.")

    hass.services.async_register(DOMAIN, "led_set", svc_led_set)
    hass.services.async_register(DOMAIN, "set_voltage", svc_set_voltage)
    hass.services.async_register(DOMAIN, "calibrate_min", svc_calibrate_min)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)
