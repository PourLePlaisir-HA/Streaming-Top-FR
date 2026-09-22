"use strict";

const fs = require("fs");

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
const CatalogCard = global.customElements.defs.get("streaming-top-fr-catalog-card");
const LocalCard = global.customElements.defs.get("streaming-local-card");

if (!StreamingCard || !CatalogCard || !LocalCard) {
  throw new Error("Streaming Top FR cards are not registered");
}

function streamingFixture() {
  const card = new StreamingCard();
  card._config = { title: "Streaming" };
  card._data = {
    settings: {
      card_layout: {
        rows_small: 2,
        rows_medium: 4,
        rows_large: 3,
        posters_par_lot: 8,
        scroll_infini: false,
      },
      discovery: {
        visible_count: 3,
        prefetch_count: 20,
        max_depth: 100,
      },
      duration_filter: {
        enabled: true,
        max_minutes: 120,
      },
    },
    provider_order: ["netflix"],
    providers: {
      netflix: {
        movies: Array.from({ length: 20 }, (_, index) => ({
          media_key: `movie:${index + 1}`,
          media_type: "movie",
          title: `Film ${index + 1}`,
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
  return card;
}

const streaming = streamingFixture();

if (streaming._stfrLayoutRows(500) !== 2) {
  throw new Error("Small card row setting failed");
}
if (streaming._stfrLayoutRows(900) !== 4) {
  throw new Error("Medium card row setting failed");
}
if (streaming._stfrLayoutRows(1400) !== 3) {
  throw new Error("Large card row setting failed");
}

if (streaming._stfrLayoutColumns(390) !== 2) {
  throw new Error("Mobile column calculation failed");
}
if (streaming._stfrLayoutColumns(850) < 4) {
  throw new Error("Medium card should gain columns");
}
if (streaming._stfrLayoutColumns(1600) < 8) {
  throw new Error("Wide card should gain substantially more columns");
}

if (streaming._stfrBatchSize() !== 8) {
  throw new Error("Default/global batch size failed");
}
if (streaming._stfrInfiniteScroll() !== false) {
  throw new Error("Infinite scroll must be disabled by default");
}

const grid = streaming.getGridOptions();
if (grid.columns !== "full" || grid.min_columns !== 3 || "rows" in grid) {
  throw new Error(`Unexpected Sections grid options: ${JSON.stringify(grid)}`);
}

// Outside rendering, preserve the historical visible_count behavior exactly.
streaming._stfrRendering = false;
if (streaming._items().length !== 3) {
  throw new Error("Historical Streaming visible_count behavior changed");
}

// Manual mode starts at exactly the visible responsive capacity, even though
// the prefetched backend pool is larger. At 390 px: 2 columns x 2 rows = 4.
streaming._stfrRendering = true;
streaming._stfrLayoutWidth = 390;
let rendered = streaming._items();
streaming._stfrRendering = false;
if (rendered.length !== 4) {
  throw new Error(
    `Manual initial render must equal visible capacity (4): ${rendered.length}`
  );
}
if (streaming._stfrLayoutFullCount !== 20) {
  throw new Error("Responsive rendering lost the available prefetched pool size");
}

// Simulate one explicit "Voir 8 de plus" request by updating the per-view
// state. The next render must expose 4 + 8 = 12 items, never more than pool.
const state = streaming._stfrLayoutStates.get(streaming._stfrLayoutKey);
state.expanded = true;
state.limit = Math.min(streaming._stfrLayoutFullCount, state.limit + streaming._stfrBatchSize());
streaming._stfrRendering = true;
rendered = streaming._items();
streaming._stfrRendering = false;
if (rendered.length !== 12) {
  throw new Error(`Manual batch expansion should expose 12 items: ${rendered.length}`);
}

// Per-card Lovelace values must override integration defaults.
const overridden = streamingFixture();
overridden._config = {
  title: "Streaming",
  scroll_infini: true,
  posters_par_lot: 5,
};
if (overridden._stfrInfiniteScroll() !== true) {
  throw new Error("Per-card scroll_infini override failed");
}
if (overridden._stfrBatchSize() !== 5) {
  throw new Error("Per-card posters_par_lot override failed");
}
overridden._stfrRendering = true;
overridden._stfrLayoutWidth = 390;
const infiniteInitial = overridden._items();
overridden._stfrRendering = false;
if (infiniteInitial.length !== 9) {
  throw new Error(
    `Infinite mode should preload capacity + batch (4 + 5): ${infiniteInitial.length}`
  );
}

// Explicit false on the card must win over a true global default.
const explicitFalse = streamingFixture();
explicitFalse._data.settings.card_layout.scroll_infini = true;
explicitFalse._config = { scroll_infini: false };
if (explicitFalse._stfrInfiniteScroll() !== false) {
  throw new Error("Explicit per-card false must override global true");
}

// Batch values are clamped. A value larger than the pool is harmless because
// rendering always slices to the number of titles actually available.
const oversized = streamingFixture();
oversized._config = { posters_par_lot: 999 };
if (oversized._stfrBatchSize() !== 50) {
  throw new Error("Per-card batch upper bound must be 50");
}
oversized._stfrRendering = true;
oversized._stfrLayoutWidth = 390;
oversized._items();
oversized._stfrRendering = false;
const oversizedState = oversized._stfrLayoutStates.get(oversized._stfrLayoutKey);
oversizedState.expanded = true;
oversizedState.limit = Math.min(
  oversized._stfrLayoutFullCount,
  oversizedState.limit + oversized._stfrBatchSize()
);
oversized._stfrRendering = true;
const oversizedRendered = oversized._items();
oversized._stfrRendering = false;
if (oversizedRendered.length !== 20) {
  throw new Error("Oversized batch must stop at the available backend pool");
}

const local = new LocalCard();
local._config = {};
local._data = {
  card_layout: {
    rows_small: 1,
    rows_medium: 2,
    rows_large: 5,
    posters_par_lot: 7,
    scroll_infini: false,
  },
};
if (local._stfrLayoutRows(500) !== 1) {
  throw new Error("Streaming Local small row setting failed");
}
if (local._stfrLayoutRows(900) !== 2) {
  throw new Error("Streaming Local medium row setting failed");
}
if (local._stfrLayoutRows(1400) !== 5) {
  throw new Error("Streaming Local large row setting failed");
}
if (local._stfrBatchSize() !== 7) {
  throw new Error("Streaming Local batch setting failed");
}

const catalog = new CatalogCard();
catalog._config = {};
catalog._data = {
  settings: {
    card_layout: {
      rows_small: 2,
      rows_medium: 2,
      rows_large: 3,
      posters_par_lot: 8,
      scroll_infini: false,
    },
  },
};
if (catalog.getGridOptions().columns !== "full") {
  throw new Error("Top Streaming Sections full-width sizing failed");
}
if (catalog._stfrLayoutRows(1400) !== 3) {
  throw new Error("Top Streaming wide row setting failed");
}
if (catalog._stfrInfiniteScroll() !== false) {
  throw new Error("Top Streaming must inherit global manual loading mode");
}

console.log("Responsive rows, controlled batches and infinite-scroll overrides passed.");


const frontendSource = fs.readFileSync(
  require.resolve("../custom_components/streaming_top_fr/www/streaming-top-fr-card.js"),
  "utf8"
);
if (!frontendSource.includes('class="tabs section-tabs"')) {
  throw new Error("Streaming bucket row is missing section-tabs class");
}
if (!frontendSource.includes(".provider-tabs,.media-tabs,.section-tabs{justify-content:center}")) {
  throw new Error("Centered Streaming buckets CSS is missing");
}
console.log("Centered Streaming buckets on wide cards passed.");
