"""Config flow for RD4 Waste Calendar integration."""
from __future__ import annotations

import re
import voluptuous as vol

from homeassistant import config_entries
from .const import DOMAIN


def _normalize_bins(value: str) -> list[str]:
    """Normalize a comma-separated bin string into a list."""
    return [b.strip() for b in value.split(",") if b.strip()]


class RD4ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RD4."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            data = dict(user_input)

            # Normalize postal code
            data["postal_code"] = re.sub(r"[^A-Z0-9]", "", data["postal_code"].upper())

            # Normalize bins
            data["bins"] = _normalize_bins(data["bins"])

            # Stable unique ID (location-based)
            unique_id = f"{data['postal_code']}_{data['house_number']}_{data['house_number_extension']}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"RD4 {data['postal_code']}",
                data=data,
            )

        # Schema for the form
        schema = vol.Schema(
            {
                vol.Required(
                    "feed_url",
                    default="https://data.rd4.nl/api/v1/waste-calendar",
                ): str,
                vol.Required("postal_code", default="6466JD"): str,
                vol.Required("house_number", default=22): int,
                vol.Optional("house_number_extension", default=""): str,
                vol.Required("scan_interval", default=360): vol.Coerce(int),
                vol.Required(
                    "bins",
                    default="residual_waste,gft,paper,pmd",
                ): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(entry):
        return RD4OptionsFlowHandler(entry)


class RD4OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for RD4 integration."""

    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        current = {**self.entry.data, **self.entry.options}

        if user_input is not None:
            data = dict(user_input)
            data["bins"] = _normalize_bins(data["bins"])
            return self.async_create_entry(title="", data=data)

        # Schema for the options form
        schema = vol.Schema(
            {
                vol.Required(
                    "feed_url",
                    default=current.get("feed_url", "https://data.rd4.nl/api/v1/waste-calendar"),
                ): str,
                vol.Required("postal_code", default=current.get("postal_code", "6466JD")): str,
                vol.Required("house_number", default=current.get("house_number", 22)): int,
                vol.Optional(
                    "house_number_extension",
                    default=current.get("house_number_extension", ""),
                ): str,
                vol.Required(
                    "scan_interval",
                    default=current.get("scan_interval", 360),
                ): vol.Coerce(int),
                vol.Required(
                    "bins",
                    default=",".join(current.get("bins", [])),
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
