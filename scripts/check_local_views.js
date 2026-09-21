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

const LocalCard = global.customElements.defs.get("streaming-local-card");
if (!LocalCard) throw new Error("streaming-local-card not registered");

const card = new LocalCard();
card._category = "movies";
card._familyCategory = "movies";
card._watchFilter = "all";
card._data = {
  family: {
    enabled: true,
    target_age: 11,
    movies: true,
    series: true,
    animation: true,
  },
  items: [
    {
      local_id: "local:m1",
      media_key: "local:m1",
      bucket: "movies",
      media_type: "movie",
      title: "Film non vu",
      year: 2020,
      watch_state: false,
      family_eligible: true,
      relative_path: "Films/Test/Film non vu.mkv",
    },
    {
      local_id: "local:m2",
      media_key: "local:m2",
      bucket: "movies",
      media_type: "movie",
      title: "Film vu",
      year: 2021,
      watch_state: true,
      family_eligible: true,
      relative_path: "Films/Test/Film vu.mkv",
    },
    {
      local_id: "local:s1e1",
      media_key: "local:s1e1",
      bucket: "series",
      media_type: "tv",
      title: "Série Test",
      franchise_title: "Série Test",
      imdb_id: "tt1234567",
      season: 1,
      episode: 1,
      episodic: true,
      watch_state: true,
      family_eligible: true,
      relative_path: "Series/Série Test/S01E01.mkv",
    },
    {
      local_id: "local:s1e2",
      media_key: "local:s1e2",
      bucket: "series",
      media_type: "tv",
      title: "Série Test",
      franchise_title: "Série Test",
      imdb_id: "tt1234567",
      season: 1,
      episode: 2,
      episodic: true,
      watch_state: false,
      family_eligible: true,
      relative_path: "Series/Série Test/S01E02.mkv",
    },
    {
      local_id: "local:d1",
      media_key: "local:d1",
      bucket: "documentaries",
      media_type: "movie",
      title: "Documentaire",
      year: 2022,
      watch_state: false,
      family_eligible: false,
      relative_path: "Documentaires/Documentaire.mkv",
    },
  ],
};

if (card._displayItems("movies").length !== 2) {
  throw new Error("Movies all bucket failed");
}
card._watchFilter = "watched";
if (card._items().length !== 1 || card._items()[0].title !== "Film vu") {
  throw new Error("Movies watched bucket failed");
}
card._watchFilter = "unwatched";
if (card._items().length !== 1 || card._items()[0].title !== "Film non vu") {
  throw new Error("Movies unwatched bucket failed");
}

card._category = "family";
card._familyCategory = "series";
card._watchFilter = "all";
let seasons = card._displayItems();
if (seasons.length !== 1 || !seasons[0].is_season_group) {
  throw new Error("Family series grouping failed");
}
if (seasons[0].watched_count !== 1 || seasons[0].watch_state !== false) {
  throw new Error("Partial season watched state failed");
}
card._watchFilter = "unwatched";
if (card._items().length !== 1) {
  throw new Error("Partial season must remain in unwatched");
}

card._data.items.find(x => x.local_id === "local:s1e2").watch_state = true;
seasons = card._displayItems();
if (seasons[0].watch_state !== true || seasons[0].watched_count !== 2) {
  throw new Error("Completed season watched state failed");
}
card._watchFilter = "watched";
if (card._items().length !== 1) {
  throw new Error("Completed season must appear in watched");
}

card._familyCategory = "movies";
card._watchFilter = "all";
if (card._items().length !== 2) {
  throw new Error("Family movies filter failed");
}
if (card._familyCategories().includes("documentaries")) {
  throw new Error("Documentaries must not appear in Family subcategories");
}

console.log("Streaming Local Family/watched view checks passed.");
