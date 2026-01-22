import logging
import re
from datetime import date, datetime, timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)


class RD4Coordinator(DataUpdateCoordinator):
    """RD4 Waste Calendar API coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.session = aiohttp.ClientSession()

        data = {**entry.data, **entry.options}

        self.feed_url = data["feed_url"]
        self.postal_code = re.sub(r"[^A-Z0-9]", "", data["postal_code"].upper())
        self.house_number = data["house_number"]
        self.house_number_extension = data.get("house_number_extension", "")
        self.bins = (
            data["bins"]
            if isinstance(data["bins"], list)
            else [b.strip() for b in data["bins"].split(",")]
        )

        super().__init__(
            hass,
            _LOGGER,
            name="RD4 Waste Calendar",
            update_interval=timedelta(minutes=data.get("scan_interval", 360)),
        )

    async def async_close(self):
        await self.session.close()

    async def _async_update_data(self):
        try:
            today = date.today()
            year = today.year

            # Fetch current year
            payload = await self._fetch_year(year)
            result = self._parse_calendar(payload)

            # Determine which bins are still missing
            missing = set(self.bins) - set(result.keys())

            # Fetch next year if needed
            if missing:
                payload_next = await self._fetch_year(year + 1)
                next_year_data = self._parse_calendar(payload_next)

                for waste in missing:
                    if waste in next_year_data:
                        result[waste] = next_year_data[waste]

            return result

        except Exception as err:
            raise UpdateFailed(err) from err

    async def _fetch_year(self, year: int):
        params = {
            "postal_code": self.postal_code,
            "house_number": self.house_number,
            "house_number_extension": self.house_number_extension,
            "year": year,
        }

        async with self.session.get(self.feed_url, params=params) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"HTTP {resp.status}")

            payload = await resp.json()

        #_LOGGER.warning("RD4 fetched calendar for year %s", year)
        return payload

    def _parse_calendar(self, payload):
        result = {}
        today = date.today()

        items = payload.get("data", {}).get("items", [])
        for sublist in items:
            if not isinstance(sublist, list):
                continue

            for entry in sublist:
                try:
                    waste = entry["type"]
                    pickup = datetime.fromisoformat(entry["date"]).date()
                except Exception:
                    continue

                # Only first upcoming pickup per waste type
                if waste in result:
                    continue

                if pickup >= today:
                    result[waste] = pickup

        return result
