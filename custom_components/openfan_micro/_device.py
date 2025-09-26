"""Device wrapper for OpenFAN Micro.

Exposes:
- `api`: low-level HTTP client
- `coordinator`: DataUpdateCoordinator for polling status
- `device_info()`: HA device registry metadata
"""
from __future__ import annotations

from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.device_registry import format_mac

from .api import OpenFanApi
from .coordinator import OpenFanCoordinator

try:
    from .const import DOMAIN  # type: ignore
except Exception:  # pragma: no cover
    DOMAIN = "openfan_micro"


class OpenFanDevice:
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        name: Optional[str] = None,
        *,
        mac: Optional[str] = None,
        session=None,
    ) -> None:
        self.hass = hass
        self.host = host
        self.name = name or f"OpenFAN Micro {host}"

        # Use HA's shared aiohttp session
        if session is None:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            session = async_get_clientsession(hass)

        self.api = OpenFanApi(host, session)
        self.coordinator: DataUpdateCoordinator = OpenFanCoordinator(hass, self.api)

        self._fixed_data: dict[str, Any] = {
            "host": host,
            "name": self.name,
            "mac": mac,
            "model": "OpenFAN Micro",
            "manufacturer": "Karanovic Research",
        }

    async def async_first_refresh(self) -> None:
        """Initial status fetch (raises if network/API fails)."""
        await self.coordinator.async_config_entry_first_refresh()

    @property
    def mac(self) -> Optional[str]:
        """Formatted MAC address or None if not available/invalid."""
        raw = self._fixed_data.get("mac")
        if not raw:
            return None
        try:
            return format_mac(raw)
        except Exception:
            return None

    def device_info(self) -> dict[str, Any]:
        """Return HA device registry information."""
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, self.host)},
            "manufacturer": self._fixed_data.get("manufacturer", "Karanovic Research"),
            "model": self._fixed_data.get("model", "OpenFAN Micro"),
            "name": self._fixed_data.get("name", self.name),
        }
        m = self.mac
        if m:
            try:
                from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
                info["connections"] = {(CONNECTION_NETWORK_MAC, m)}
            except Exception:
                pass
        return info

    @property
    def coordinator_data(self) -> dict[str, Any]:
        return dict(self.coordinator.data or {})

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OpenFanDevice host={self.host} name={self.name!r} mac={self.mac!r}>"


# Backwards-compatible alias
Device = OpenFanDevice
