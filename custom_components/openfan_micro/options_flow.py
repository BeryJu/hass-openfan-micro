"""Options flow for OpenFAN Micro (polling, thresholds, temp curve + smoothing)."""
from __future__ import annotations
from typing import Any, Dict
import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

DEFAULTS = {
    "poll_interval": 5,
    "min_pwm": 0,
    "temp_entity": "",
    "temp_curve": "45=25, 65=55, 70=100",  # C=%
    "temp_integrate_seconds": 30,
    "temp_update_min_interval": 10,
    "temp_deadband_pct": 3,
    "failure_threshold": 3,
    "stall_consecutive": 3,
    # "min_pwm_calibrated": false
}

def _schema(options: dict):
    return vol.Schema({
        vol.Optional("poll_interval", default=options.get("poll_interval", DEFAULTS["poll_interval"])): vol.All(int, vol.Range(min=2, max=60)),
        vol.Optional("min_pwm", default=options.get("min_pwm", DEFAULTS["min_pwm"])): vol.All(int, vol.Range(min=0, max=60)),
        vol.Optional("temp_entity", default=options.get("temp_entity", DEFAULTS["temp_entity"])): str,
        vol.Optional("temp_curve", default=options.get("temp_curve", DEFAULTS["temp_curve"])): str,
        vol.Optional("temp_integrate_seconds", default=options.get("temp_integrate_seconds", DEFAULTS["temp_integrate_seconds"])): vol.All(int, vol.Range(min=5, max=900)),
        vol.Optional("temp_update_min_interval", default=options.get("temp_update_min_interval", DEFAULTS["temp_update_min_interval"])): vol.All(int, vol.Range(min=2, max=300)),
        vol.Optional("temp_deadband_pct", default=options.get("temp_deadband_pct", DEFAULTS["temp_deadband_pct"])): vol.All(int, vol.Range(min=0, max=20)),
        vol.Optional("failure_threshold", default=options.get("failure_threshold", DEFAULTS["failure_threshold"])): vol.All(int, vol.Range(min=1, max=10)),
        vol.Optional("stall_consecutive", default=options.get("stall_consecutive", DEFAULTS["stall_consecutive"])): vol.All(int, vol.Range(min=1, max=10)),
    })

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None):
        if user_input is not None:
            merged = dict(self.entry.options or {})
            merged.update(user_input)
            return self.async_create_entry(title="", data=merged)

        return self.async_show_form(step_id="init", data_schema=_schema(self.entry.options or {}))
