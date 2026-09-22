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
const CatalogCard = global.customElements.defs.get("streaming-top-fr-catalog-card");
const LocalCard = global.customElements.defs.get("streaming-local-card");

if (!StreamingCard || !CatalogCard || !LocalCard) {
  throw new Error("Streaming Top FR cards are not registered");
}

const streaming = new StreamingCard();
streaming._data = {
  settings: {
    card_layout: {
      rows_small: 2,
      rows_medium: 4,
      rows_large: 3,
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
streaming._provider = "netflix";
streaming._media = "movies";
streaming._section = "discover";

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

const grid = streaming.getGridOptions();
if (grid.columns !== 12 || grid.min_columns !== 3 || "rows" in grid) {
  throw new Error(`Unexpected Sections grid options: ${JSON.stringify(grid)}`);
}

// Outside rendering, preserve the historical visible_count behavior exactly.
streaming._stfrRendering = false;
if (streaming._items().length !== 3) {
  throw new Error("Historical Streaming visible_count behavior changed");
}

// During rendering only, the responsive layer may progressively consume the
// already-prefetched pool. The backend ranking/discovery engine is untouched.
streaming._stfrRendering = true;
streaming._stfrLayoutWidth = 390;
const rendered = streaming._items();
streaming._stfrRendering = false;
if (rendered.length <= 3 || rendered.length >= 20) {
  throw new Error(
    `Lazy rendering did not expose a progressive subset: ${rendered.length}`
  );
}
if (streaming._stfrLayoutFullCount !== 20) {
  throw new Error("Lazy rendering lost the available prefetched pool size");
}

const local = new LocalCard();
local._data = {
  card_layout: {
    rows_small: 1,
    rows_medium: 2,
    rows_large: 5,
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

const catalog = new CatalogCard();
catalog._data = {
  settings: {
    card_layout: {
      rows_small: 2,
      rows_medium: 2,
      rows_large: 3,
    },
  },
};
if (catalog.getGridOptions().columns !== 12) {
  throw new Error("Top Streaming Sections sizing failed");
}
if (catalog._stfrLayoutRows(1400) !== 3) {
  throw new Error("Top Streaming wide row setting failed");
}

console.log("Responsive vertical grid and lazy rendering checks passed.");
