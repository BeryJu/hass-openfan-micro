"""Diagnostics (Download diagnostics) for OpenFAN Micro."""
from __future__ import annotations
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

REDACT = {"host"}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    dev = getattr(entry, "runtime_data", None)
    coord = getattr(dev, "coordinator", None)

    data = {
        "config_entry": {
            "title": entry.title,
            "data": {k: ("REDACTED" if k in REDACT else v) for k, v in entry.data.items()},
            "options": entry.options,
            "entry_id": entry.entry_id,
        },
        "coordinator": {
            "last_update_success": getattr(coord, "last_update_success", None),
            "data": getattr(coord, "data", None),
            "failure_count": getattr(coord, "_consecutive_failures", None),
            "stall_count": getattr(coord, "_consecutive_stall", None),
            "forced_unavailable": getattr(coord, "_forced_unavailable", None),
            "last_error": getattr(coord, "_last_error", None),
        },
        "api_tuning": {
            "poll_interval": getattr(dev.api, "_poll_interval", None),
            "min_pwm": getattr(dev.api, "_min_pwm", None),
            "stall_consecutive": getattr(dev.api, "_stall_consecutive", None),
            "failure_threshold": getattr(dev.api, "_failure_threshold", None),
            "temp_integrate_seconds": entry.options.get("temp_integrate_seconds"),
            "temp_update_min_interval": entry.options.get("temp_update_min_interval"),
            "temp_deadband_pct": entry.options.get("temp_deadband_pct"),
            "min_pwm_calibrated": entry.options.get("min_pwm_calibrated"),
        },
    }
    return data
