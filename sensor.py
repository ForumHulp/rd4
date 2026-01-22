from datetime import date
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, WASTE_ICONS, RENAME_MESSAGE, ATTR_TITLE, ATTR_MESSAGE, ATTR_WASTE_TYPE, ATTR_DAYS_UNTIL, ATTR_PICTURE, ATTR_PICK_UP
from .coordinator import RD4Coordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    coordinator: RD4Coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        RD4BinSensor(coordinator, bin_type, entry)
        for bin_type in coordinator.bins
    )


class RD4BinSensor(CoordinatorEntity, SensorEntity):
    """Date sensor for next bin pickup."""

    _attr_device_class = "date"

    def __init__(self, coordinator, bin_type, entry):
        super().__init__(coordinator)
        self.bin_type = bin_type
        self._attr_unique_id = f"{entry.entry_id}_{bin_type}"
        self._attr_name = f"RD4 {bin_type.replace('_', ' ').title()}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self.bin_type)

    @property
    def extra_state_attributes(self):
        pickup = self.native_value
        if not pickup:
            return {}

        return {
            ATTR_WASTE_TYPE: self.bin_type,
            ATTR_DAYS_UNTIL: (pickup - date.today()).days,
            ATTR_PICK_UP: pickup == date.today(),
            ATTR_TITLE: RENAME_MESSAGE.get(self.bin_type, None),
            ATTR_MESSAGE: RENAME_MESSAGE.get(self.bin_type, None) + ' buiten zetten',
            ATTR_PICTURE: WASTE_ICONS.get(self.bin_type, None)
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "RD4 Waste Calendar",
            "manufacturer": "RD4",
        }
