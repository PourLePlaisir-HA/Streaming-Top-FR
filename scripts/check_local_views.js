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
  local_playback: {
    enabled: true,
    mode: "vlc_smb",
    players: [
      { id: "salon", name: "Salon" },
      { id: "etage", name: "Étage" },
    ],
  },
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

const playable = card._data.items.find(x => x.local_id === "local:m1");
const vlcControls = card._vlcControls(playable);
if (!vlcControls.includes("Voir avec VLC") || !vlcControls.includes("sur Salon") || !vlcControls.includes("sur Étage")) {
  throw new Error("VLC destination controls failed");
}
card._data.local_playback.enabled = false;
if (card._vlcControls(playable) !== "") {
  throw new Error("VLC controls must be hidden when direct playback is disabled");
}


// v1.0.3: Local Movies are ordered by localized French title. A saga keeps
// one alphabetical position and its members are ordered chronologically.
const sortCard = new LocalCard();
sortCard._category = "movies";
sortCard._familyCategory = "movies";
sortCard._watchFilter = "all";
sortCard._data = {
  family: { enabled: false },
  items: [
    {
      local_id: "local:ij3",
      bucket: "movies",
      media_type: "movie",
      title: "Indiana Jones et la Dernière Croisade",
      parsed_title: "Indiana Jones and the Last Crusade",
      year: 1989,
      relative_path: "Films/Indiana Jones/Indiana.Jones.3.1989.mkv",
    },
    {
      local_id: "local:call",
      bucket: "movies",
      media_type: "movie",
      title: "Dix pour cent : Le film",
      parsed_title: "Call My Agent!",
      year: 2026,
      relative_path: "Films/Call.My.Agent.2026.mkv",
    },
    {
      local_id: "local:ij1",
      bucket: "movies",
      media_type: "movie",
      title: "Les Aventuriers de l'arche perdue",
      parsed_title: "Raiders of the Lost Ark",
      year: 1981,
      relative_path: "Films/Indiana Jones/Indiana.Jones.1.1981.mkv",
    },
    {
      local_id: "local:a",
      bucket: "movies",
      media_type: "movie",
      title: "Avatar",
      year: 2009,
      relative_path: "Films/Avatar.2009.mkv",
    },
    {
      local_id: "local:ij2",
      bucket: "movies",
      media_type: "movie",
      title: "Indiana Jones et le Temple maudit",
      parsed_title: "Indiana Jones and the Temple of Doom",
      year: 1984,
      relative_path: "Films/Indiana Jones/Indiana.Jones.2.1984.mkv",
    },
  ],
};
const sortedMovies = sortCard._displayItems("movies");
const sortedIds = sortedMovies.map(item => item.local_id);
const expectedIds = ["local:a", "local:call", "local:ij1", "local:ij2", "local:ij3"];
if (JSON.stringify(sortedIds) !== JSON.stringify(expectedIds)) {
  throw new Error(`French title / saga chronology sort failed: ${JSON.stringify(sortedIds)}`);
}

console.log("Streaming Local French alphabetical + saga chronology checks passed.");

console.log("Streaming Local Family/watched/VLC view checks passed.");
