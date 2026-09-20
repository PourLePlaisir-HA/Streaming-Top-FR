from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            StreamingTopFrProblem(
                entry,
                data["coordinator"],
                data["store"],
            )
        ]
    )


class StreamingTopFrProblem(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Streaming Top FR"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, coordinator, store):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self.store = store

    @property
    def is_on(self):
        return not self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        providers = data.get("providers", {})
        return {
            "updated_at": data.get("updated_at"),
            "settings": data.get("settings", {}),
            "providers": {
                key: {
                    "movies": len(value.get("movies", [])),
                    "tv": len(value.get("tv", [])),
                    "error": value.get("error"),
                    "source": value.get("source_label"),
                    "week": value.get("week"),
                }
                for key, value in providers.items()
            },
            "watched_count": len(self.store.watched_keys()),
            "watchlist_count": len(self.store.watchlist_keys()),
            "not_interested_count": len(self.store.not_interested_keys()),
        }
