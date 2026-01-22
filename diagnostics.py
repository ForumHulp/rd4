from homeassistant.components.diagnostics import async_redact_data

REDACT = {
    "postal_code",
    "house_number",
    "house_number_extension",
}


async def async_get_config_entry_diagnostics(hass, entry):
    data = {**entry.data, **entry.options}
    return async_redact_data(data, REDACT)
