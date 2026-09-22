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
  define(name, ctor) { this.defs.set(name, ctor); },
};

require("../custom_components/streaming_top_fr/www/streaming-top-fr-card.js");

const StreamingCard = global.customElements.defs.get("streaming-top-fr-card");
const LocalCard = global.customElements.defs.get("streaming-local-card");
if (!StreamingCard || !LocalCard) throw new Error("Cards not registered");

function fixture(config = {}) {
  const card = new StreamingCard();
  card._config = { ...config };
  card._data = {
    settings: {
      card_layout: {
        rows_small: 2, rows_medium: 2, rows_large: 3,
        posters_par_lot: 8, scroll_infini: false,
      },
      discovery: { visible_count: 3, prefetch_count: 20, max_depth: 100 },
    },
    provider_order: ["netflix"],
    providers: {
      netflix: {
        movies: [
          {media_key:"m1",media_type:"movie",title:"Action One",genres:["action","thriller"],genres_raw:["act","trl"],genre_labels:["Action","Thriller"],genre_source:"justwatch"},
          {media_key:"m2",media_type:"movie",title:"Drama One",genres:["drama"],genres_raw:["drm"],genre_labels:["Drame"],genre_source:"justwatch"},
          {media_key:"m3",media_type:"movie",title:"Action Two",genres:["action","adventure"],genres_raw:["act"],genre_labels:["Action","Aventure"],genre_source:"justwatch"},
          {media_key:"m4",media_type:"movie",title:"Comedy One",genres:["comedy"],genres_raw:["cmy"],genre_labels:["Comédie"],genre_source:"justwatch"},
          {media_key:"m5",media_type:"movie",title:"Thriller Two",genres:["thriller"],genres_raw:["trl"],genre_labels:["Thriller"],genre_source:"justwatch"},
        ],
        tv: [],
      },
    },
    watched_keys: [], watchlist_keys: [], not_interested_keys: [],
    watched: [], watchlist: [], not_interested: [],
  };
  card._provider = "netflix";
  card._media = "movies";
  card._section = "discover";
  card._stfrLayoutWidth = 390;
  card._stfrRendering = true;
  return card;
}

const card = fixture();
const options = card._stfrGenreOptions();
for (const genre of ["action","adventure","comedy","drama","thriller"]) {
  if (!options.includes(genre)) throw new Error(`Missing genre option: ${genre}`);
}

card._stfrGenre = "thriller";
card._stfrLayoutStates = new Map();
let items = card._items();
if (card._stfrLayoutFullCount !== 2 || !items.every(item => item.genres.includes("thriller"))) {
  throw new Error("Thriller filter failed");
}

card._stfrSearchQuery = "two";
card._stfrLayoutStates = new Map();
items = card._items();
if (card._stfrLayoutFullCount !== 1 || items[0]?.title !== "Thriller Two") {
  throw new Error("Genre + title search composition failed");
}

card._stfrSearchQuery = "";
card._stfrGenre = "action";
const state = card._stfrCaptureRefreshState();
card._stfrGenre = "all";
card._stfrRestoreRefreshState(state);
if (card._stfrGenre !== "action") throw new Error("Genre was not restored after refresh");

const disabled = fixture({genre_filter:false});
disabled._stfrGenre = "thriller";
disabled._stfrLayoutStates = new Map();
items = disabled._items();
if (disabled._stfrLayoutFullCount !== 5) {
  throw new Error("genre_filter:false must disable genre filtering");
}

const local = new LocalCard();
local._config = {};
local._stfrGenre = "drama";
const localItems = local._stfrGenreFilter([
  {title:"A",genres:["drama"]},
  {title:"B",genres:["comedy"]},
]);
if (localItems.length !== 1 || localItems[0].title !== "A") {
  throw new Error("Streaming Local genre filter failed");
}

console.log("Transversal genre filtering, composition and persistence passed.");
