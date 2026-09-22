"use strict";

global.HTMLElement = class {};
global.window = {
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() {},
};
global.CustomEvent = class {
  constructor(type, options) {
    this.type = type;
    this.detail = options?.detail;
  }
};
global.customElements = {
  defs: new Map(),
  define(name, ctor) {
    this.defs.set(name, ctor);
  },
};

require("../custom_components/streaming_top_fr/www/streaming-top-fr-card.js");

const StreamingCard = global.customElements.defs.get("streaming-top-fr-card");
const LocalCard = global.customElements.defs.get("streaming-local-card");

if (!StreamingCard || !LocalCard) {
  throw new Error("Streaming Top FR cards are not registered");
}

const titles = [
  "Indiana Jones et les Aventuriers de l'arche perdue",
  "Inside Out",
  "Incendies",
  "Interstellar",
  "Intouchables",
  "Inception",
  "Insomnia",
  "Invictus",
  "Inferno",
  "Insidious",
  "Into the Wild",
  "Indiana Jones et la Dernière Croisade",
  "Élite",
  "Matrix",
];

const card = new StreamingCard();
card._config = { title: "Streaming" };
card._data = {
  settings: {
    card_layout: {
      rows_small: 2,
      rows_medium: 2,
      rows_large: 3,
      posters_par_lot: 8,
      scroll_infini: false,
    },
    discovery: {
      visible_count: 3,
      prefetch_count: 20,
      max_depth: 100,
    },
  },
  provider_order: ["netflix"],
  providers: {
    netflix: {
      movies: titles.map((title, index) => ({
        media_key: `movie:${index + 1}`,
        media_type: "movie",
        title,
      })),
      tv: [],
    },
  },
  watched_keys: [],
  watchlist_keys: [],
  not_interested_keys: [],
  watched: [],
  watchlist: [],
  not_interested: [],
};
card._provider = "netflix";
card._media = "movies";
card._section = "discover";
card._stfrLayoutWidth = 390;
card._stfrRendering = true;

card._stfrSearchQuery = "I";
let results = card._items();
if (card._stfrLayoutFullCount !== 12) {
  throw new Error(`I should match 12 titles, got ${card._stfrLayoutFullCount}`);
}
if (results.length !== 4) {
  throw new Error(`I initial render should respect 4-card capacity, got ${results.length}`);
}

card._stfrSearchQuery = "IN";
results = card._items();
if (card._stfrLayoutFullCount !== 12) {
  throw new Error(`IN should match the same 12-title fixture, got ${card._stfrLayoutFullCount}`);
}

card._stfrSearchQuery = "IND";
results = card._items();
if (card._stfrLayoutFullCount !== 2) {
  throw new Error(`IND should match the two Indiana Jones titles, got ${card._stfrLayoutFullCount}`);
}
if (!results.every(item => item.title.startsWith("Indiana"))) {
  throw new Error("IND returned a non-Indiana title");
}

card._stfrSearchQuery = "e";
results = card._items();
if (card._stfrLayoutFullCount !== 1 || results[0]?.title !== "Élite") {
  throw new Error("Accent-insensitive prefix search failed for Élite");
}

card._stfrSearchQuery = "indiana jones et la d";
results = card._items();
if (
  card._stfrLayoutFullCount !== 1 ||
  !results[0]?.title.includes("Dernière Croisade")
) {
  throw new Error("Multi-word progressive prefix search failed");
}

// Verify that Voir plus operates on the filtered pool, not the unfiltered pool.
card._stfrSearchQuery = "in";
card._stfrLayoutStates = new Map();
results = card._items();
const state = card._stfrLayoutStates.get(card._stfrLayoutKey);
if (!state) throw new Error("Search-specific layout state was not created");
state.expanded = true;
state.limit = Math.min(
  card._stfrLayoutFullCount,
  state.limit + card._stfrBatchSize()
);
results = card._items();
if (results.length !== 12) {
  throw new Error(`Filtered Voir plus should expose 12 results, got ${results.length}`);
}

// Clearing the field restores the normal unfiltered pool.
card._stfrSearchQuery = "";
card._stfrLayoutStates = new Map();
results = card._items();
if (card._stfrLayoutFullCount !== titles.length) {
  throw new Error("Clearing search did not restore the full pool");
}

// Streaming Local uses the same normalization and prefix semantics.
const local = new LocalCard();
local._config = {};
local._stfrSearchQuery = "ind";
const localFiltered = local._stfrSearchFilter([
  { title: "Indiana Jones" },
  { title: "Inside Man" },
  { title: "Été 85" },
]);
if (localFiltered.length !== 1 || localFiltered[0].title !== "Indiana Jones") {
  throw new Error("Streaming Local prefix search failed");
}

if (local._stfrSearchNormalize("Éléphant") !== "elephant") {
  throw new Error("French accent normalization failed");
}

console.log("Instant title prefix search passed.");
