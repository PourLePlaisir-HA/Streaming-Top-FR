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
  "Les Chroniques de Riddick : Pitch Black",
  "Élite",
  "Matrix",
];

function streamingFixture(config = {}) {
  const card = new StreamingCard();
  card._config = { title: "Streaming", ...config };
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
  return card;
}

const card = streamingFixture();

if (card._stfrSearchBoxEnabled() !== true) {
  throw new Error("Search box must be enabled by default");
}

card._stfrSearchQuery = "I";
let results = card._items();
const countI = card._stfrLayoutFullCount;
if (countI < 2 || results.length !== 4) {
  throw new Error("I search should return multiple titles and respect initial capacity");
}

card._stfrSearchQuery = "IN";
results = card._items();
const countIN = card._stfrLayoutFullCount;
if (countIN > countI || countIN < 2) {
  throw new Error("IN should progressively narrow or keep the I result set");
}

card._stfrSearchQuery = "IND";
results = card._items();
if (card._stfrLayoutFullCount !== 2) {
  throw new Error(`IND should match the two Indiana Jones titles, got ${card._stfrLayoutFullCount}`);
}
if (!results.every(item => item.title.includes("Indiana"))) {
  throw new Error("IND returned a non-Indiana title");
}

// Search is now "contains", not only "starts with".
card._stfrSearchQuery = "pit";
card._stfrLayoutStates = new Map();
results = card._items();
if (
  card._stfrLayoutFullCount !== 1 ||
  results[0]?.title !== "Les Chroniques de Riddick : Pitch Black"
) {
  throw new Error("Contains search failed for 'Pit' / Pitch Black");
}

card._stfrSearchQuery = "elite";
card._stfrLayoutStates = new Map();
results = card._items();
if (card._stfrLayoutFullCount !== 1 || results[0]?.title !== "Élite") {
  throw new Error("Accent-insensitive contains search failed for Élite");
}

card._stfrSearchQuery = "derniere croisade";
card._stfrLayoutStates = new Map();
results = card._items();
if (
  card._stfrLayoutFullCount !== 1 ||
  !results[0]?.title.includes("Dernière Croisade")
) {
  throw new Error("Multi-word contains search failed");
}

// Verify that Voir plus operates on the filtered pool, not the unfiltered pool.
card._stfrSearchQuery = "in";
card._stfrLayoutStates = new Map();
results = card._items();
const state = card._stfrLayoutStates.get(card._stfrLayoutKey);
if (!state) throw new Error("Search-specific layout state was not created");
const filteredCount = card._stfrLayoutFullCount;
state.expanded = true;
state.limit = Math.min(
  filteredCount,
  state.limit + card._stfrBatchSize()
);
results = card._items();
if (results.length !== Math.min(filteredCount, 12)) {
  throw new Error("Filtered Voir plus did not expand only the matching pool");
}

// Clearing the field restores the normal unfiltered pool.
card._stfrSearchQuery = "";
card._stfrLayoutStates = new Map();
results = card._items();
if (card._stfrLayoutFullCount !== titles.length) {
  throw new Error("Clearing search did not restore the full pool");
}

// Lovelace searchbox:false disables both the UI capability and filtering.
const disabled = streamingFixture({ searchbox: false });
if (disabled._stfrSearchBoxEnabled() !== false) {
  throw new Error("searchbox:false Lovelace override was ignored");
}
disabled._stfrSearchQuery = "indiana";
disabled._stfrLayoutStates = new Map();
results = disabled._items();
if (disabled._stfrLayoutFullCount !== titles.length) {
  throw new Error("Disabled searchbox must not filter the card");
}

// Search must inspect all known title fields, not only the first non-empty one.
// This mirrors Local items where the displayed/main title may differ from the
// parsed/original/file title that contains the user's query.
const aliases = streamingFixture();
aliases._stfrSearchQuery = "pit";
aliases._stfrLayoutStates = new Map();
aliases._data.providers.netflix.movies = [
  {
    media_key: "movie:alias",
    media_type: "movie",
    title: "Les Chroniques de Riddick",
    parsed_title: "Pitch Black",
    original_title: "Pitch Black",
    filename: "Pitch Black (2000).mkv",
  },
];
results = aliases._items();
if (
  aliases._stfrLayoutFullCount !== 1 ||
  results[0]?.title !== "Les Chroniques de Riddick"
) {
  throw new Error("Search did not inspect parsed/original/file title aliases");
}

// Streaming Local uses the same contains semantics.
const local = new LocalCard();
local._config = {};
local._stfrSearchQuery = "pit";
const localFiltered = local._stfrSearchFilter([
  { title: "Indiana Jones" },
  { title: "Les Chroniques de Riddick : Pitch Black" },
  { title: "Été 85" },
]);
if (
  localFiltered.length !== 1 ||
  localFiltered[0].title !== "Les Chroniques de Riddick : Pitch Black"
) {
  throw new Error("Streaming Local contains search failed");
}

if (local._stfrSearchNormalize("Éléphant") !== "elephant") {
  throw new Error("French accent normalization failed");
}

console.log("Instant contains-title search and searchbox override passed.");


const noResult = streamingFixture();
noResult._stfrSearchQuery = "introuvable";
const noResultMessage = noResult._stfrSearchNoResultMessage();
if (
  !noResultMessage.includes("introuvable") ||
  !noResultMessage.includes("Aucun résultat")
) {
  throw new Error("No-result search feedback does not explain the empty result");
}
console.log("No-result search feedback passed.");
