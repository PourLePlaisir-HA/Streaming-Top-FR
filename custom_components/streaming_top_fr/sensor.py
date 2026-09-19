from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
async def async_setup_entry(hass, entry, async_add_entities):
    d=hass.data[DOMAIN][entry.entry_id]; async_add_entities([Status(entry,d["coordinator"],d["store"])])
class Status(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name=True; _attr_name="Streaming Top FR"; _attr_icon="mdi:movie-open-star"; _attr_entity_category=EntityCategory.DIAGNOSTIC
    def __init__(self, entry, coordinator, store): super().__init__(coordinator); self._attr_unique_id=f"{entry.entry_id}_status"; self.store=store
    @property
    def native_value(self): return "ok" if self.coordinator.last_update_success else "error"
    @property
    def extra_state_attributes(self):
        data=self.coordinator.data or {}; providers=data.get("providers",{})
        return {"updated_at":data.get("updated_at"), "settings":data.get("settings",{}), "providers":{k:{"movies":len(v.get("movies",[])),"tv":len(v.get("tv",[])),"error":v.get("error"),"source":v.get("source_label"),"week":v.get("week")} for k,v in providers.items()}, "watched_count":len(self.store.watched_keys()), "watchlist_count":len(self.store.watchlist_keys()), "not_interested_count":len(self.store.not_interested_keys())}
