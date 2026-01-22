from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as get_device_registry

from .const import DOMAIN
from .coordinator import RD4Coordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    coordinator: RD4Coordinator = hass.data[DOMAIN][entry.entry_id]

    # Ensure device exists first
    dev_reg = get_device_registry(hass)
    device_entry = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="YourManufacturer",
        name="RD4 Feed",
        model="RD4 Coordinator",
    )

    # Add the button after device is created
    async_add_entities([RD4RefreshButton(coordinator, device_entry.id)])


class RD4RefreshButton(ButtonEntity):
    """Momentary button to refresh RD4 feed."""

    def __init__(self, coordinator: RD4Coordinator, device_id: str):
        self.coordinator = coordinator
        self._attr_name = "RD4 Refresh Feed"
        self._attr_unique_id = "rd4_refresh_feed"
        self._attr_icon = "mdi:refresh"
        self._attr_device_id = device_id

    async def async_press(self):
        """Trigger the refresh when pressed."""
        await self.coordinator.async_request_refresh()
