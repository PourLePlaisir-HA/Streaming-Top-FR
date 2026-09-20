const STFR_VERSION = "0.8.0-beta.3";
class StreamingTopFrCard extends HTMLElement {
  connectedCallback(){
    if(this._statusSyncHandler)return;
    this._statusSyncHandler=e=>{if(e?.detail?.source===this)return;void this._externalStatusRefresh()};
    window.addEventListener("streaming-top-fr-status-changed",this._statusSyncHandler);
  }
  disconnectedCallback(){
    if(this._statusSyncHandler)window.removeEventListener("streaming-top-fr-status-changed",this._statusSyncHandler);
    this._statusSyncHandler=null;
  }
  async _externalStatusRefresh(){if(this._hass&&!this._loading)await this._load()}
  _broadcastStatusChange(){window.dispatchEvent(new CustomEvent("streaming-top-fr-status-changed",{detail:{source:this}}))}
  setConfig(c){
    this._config={title:"Streaming",default_provider:"netflix",default_media:"movies",...c};
    if(!this.shadowRoot)this.attachShadow({mode:"open"});
    this._provider=this._config.default_provider;
    this._media=this._config.default_media;
    this._section="discover";
    this._data=null;this._loading=false;this._error=null;this._render();
  }
  set hass(h){this._hass=h;if(!this._data&&!this._loading)this._load()}
  getCardSize(){return 6}
  async _load(){if(!this._hass)return;this._loading=true;this._render();try{this._data=await this._hass.callWS({type:"streaming_top_fr/get_data"});const order=this._providerOrder();if(order.length&&!order.includes(this._provider))this._provider=order[0];this._error=null}catch(e){this._error=String(e)}finally{this._loading=false;this._render()}}
  async _refresh(){if(!this._hass)return;this._loading=true;this._render();try{await this._hass.callWS({type:"streaming_top_fr/refresh"});await this._load()}catch(e){this._error=String(e);this._loading=false;this._render()}}
  async _set(item,status,enabled){
    const work=this._work(item);
    await this._hass.callWS({type:"streaming_top_fr/set_status",key:work.media_key,status,enabled,item:work});
    await this._load();
    this._broadcastStatusChange();
  }
  _esc(s){return String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;")}
  _watched(){return new Set(this._data?.watched_keys||[])}
  _watchlist(){return new Set(this._data?.watchlist_keys||[])}
  _notInterested(){return new Set(this._data?.not_interested_keys||[])}
  _providerOrder(){const configured=this._data?.provider_order;if(Array.isArray(configured))return configured.filter(x=>this._data?.providers?.[x]);return Object.keys(this._data?.providers||{})}
  _pd(){return this._data?.providers?.[this._provider]||null}
  _selectedMediaType(){return this._media==="movies"?"movie":"tv"}
  _stored(bucket){
    const mt=this._selectedMediaType();
    return(this._data?.[bucket]||[]).map(x=>x.item||{}).filter(x=>x.media_type===mt);
  }
  _items(){
    if(this._section==="watched")return this._stored("watched");
    if(this._section==="watchlist")return this._stored("watchlist");
    if(this._section==="not_interested")return this._stored("not_interested");
    const w=this._watched(),n=this._notInterested();
    const all=(this._pd()?.[this._media]||[]).filter(x=>!w.has(x.media_key)&&!n.has(x.media_key));
    const configured=Number(this._data?.settings?.discovery?.visible_count ?? 10);
    const visible=Number.isFinite(configured)?Math.max(1,Math.floor(configured)):10;
    return all.slice(0,visible);
  }
  _label(id){return{netflix:"Netflix",disney:"Disney+",prime:"Prime Video",hbo_max:"HBO Max",apple_tv:"Apple TV+",paramount:"Paramount+",canal:"CANAL+",crunchyroll:"Crunchyroll",mubi:"MUBI",adn:"ADN"}[id]||this._data?.providers?.[id]?.name||id}
  _providerLogo(id){
    const logos={
      netflix:`<span class="brand-logo brand-netflix" aria-hidden="true"><span class="netflix-n">N</span></span>`,
      disney:`<span class="brand-logo brand-disney" aria-hidden="true"><span class="disney-arc"></span><span class="disney-word">Disney+</span></span>`,
      prime:`<span class="brand-logo brand-prime" aria-hidden="true"><span class="prime-word">prime</span><span class="prime-smile"></span></span>`,
      hbo_max:`<span class="brand-logo brand-word brand-hbomax" aria-hidden="true">HBO&nbsp;Max</span>`,
      apple_tv:`<span class="brand-logo brand-word brand-apple" aria-hidden="true">Apple&nbsp;TV+</span>`,
      paramount:`<span class="brand-logo brand-word brand-paramount" aria-hidden="true">Paramount+</span>`,
      canal:`<span class="brand-logo brand-word brand-canal" aria-hidden="true">CANAL+</span>`,
      crunchyroll:`<span class="brand-logo brand-word brand-crunchy" aria-hidden="true">Crunchyroll</span>`,
      mubi:`<span class="brand-logo brand-word brand-mubi" aria-hidden="true">MUBI</span>`,
      adn:`<span class="brand-logo brand-word brand-adn" aria-hidden="true">ADN</span>`
    };
    return logos[id]||`<span class="brand-logo brand-word">${this._esc(this._label(id))}</span>`;
  }
  _playLabel(id){return{netflix:"Voir sur Netflix",disney:"Voir sur Disney+",prime:"Lancer Prime",hbo_max:"Voir sur HBO Max",apple_tv:"Voir sur Apple TV+",paramount:"Voir sur Paramount+",canal:"Voir sur CANAL+",crunchyroll:"Voir sur Crunchyroll",mubi:"Voir sur MUBI",adn:"Voir sur ADN"}[id]||`Voir sur ${this._label(id)}`}
  _providerPayload(i){
    const provider=String(i?.provider||"").trim();
    if(!provider)return null;
    return{provider,provider_name:i.provider_name||this._label(provider),watch_url:i.watch_url||null,playback_id:i.playback_id||null,details_url:i.details_url||null};
  }
  _mergeWorks(...items){
    const out={};const providers={};let imdbPoster=null;
    for(const src of items){
      if(src?.poster_source==="imdb"&&src?.poster)imdbPoster=src.poster;
      if(!src||typeof src!=="object")continue;
      for(const [k,v] of Object.entries(src)){
        if(k==="providers")continue;
        if(v!==null&&v!==undefined&&v!==""&&!(Array.isArray(v)&&!v.length)&&!(typeof v==="object"&&!Array.isArray(v)&&Object.keys(v).length===0))out[k]=v;
        else if(!(k in out))out[k]=v;
      }
      if(src.providers&&typeof src.providers==="object"){
        for(const [pid,pdata] of Object.entries(src.providers)){
          if(!pid)continue;providers[pid]={...(providers[pid]||{}),...(pdata&&typeof pdata==="object"?pdata:{}),provider:pid};
        }
      }
      const legacy=this._providerPayload(src);
      if(legacy)providers[legacy.provider]={...(providers[legacy.provider]||{}),...legacy};
    }
    out.providers=providers;if(imdbPoster){out.poster=imdbPoster;out.poster_source="imdb"}return out;
  }
  _work(i){
    if(!i?.media_key)return i||{};
    const variants=[];
    Object.values(this._data?.providers||{}).forEach(p=>{
      for(const x of [...(p.movies||[]),...(p.tv||[])])if(x.media_key===i.media_key)variants.push(x);
    });
    for(const b of ["watched","watchlist","not_interested"]){
      for(const row of (this._data?.[b]||[])){const x=row.item||{};if(x.media_key===i.media_key)variants.push(x)}
    }
    variants.push(i);
    return this._mergeWorks(...variants);
  }
  _find(k){
    const current=(this._currentItems||[]).find(x=>x.media_key===k);
    if(current)return current;
    const exact=(this._pd()?.[this._media]||[]).find(x=>x.media_key===k);
    if(exact)return exact;
    for(const b of ["watched","watchlist","not_interested"]){
      const row=(this._data?.[b]||[]).find(x=>x.item?.media_key===k);if(row)return row.item||{};
    }
    let found=null;Object.values(this._data?.providers||{}).some(p=>{found=[...(p.movies||[]),...(p.tv||[])].find(x=>x.media_key===k);return!!found});
    return found;
  }
  _variantForProvider(i,provider){
    const work=this._work(i);const p=work.providers?.[provider]||{};
    return{...work,...p,provider,provider_name:p.provider_name||this._label(provider)};
  }
  _availableProviders(i){
    const work=this._work(i);const enabled=this._providerOrder();const keys=new Set(Object.keys(work.providers||{}));
    if(work.provider)keys.add(work.provider);
    return enabled.filter(x=>keys.has(x));
  }
  _players(){
    const raw=this._data?.settings?.players||{};
    return Object.entries(raw).filter(([,v])=>v&&typeof v==="object").map(([id,v])=>({id,name:v.name||id,type:v.type||"android_tv",media_player:v.media_player||null,remote:v.remote||null,adb_player:v.adb_player||null}));
  }
  _playbackId(i){
    if(i.playback_id)return String(i.playback_id);
    const u=String(i.watch_url||"");
    if(i.provider==="netflix"){const m=u.match(/\/(?:title|watch)\/(\d+)(?:[/?#]|$)/i);return m?m[1]:""}
    if(i.provider==="disney"){const m=u.match(/entity-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i);return m?m[1]:""}
    return "";
  }
  _supportsPlayback(provider){
    const ids=this._data?.playback_providers;return Array.isArray(ids)?ids.includes(provider):["netflix","disney","prime"].includes(provider);
  }
  _canPlay(i){return this._supportsPlayback(i.provider)&&(i.provider==="prime"||i.provider==="disney"||!!this._playbackId(i))}
  async _play(i,provider,playerId,button){
    if(!this._hass)return;
    const variant=this._variantForProvider(i,provider);
    const contentId=this._playbackId(variant);
    if(provider!=="prime"&&provider!=="disney"&&!contentId){if(button){button.innerHTML=`<span class="launching">ID indisponible</span>`;button.disabled=true}return}
    const old=button?.innerHTML;if(button){button.disabled=true;button.innerHTML=`<span class="launching">Lancement…</span>`}
    try{
      const msg={type:"streaming_top_fr/play",provider,player:playerId};
      if(contentId)msg.content_id=contentId;
      if(variant.watch_url)msg.watch_url=String(variant.watch_url);
      if(variant.title)msg.title=String(variant.title);
      if(variant.original_title)msg.original_title=String(variant.original_title);
      if(variant.year!==null&&variant.year!==undefined&&variant.year!=="")msg.year=variant.year;
      if(variant.media_type)msg.media_type=String(variant.media_type);
      await this._hass.callWS(msg);
      this.shadowRoot.querySelector('.modalbg')?.remove();
    }catch(e){if(button){button.disabled=false;button.innerHTML=old||"Réessayer"}this._error=`Lecture: ${String(e)}`}
  }
  _playSections(i){
    const providers=this._availableProviders(i);if(!providers.length)return"";
    const players=this._players();
    return providers.map(provider=>{
      const variant=this._variantForProvider(i,provider);const logo=this._providerLogo(provider);const label=this._playLabel(provider);
      if(!this._supportsPlayback(provider))return`<div class="service-play unavailable"><div class="service-heading"><span class="play-brand">${logo}</span><strong>${this._esc(label)}</strong></div><small>Lancement Home Assistant non encore validé</small></div>`;
      if(!players.length)return`<div class="service-play unavailable"><div class="service-heading"><span class="play-brand">${logo}</span><strong>${this._esc(label)}</strong></div><small>Aucune destination configurée</small></div>`;
      const playable=this._canPlay(variant);const title=playable?"Lancer sur cette destination":"ID de lecture indisponible pour ce titre";
      const buttons=players.map(pl=>`<button class="${this._esc(provider)}" data-play-provider="${this._esc(provider)}" data-player="${this._esc(pl.id)}" ${playable?"":"disabled"} title="${this._esc(title)}${pl.media_player?` · ${this._esc(pl.media_player)}`:""}"><span class="play-brand">${logo}</span><span class="playcopy"><strong>${this._esc(label)}</strong><small>${this._esc(pl.name)}</small></span></button>`).join("");
      return`<div class="service-play"><div class="playrow">${buttons}</div></div>`;
    }).join("");
  }
  _actionButtons(i){
    const w=this._watched().has(i.media_key),l=this._watchlist().has(i.media_key),n=this._notInterested().has(i.media_key);
    if(this._section==="not_interested"){
      return `<button data-act="restore" data-key="${this._esc(i.media_key)}" class="ico restore" title="Remettre dans À découvrir">↩</button><button data-act="watched" data-key="${this._esc(i.media_key)}" class="ico" title="Marquer déjà vu">✓</button>`;
    }
    return `<button data-act="watched" data-key="${this._esc(i.media_key)}" class="ico ${w?"on":""}" title="${w?"Marquer non vu":"Déjà vu"}">✓</button><button data-act="watchlist" data-key="${this._esc(i.media_key)}" class="ico ${l?"on":""}" title="${l?"Retirer de Ma liste":"Ajouter à Ma liste"}">${l?"♥":"♡"}</button><button data-act="not_interested" data-key="${this._esc(i.media_key)}" class="ico reject ${n?"on":""}" title="Pas intéressé">×</button>`;
  }
  _ageFor(i){
    const cfg=this._data?.settings?.classification||{};
    if(cfg.enabled===false)return {value:null,country:null};
    const fr=i.age_fr||(String(i.age_country||"").toUpperCase()==="FR"?i.age_certification:null);
    const us=i.age_us||(String(i.age_country||"").toUpperCase()==="US"?i.age_certification:null);
    if(fr){
      if(cfg.france!==false)return {value:fr,country:"FR"};
      return {value:null,country:null};
    }
    if(cfg.us_fallback!==false&&us){
      const v=String(us).toUpperCase();
      if(v.startsWith("TV-")&&cfg.us_tv===false)return {value:null,country:null};
      return {value:us,country:"US"};
    }
    return {value:null,country:null};
  }
  _ageBadge(value,country){
    const v=String(value||"").trim().toUpperCase();
    const c=String(country||"").trim().toUpperCase();
    if(!v)return "";
    if(c==="FR")return `<span class="age-badge fr" title="Classification France ${this._esc(v)}">${this._esc(v)}</span>`;
    if(c==="US")return `<span class="age-badge us" title="Classification US ${this._esc(v)}">${this._esc(v)}</span>`;
    return "";
  }
  _card(i){
    const rating=i.rating!=null?`★ ${Number(i.rating).toFixed(1)} ${i.rating_source||""}`:"";
    const meta=[i.year,rating,i.days_in_top?`${i.days_in_top}× Top`:""].filter(Boolean).join('<span class="sep">·</span>');
    const rank=(i.rank!==null&&i.rank!==undefined&&Number(i.rank)>0)?`<span class="rank">#${this._esc(i.rank)}</span>`:"";
    return `<article class="mcard" data-key="${this._esc(i.media_key)}"><div class="poster">${i.poster?`<img src="${this._esc(i.poster)}" loading="lazy">`:`<div class="fallback">${this._esc((i.title||"?")[0])}</div>`}${rank}<div class="actions">${this._actionButtons(i)}</div></div><div class="info"><b>${this._esc(i.title)}</b>${i.subtitle?`<small>${this._esc(i.subtitle)}</small>`:""}<em class="meta-line">${meta}</em></div></article>`;
  }
  _render(){
    if(!this.shadowRoot)return;
    const p=this._pd(),items=this._items();
    this._currentItems=items;
    const selectedMediaType=this._selectedMediaType();
    const filt=(bucket)=>(this._data?.[bucket]||[]).filter(x=>x.item?.media_type===selectedMediaType).length;
    const wc=filt("watched"),lc=filt("watchlist"),nc=filt("not_interested");
    let body;
    if(this._loading&&!this._data)body='<div class="state">Chargement…</div>';
    else if(this._error)body=`<div class="state err">${this._esc(this._error)}</div>`;
    else if(this._section==="discover"&&p?.error&&!(p?.[this._media]||[]).length)body=`<div class="state err"><b>Source indisponible</b><br>${this._esc(p.error)}</div>`;
    else if(items.length)body=`<div class="rail">${items.map(i=>this._card(i)).join("")}</div>`;
    else {
      const raw=(p?.[this._media]||[]).length;
      const hidden=wc+nc;
      body=`<div class="state">${this._section==="discover"&&raw>0&&hidden>0?"Tous les titres de ce classement sont déjà classés 🎉":this._section==="discover"?"Aucun titre dans cette rubrique.":"Aucun titre dans cette rubrique."}</div>`;
    }
    const upd=this._data?.updated_at?new Date(this._data.updated_at).toLocaleString("fr-FR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"";
    this.shadowRoot.innerHTML=`<style>:host{display:block}ha-card{overflow:hidden}.wrap{padding:18px}.top{display:flex;align-items:center;gap:12px}.title{font-size:1.2rem;font-weight:850}.updated,.source{color:var(--secondary-text-color);font-size:.72rem}.spacer{flex:1}.refresh{border:0;border-radius:50%;width:38px;height:38px;background:var(--secondary-background-color);color:var(--primary-text-color);font-size:18px;cursor:pointer}.tabs{display:flex;gap:8px;overflow:auto;margin-top:12px;scrollbar-width:none}.provider-tabs,.media-tabs{justify-content:center}.provider-tabs.many{justify-content:flex-start;overflow-x:auto}.tab{border:0;border-radius:999px;padding:9px 14px;font:inherit;font-weight:800;background:var(--secondary-background-color);color:var(--secondary-text-color);white-space:nowrap;cursor:pointer}.tab.active{background:var(--primary-color);color:#fff}.netflix.active{background:#e50914}.disney.active{background:#1535c9}.prime.active{background:#00a8e1;color:#07151c}.count{padding:2px 6px;border-radius:999px;background:rgba(127,127,127,.18);font-size:.68rem}.source{margin:12px 0}.rail{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(155px,175px);gap:13px;overflow-x:auto;padding:2px 2px 12px}.mcard{overflow:hidden;border-radius:18px;background:var(--card-background-color);box-shadow:0 3px 12px rgba(0,0,0,.16);cursor:pointer}.poster{position:relative;aspect-ratio:2/3;background:#222}.poster img,.fallback{width:100%;height:100%;object-fit:cover}.fallback{display:grid;place-items:center;font-size:4rem;font-weight:900;background:linear-gradient(145deg,#343741,#14151a);color:#777}.rank{position:absolute;left:8px;top:8px;padding:5px 8px;border-radius:999px;background:rgba(0,0,0,.78);color:#fff;font-size:.7rem;font-weight:900}.actions{position:absolute;right:8px;top:8px;display:flex;flex-direction:column;gap:6px}.ico{border:0;width:35px;height:35px;border-radius:50%;background:rgba(0,0,0,.76);color:#fff;font-size:17px;cursor:pointer}.ico.on{background:var(--primary-color)}.ico.reject{font-size:23px}.ico.reject.on{background:#b3261e}.ico.restore{font-size:19px;background:#325d3a}.info{padding:10px 11px 12px;min-height:68px}.info b{display:block;line-height:1.2}.info small,.info em{display:block;color:var(--secondary-text-color);font-size:.7rem;margin-top:4px;font-style:normal}.meta-line{display:flex!important;align-items:center;gap:5px;white-space:nowrap;overflow:hidden}.meta-line .sep{opacity:.7}.age-badge{display:inline-grid;place-items:center;flex:0 0 auto;box-sizing:border-box;font-weight:900;line-height:1;vertical-align:middle}.age-badge.fr{width:29px;height:29px;border-radius:50%;background:#d9d9d9!important;color:#111!important;border:0!important;font-size:.66rem;box-shadow:none!important}.age-badge.us{min-width:42px;height:26px;padding:0 7px;border-radius:6px;background:#242424!important;color:#fff!important;border:0!important;font-size:.64rem;letter-spacing:.01em;box-shadow:none!important}.state{padding:34px 8px;text-align:center;color:var(--secondary-text-color);line-height:1.5}.err{color:var(--error-color,#d93025)}.provider-tab{display:inline-flex;align-items:center;justify-content:center;min-width:92px;height:48px;padding:6px 14px}.provider-tab .brand-logo{display:flex;align-items:center;justify-content:center;position:relative;max-width:76px;height:30px;overflow:visible}.brand-netflix{width:32px}.netflix-n{display:block;color:#e50914;font-family:Arial Black,Arial,sans-serif;font-size:31px;font-weight:900;line-height:30px;letter-spacing:-4px;transform:scaleX(.82);transform-origin:center}.brand-disney{width:76px;color:#113ccf}.disney-word{position:relative;z-index:1;display:block;font-family:"Trebuchet MS",Arial,sans-serif;font-size:19px;font-weight:800;font-style:italic;letter-spacing:-1.5px;line-height:30px;white-space:nowrap}.disney-arc{position:absolute;left:7px;right:4px;top:2px;height:13px;border-top:2px solid currentColor;border-radius:60% 60% 0 0;transform:rotate(-7deg)}.brand-prime{width:70px;color:#00a8e1;flex-direction:column;gap:0}.brand-word{display:inline-flex;align-items:center;justify-content:center;width:auto;min-width:62px;max-width:92px;height:28px;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:900;line-height:1;white-space:nowrap;letter-spacing:-.35px}.brand-hbomax{color:#6b38ff}.brand-apple{color:#111}.brand-paramount{color:#1665d8}.brand-canal{color:#111;letter-spacing:-.7px}.brand-crunchy{color:#f47521;font-size:12px}.brand-mubi{color:#111;letter-spacing:1px}.brand-adn{color:#e72b35;font-size:18px}.prime-word{display:block;font-family:Arial,Helvetica,sans-serif;font-size:18px;font-weight:800;line-height:19px;letter-spacing:-.7px}.prime-smile{position:relative;display:block;width:50px;height:8px;border-bottom:2px solid currentColor;border-radius:0 0 60% 60%;transform:translateY(-1px) rotate(-3deg)}.prime-smile:after{content:"";position:absolute;right:-1px;bottom:-4px;width:6px;height:6px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-18deg)}.provider-tab.netflix{color:#e50914}.provider-tab.disney{color:#113ccf}.provider-tab.prime{color:#00a8e1}.provider-tab:not(.active){background:rgba(127,127,127,.12)}.provider-tab:not(.active) .brand-logo{opacity:.58;filter:saturate(.72)}.provider-tab.netflix.active{background:rgba(229,9,20,.14);box-shadow:inset 0 0 0 1px rgba(229,9,20,.28)}.provider-tab.disney.active{background:rgba(17,60,207,.14);box-shadow:inset 0 0 0 1px rgba(17,60,207,.28)}.provider-tab.prime.active{background:rgba(0,168,225,.15);box-shadow:inset 0 0 0 1px rgba(0,168,225,.3)}.provider-tab.hbo_max.active{background:rgba(107,56,255,.14);box-shadow:inset 0 0 0 1px rgba(107,56,255,.3)}.provider-tab.apple_tv.active{background:rgba(20,20,20,.10);box-shadow:inset 0 0 0 1px rgba(20,20,20,.24)}.provider-tab.paramount.active{background:rgba(22,101,216,.14);box-shadow:inset 0 0 0 1px rgba(22,101,216,.28)}.provider-tab.canal.active{background:rgba(20,20,20,.10);box-shadow:inset 0 0 0 1px rgba(20,20,20,.24)}.provider-tab.crunchyroll.active{background:rgba(244,117,33,.14);box-shadow:inset 0 0 0 1px rgba(244,117,33,.3)}.provider-tab.mubi.active{background:rgba(20,20,20,.10);box-shadow:inset 0 0 0 1px rgba(20,20,20,.24)}.provider-tab.adn.active{background:rgba(231,43,53,.14);box-shadow:inset 0 0 0 1px rgba(231,43,53,.28)}.media-tab{display:inline-flex;align-items:center;gap:7px}.media-tab ha-icon{--mdc-icon-size:20px}.modalbg{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:16px;overflow:auto}.modal{position:relative;box-sizing:border-box;width:min(460px,calc(100vw - 32px));max-width:460px;max-height:calc(100dvh - 32px);overflow:auto;padding:20px;border-radius:22px;background:var(--card-background-color)}.modal-close{position:absolute;top:10px;right:10px;width:38px;height:38px;padding:0!important;border-radius:50%!important;display:grid;place-items:center;background:rgba(127,127,127,.18)!important;color:var(--primary-text-color)!important;font-size:25px!important;line-height:1!important;z-index:2}.modal-title-row{display:flex;align-items:center;gap:10px;padding-right:44px;margin:4px 0 12px}.modal-title-row h2{flex:0 1 auto;overflow-wrap:anywhere;padding:0;margin:0}.modal-title-row .age-badge{flex:0 0 auto}.modal-title-row .age-badge.fr{width:30px;height:30px;font-size:.68rem}.modal-title-row .age-badge.us{height:28px;min-width:44px;font-size:.68rem}.modal p{color:var(--secondary-text-color);line-height:1.45;overflow-wrap:anywhere}.modal .buttons{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;align-items:center}.service-play{margin:12px 0 16px}.service-play.unavailable{padding:10px 12px;border-radius:14px;background:var(--secondary-background-color);text-align:center}.service-play.unavailable small{display:block;margin-top:6px;color:var(--secondary-text-color)}.service-heading{display:flex;align-items:center;justify-content:center;gap:8px}.service-heading .play-brand{display:flex;align-items:center;justify-content:center}.service-heading .brand-logo{max-width:70px;height:24px}.playrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:10px 0 0}.playrow button{min-width:0;min-height:76px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;padding:9px 10px!important;color:#fff!important;border:1px solid transparent!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.08);backdrop-filter:blur(8px);text-align:center}.playrow button *{color:#fff!important}.playrow .play-brand{display:flex;align-items:center;justify-content:center;height:22px;margin-bottom:2px}.playrow .play-brand .brand-logo{max-width:62px;height:22px;color:#fff}.playrow .play-brand .netflix-n{color:#fff;font-size:24px;line-height:22px}.playrow .play-brand .disney-word{font-size:15px;line-height:22px;color:#fff}.playrow .play-brand .disney-arc{border-color:#fff;top:0}.playrow .play-brand .prime-word{font-size:14px;line-height:15px;color:#fff}.playrow .play-brand .prime-smile{width:40px;height:6px;border-color:#fff}.playrow .play-brand .prime-smile:after{border-color:#fff}.playrow .playcopy{min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.08;text-align:center;width:100%;transform:translateY(-3px)}.playrow .playcopy strong{font-size:.86rem;white-space:normal;text-align:center;color:#fff!important}.playrow .playcopy small{font-size:.92rem;margin-top:5px;opacity:1;font-weight:900;color:#fff!important}.playrow button.netflix{background:linear-gradient(rgba(229,9,20,.34),rgba(83,0,7,.42)),rgba(14,14,14,.82)!important;border-color:rgba(229,9,20,.55)!important}.playrow button.disney{background:linear-gradient(rgba(17,60,207,.34),rgba(5,18,61,.45)),rgba(10,18,36,.82)!important;border-color:rgba(53,104,235,.55)!important}.playrow button.prime{background:linear-gradient(rgba(0,168,225,.42),rgba(0,93,132,.38)),rgba(10,25,32,.78)!important;border-color:rgba(0,188,235,.58)!important}.playrow button:disabled{opacity:.45;cursor:not-allowed}.modal button,.modal a{box-sizing:border-box;border:0;border-radius:999px;padding:9px 13px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;font-weight:800;text-decoration:none;cursor:pointer}@media(max-width:600px){.wrap{padding:14px 11px}.provider-tabs,.media-tabs{justify-content:center;overflow:visible}.provider-tabs.many{justify-content:flex-start;overflow-x:auto}.rail{grid-auto-columns:minmax(140px,44vw)}.provider-tab{min-width:82px;height:46px;padding:6px 12px}.provider-tab .brand-logo{max-width:70px;height:28px}.provider-tab .disney-word{font-size:18px}.provider-tab .prime-word{font-size:17px}.modalbg{padding:16px}.modal{width:min(360px,calc(100vw - 32px));max-width:calc(100vw - 32px);max-height:calc(100dvh - 32px);padding:14px;border-radius:18px}.modal-close{top:8px;right:8px;width:34px;height:34px;font-size:22px!important}.modal-title-row{gap:8px;padding-right:38px;margin:4px 0 10px}.modal-title-row h2{font-size:1.3rem}.modal-title-row .age-badge.fr{width:27px;height:27px;font-size:.62rem}.modal-title-row .age-badge.us{height:25px;min-width:41px;font-size:.61rem}.modal p{margin:0 0 10px;font-size:.91rem;line-height:1.38}.playrow{gap:8px;margin:12px 0 14px}.playrow button{min-height:72px;padding:8px!important}.playrow .playcopy strong{font-size:.78rem}.playrow .playcopy small{font-size:.9rem}.modal .buttons{gap:7px}.modal .buttons button,.modal .buttons a{padding:8px 11px;font-size:.88rem}}@media(max-width:360px){.playrow{grid-template-columns:1fr}.modal{width:calc(100vw - 24px);max-width:calc(100vw - 24px)}} </style><ha-card><div class="wrap"><div class="top"><div class="title">${this._esc(this._config.title)}</div><div class="updated">${upd}</div><div class="spacer"></div><button class="refresh">${this._loading?"…":"↻"}</button></div><div class="tabs provider-tabs ${this._providerOrder().length>4?"many":""}">${this._providerOrder().map(x=>`<button class="tab provider-tab ${x} ${this._provider===x?"active":""}" data-provider="${x}" title="${this._label(x)}" aria-label="${this._label(x)}">${this._providerLogo(x)}</button>`).join("")}</div><div class="tabs media-tabs"><button class="tab media-tab ${this._media==="movies"?"active":""}" data-media="movies"><ha-icon icon="mdi:filmstrip"></ha-icon><span>Films</span></button><button class="tab media-tab ${this._media==="tv"?"active":""}" data-media="tv"><ha-icon icon="mdi:television-play"></ha-icon><span>Séries</span></button></div><div class="tabs"><button class="tab ${this._section==="discover"?"active":""}" data-section="discover">À découvrir</button><button class="tab ${this._section==="watchlist"?"active":""}" data-section="watchlist">Ma liste <span class="count">${lc}</span></button><button class="tab ${this._section==="watched"?"active":""}" data-section="watched">Déjà vus <span class="count">${wc}</span></button><button class="tab ${this._section==="not_interested"?"active":""}" data-section="not_interested">Pas intéressé <span class="count">${nc}</span></button></div><div class="source">${this._section==="discover"?`${this._esc(p?.source_label||"")}${p?.week?` · semaine ${this._esc(p.week)}`:""}`:"Bibliothèque globale · toutes plateformes activées"}</div>${body}</div></ha-card>`;
    this._bind();
  }
  _bind(){
    const r=this.shadowRoot;
    r.querySelector('.refresh')?.addEventListener('click',()=>this._refresh());
    r.querySelectorAll('[data-provider]').forEach(b=>b.onclick=()=>{this._provider=b.dataset.provider;this._render()});
    r.querySelectorAll('[data-media]').forEach(b=>b.onclick=()=>{this._media=b.dataset.media;this._render()});
    r.querySelectorAll('[data-section]').forEach(b=>b.onclick=()=>{this._section=b.dataset.section;this._render()});
    r.querySelectorAll('.ico').forEach(b=>b.onclick=async e=>{
      e.stopPropagation();const i=this._find(b.dataset.key);if(!i)return;
      if(b.dataset.act==='watched')await this._set(i,'watched',!this._watched().has(i.media_key));
      else if(b.dataset.act==='watchlist')await this._set(i,'watchlist',!this._watchlist().has(i.media_key));
      else if(b.dataset.act==='not_interested')await this._set(i,'not_interested',true);
      else if(b.dataset.act==='restore')await this._set(i,'not_interested',false);
    });
    r.querySelectorAll('.mcard').forEach(c=>c.onclick=()=>{const i=this._find(c.dataset.key);if(i)this._detail(i)});
  }
  _detail(i){
    this.shadowRoot.querySelector('.modalbg')?.remove();
    i=this._work(i);
    const w=this._watched().has(i.media_key),l=this._watchlist().has(i.media_key),n=this._notInterested().has(i.media_key),m=document.createElement('div');
    const disposition=n?`<button data-a="restore">↩ Remettre dans le flow</button><button data-a="watched">✓ Déjà vu</button>`:`<button data-a="watched">${w?"↩ Pas vu":"✓ Déjà vu"}</button><button data-a="watchlist">${l?"♥ Retirer":"♡ Ma liste"}</button><button data-a="not_interested">× Pas intéressé</button>`;
    const playBlock=this._playSections(i);
    const age=this._ageFor(i);
    const ageBadge=this._ageBadge(age.value,age.country);
    m.className='modalbg';m.innerHTML=`<div class="modal"><button class="modal-close" data-a="close" aria-label="Fermer" title="Fermer">×</button><div class="modal-title-row"><h2>${this._esc(i.title)}</h2>${ageBadge}</div><p>${this._esc(i.description||"Pas de synopsis disponible pour le moment.")}</p>${playBlock}<div class="buttons">${disposition}</div></div>`;
    m.onclick=e=>{if(e.target===m)m.remove()};
    m.querySelector('[data-a="close"]').onclick=()=>m.remove();
    m.querySelectorAll('[data-play-provider]').forEach(b=>b.addEventListener('click',async e=>{e.stopPropagation();await this._play(i,b.dataset.playProvider,b.dataset.player,b)}));
    m.querySelector('[data-a="watched"]')?.addEventListener('click',async()=>{m.remove();await this._set(i,'watched',n?true:!w)});
    m.querySelector('[data-a="watchlist"]')?.addEventListener('click',async()=>{m.remove();await this._set(i,'watchlist',!l)});
    m.querySelector('[data-a="not_interested"]')?.addEventListener('click',async()=>{m.remove();await this._set(i,'not_interested',true)});
    m.querySelector('[data-a="restore"]')?.addEventListener('click',async()=>{m.remove();await this._set(i,'not_interested',false)});
    this.shadowRoot.appendChild(m);
  }}
customElements.define('streaming-top-fr-card',StreamingTopFrCard);

class StreamingTopFrCatalogCard extends StreamingTopFrCard {
  setConfig(c){
    const hasLocalDefaultDecade=Object.prototype.hasOwnProperty.call(c||{},"default_decade");
    this._config={title:"Top Streaming",default_category:"movies",default_family_category:"movies",...c};
    this._configuredDefaultDecade=hasLocalDefaultDecade?String(c.default_decade):null;
    if(!this.shadowRoot)this.attachShadow({mode:"open"});
    this._decade=this._configuredDefaultDecade||"1990";
    this._defaultDecadeApplied=false;
    this._category=String(this._config.default_category||"movies");
    this._familyType=String(this._config.default_family_category||"movies");
    this._familyCache={};this._familyLoadingKey=null;this._familyError={};
    this._data=null;this._loading=false;this._error=null;this._render();
  }
  getCardSize(){return 6}
  async _load(){
    await super._load();
    if(!this._defaultDecadeApplied){
      const globalDefault=String(this._data?.settings?.top_catalog?.default_decade||"");
      this._decade=this._configuredDefaultDecade||globalDefault||this._decade||"1990";
      this._defaultDecadeApplied=true;
    }
    this._normalizeCatalogSelection();
    if(this._category==="family")await this._loadFamily();
    this._render();
  }
  async _refresh(){
    this._familyCache={};this._familyError={};this._familyLoadingKey=null;
    if(!this._configuredDefaultDecade)this._defaultDecadeApplied=false;
    await super._refresh();
  }
  _catalog(){return this._data?.top_catalog||null}
  _decadeOrder(){const v=this._catalog()?.decade_order;return Array.isArray(v)?v.map(String):[]}
  _decadeData(decade=this._decade){return this._catalog()?.decades?.[String(decade)]||null}
  _familySettings(){return this._data?.settings?.family||{enabled:true,target_age:11,allow_unrated:false,movies:true,animation:true,series:true}}
  _standardCategories(decade=this._decade){
    const d=this._decadeData(decade);if(!d)return[];
    const configured=this._catalog()?.category_order||["movies","animation","series"];
    return configured.filter(x=>["movies","animation","series"].includes(x)&&d?.categories?.[x]);
  }
  _familyTypes(decade=this._decade){
    const family=this._familySettings();if(family.enabled===false)return[];
    return this._standardCategories(decade).filter(x=>family?.[x]!==false);
  }
  _categories(decade=this._decade){
    const base=this._standardCategories(decade);
    if(this._familyTypes(decade).length)base.push("family");
    return base;
  }
  _normalizeCatalogSelection(){
    const decades=this._decadeOrder();
    if(decades.length&&!decades.includes(String(this._decade)))this._decade=decades.includes("1990")?"1990":decades[0];
    const cats=this._categories();
    if(cats.length&&!cats.includes(this._category))this._category=cats[0];
    const familyTypes=this._familyTypes();
    if(familyTypes.length&&!familyTypes.includes(this._familyType))this._familyType=familyTypes[0];
  }
  _familyKey(){return`${this._decade}:${this._familyType}`}
  _familyBranch(){return this._familyCache?.[this._familyKey()]||null}
  _catalogBranch(){return this._category==="family"?this._familyBranch():this._decadeData()?.categories?.[this._category]||null}
  _catalogItems(){
    const w=this._watched(),n=this._notInterested();
    return(this._catalogBranch()?.items||[]).filter(i=>!w.has(i.media_key)&&!n.has(i.media_key)).map((i,index)=>({...i,rank:index+1}));
  }
  _categoryLabel(id){return{movies:"Films",animation:"Animation",series:"Séries",family:"Famille"}[id]||id}
  _categoryIcon(id){return{movies:"mdi:filmstrip",animation:"mdi:creation",series:"mdi:television-play",family:"mdi:account-group"}[id]||"mdi:movie-open"}
  async _externalStatusRefresh(){
    this._familyCache={};this._familyError={};this._familyLoadingKey=null;
    await super._externalStatusRefresh();
  }
  async _set(item,status,enabled){
    if(!this._hass)return;
    const work=this._work(item);
    await this._hass.callWS({type:"streaming_top_fr/set_status",key:work.media_key,status,enabled,item:work});
    if(status==="watched"||status==="not_interested"){
      this._familyCache={};this._familyError={};this._familyLoadingKey=null;
    }
    await this._load();
    this._broadcastStatusChange();
  }
  async _loadFamily(force=false){
    if(!this._hass||this._category!=="family")return;
    const key=this._familyKey();
    if(!force&&this._familyCache[key])return;
    if(this._familyLoadingKey===key)return;
    this._familyLoadingKey=key;delete this._familyError[key];this._render();
    try{
      const result=await this._hass.callWS({type:"streaming_top_fr/get_family_catalog",decade:Number(this._decade),category:this._familyType});
      this._familyCache[key]=result||{items:[]};delete this._familyError[key];
    }catch(e){this._familyError[key]=String(e)}finally{if(this._familyLoadingKey===key)this._familyLoadingKey=null;this._render()}
  }
  async _detail(i){
    let item=i;
    const cfg=this._data?.settings?.classification||{};
    const needsAge=cfg.enabled!==false&&!item?.age_fr&&!item?.age_us&&!item?.age_certification;
    const needsPoster=item?.poster_source!=="imdb";
    if((needsAge||needsPoster)&&this._hass){
      try{
        const enriched=await this._hass.callWS({type:"streaming_top_fr/enrich_item",item});
        if(enriched&&typeof enriched==="object"){
          item={...item,...enriched};
          const idx=(this._currentItems||[]).findIndex(x=>x.media_key===item.media_key);
          if(idx>=0)this._currentItems[idx]=item;
        }
      }catch(e){/* classification is optional; open the popup anyway */}
    }
    return super._detail(item);
  }
  _catalogCard(i){
    const rating=i.rating!=null?`★ ${Number(i.rating).toFixed(1)} IMDb`:"";
    const votes=Number(i.imdb_votes||0);
    const voteText=votes>=1000000?`${(votes/1000000).toFixed(votes>=10000000?0:1).replace(".0","")} M votes`:votes>=1000?`${Math.round(votes/1000)} k votes`:votes?`${votes} votes`:"";
    const meta=[i.year,rating,voteText].filter(Boolean).join('<span class="sep">·</span>');
    const rank=(i.rank!==null&&i.rank!==undefined&&Number(i.rank)>0)?`<span class="rank">#${this._esc(i.rank)}</span>`:"";
    return `<article class="mcard" data-key="${this._esc(i.media_key)}"><div class="poster">${i.poster?`<img src="${this._esc(i.poster)}" loading="lazy">`:`<div class="fallback">${this._esc((i.title||"?")[0])}</div>`}${rank}<div class="actions">${this._actionButtons(i)}</div></div><div class="info"><b>${this._esc(i.title)}</b><em class="meta-line">${meta}</em></div></article>`;
  }
  _bindCatalog(){
    const r=this.shadowRoot;
    r.querySelector('.refresh')?.addEventListener('click',()=>this._refresh());
    r.querySelectorAll('[data-decade]').forEach(b=>b.onclick=async()=>{this._decade=b.dataset.decade;this._normalizeCatalogSelection();this._render();if(this._category==="family")await this._loadFamily()});
    r.querySelectorAll('[data-category]').forEach(b=>b.onclick=async()=>{this._category=b.dataset.category;this._normalizeCatalogSelection();this._render();if(this._category==="family")await this._loadFamily()});
    r.querySelectorAll('[data-family-type]').forEach(b=>b.onclick=async()=>{this._familyType=b.dataset.familyType;this._render();await this._loadFamily()});
    r.querySelectorAll('.ico').forEach(b=>b.onclick=async e=>{
      e.stopPropagation();const i=this._find(b.dataset.key);if(!i)return;
      if(b.dataset.act==='watched')await this._set(i,'watched',!this._watched().has(i.media_key));
      else if(b.dataset.act==='watchlist')await this._set(i,'watchlist',!this._watchlist().has(i.media_key));
      else if(b.dataset.act==='not_interested')await this._set(i,'not_interested',true);
      else if(b.dataset.act==='restore')await this._set(i,'not_interested',false);
    });
    r.querySelectorAll('.mcard').forEach(c=>c.onclick=()=>{const i=this._find(c.dataset.key);if(i)this._detail(i)});
  }
  _render(){
    if(!this.shadowRoot)return;
    this._normalizeCatalogSelection();
    const catalog=this._catalog();const decades=this._decadeOrder();const cats=this._categories();const branch=this._catalogBranch();
    const items=this._catalogItems();this._currentItems=items;
    const familyTypes=this._familyTypes();const familyKey=this._familyKey();const familyLoading=this._category==="family"&&this._familyLoadingKey===familyKey;
    let body;
    if(this._loading&&!this._data)body='<div class="state">Chargement du classement…</div>';
    else if(this._error)body=`<div class="state err">${this._esc(this._error)}</div>`;
    else if(catalog?.enabled===false)body='<div class="state">La carte Top Streaming est désactivée dans streaming_top_fr.yaml.</div>';
    else if(!decades.length)body=`<div class="state">${this._esc(catalog?.error||"Aucune décennie activée dans la configuration.")}</div>`;
    else if(this._category==="family"&&familyLoading&&!items.length)body='<div class="state">Recherche des contenus Famille et vérification des classifications d’âge…</div>';
    else if(this._category==="family"&&this._familyError[familyKey]&&!items.length)body=`<div class="state err"><b>Filtre Famille indisponible</b><br>${this._esc(this._familyError[familyKey])}</div>`;
    else if(branch?.error&&!items.length)body=`<div class="state err"><b>Classement indisponible</b><br>${this._esc(branch.error)}</div>`;
    else if(items.length)body=`<div class="rail">${items.map(i=>this._catalogCard(i)).join("")}</div>`;
    else body='<div class="state">Aucun titre disponible pour cette sélection.</div>';
    const upd=this._data?.updated_at?new Date(this._data.updated_at).toLocaleString("fr-FR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"";
    const topCount=this._decadeData()?.top_count||"";
    const family=this._familySettings();
    const source=this._category==="family"?`Famille · âge cible ${family.target_age??11} ans · FR prioritaire${(this._data?.settings?.classification?.us_fallback!==false)?" · US fallback":""}`:(catalog?.source_label||"Popularité FR → qualité IMDb · disponibilité JustWatch France");
    const familyTabs=`<div class="tabs family-tabs ${this._category==="family"?"":"reserved"}" ${this._category==="family"?"":'aria-hidden="true"'}>${this._category==="family"?familyTypes.map(c=>`<button class="tab family-tab ${this._familyType===c?"active":""}" data-family-type="${this._esc(c)}"><ha-icon icon="${this._categoryIcon(c)}"></ha-icon><span>${this._esc(this._categoryLabel(c))}</span></button>`).join(""):""}</div>`;
    this.shadowRoot.innerHTML=`<style>
:host{display:block}ha-card{overflow:hidden}.wrap{padding:18px}.top{display:flex;align-items:center;gap:12px}.title{font-size:1.2rem;font-weight:850}.updated,.source{color:var(--secondary-text-color);font-size:.72rem}.spacer{flex:1}.refresh{border:0;border-radius:50%;width:38px;height:38px;background:var(--secondary-background-color);color:var(--primary-text-color);font-size:18px;cursor:pointer}.tabs{display:flex;gap:8px;overflow:auto;margin-top:12px;scrollbar-width:none}.decade-tabs,.category-tabs,.family-tabs{justify-content:center}.tab{border:0;border-radius:999px;padding:9px 14px;font:inherit;font-weight:800;background:var(--secondary-background-color);color:var(--secondary-text-color);white-space:nowrap;cursor:pointer}.tab.active{background:var(--primary-color);color:#fff}.category-tab,.family-tab{display:inline-flex;align-items:center;gap:7px}.category-tab ha-icon,.family-tab ha-icon{--mdc-icon-size:20px}.family-tabs{margin-top:8px;min-height:38px}.family-tabs.reserved{visibility:hidden;pointer-events:none}.family-tab{padding:7px 12px;font-size:.88rem}.source{margin:12px 0}.rail{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(155px,175px);gap:13px;overflow-x:auto;padding:2px 2px 12px}.mcard{overflow:hidden;border-radius:18px;background:var(--card-background-color);box-shadow:0 3px 12px rgba(0,0,0,.16);cursor:pointer}.poster{position:relative;aspect-ratio:2/3;background:#222}.poster img,.fallback{width:100%;height:100%;object-fit:cover}.fallback{display:grid;place-items:center;font-size:4rem;font-weight:900;background:linear-gradient(145deg,#343741,#14151a);color:#777}.rank{position:absolute;left:8px;top:8px;padding:5px 8px;border-radius:999px;background:rgba(0,0,0,.78);color:#fff;font-size:.7rem;font-weight:900}.actions{position:absolute;right:8px;top:8px;display:flex;flex-direction:column;gap:6px}.ico{border:0;width:35px;height:35px;border-radius:50%;background:rgba(0,0,0,.76);color:#fff;font-size:17px;cursor:pointer}.ico.on{background:var(--primary-color)}.ico.reject{font-size:23px}.ico.reject.on{background:#b3261e}.ico.restore{font-size:19px;background:#325d3a}.info{padding:10px 11px 12px;min-height:68px}.info b{display:block;line-height:1.2}.info em{display:block;color:var(--secondary-text-color);font-size:.7rem;margin-top:4px;font-style:normal}.meta-line{display:flex!important;align-items:center;gap:5px;white-space:nowrap;overflow:hidden}.meta-line .sep{opacity:.7}.state{padding:34px 8px;text-align:center;color:var(--secondary-text-color);line-height:1.5}.err{color:var(--error-color,#d93025)}
.age-badge{display:inline-grid;place-items:center;flex:0 0 auto;box-sizing:border-box;font-weight:900;line-height:1;vertical-align:middle}.age-badge.fr{width:29px;height:29px;border-radius:50%;background:#d9d9d9!important;color:#111!important;border:0!important;font-size:.66rem}.age-badge.us{min-width:42px;height:26px;padding:0 7px;border-radius:6px;background:#242424!important;color:#fff!important;border:0!important;font-size:.64rem}
.brand-logo{display:flex;align-items:center;justify-content:center;position:relative;max-width:76px;height:30px;overflow:visible}.brand-netflix{width:32px}.netflix-n{display:block;color:#e50914;font-family:Arial Black,Arial,sans-serif;font-size:31px;font-weight:900;line-height:30px;letter-spacing:-4px;transform:scaleX(.82)}.brand-disney{width:76px;color:#113ccf}.disney-word{position:relative;z-index:1;display:block;font-family:"Trebuchet MS",Arial,sans-serif;font-size:19px;font-weight:800;font-style:italic;letter-spacing:-1.5px;line-height:30px;white-space:nowrap}.disney-arc{position:absolute;left:7px;right:4px;top:2px;height:13px;border-top:2px solid currentColor;border-radius:60% 60% 0 0;transform:rotate(-7deg)}.brand-prime{width:70px;color:#00a8e1;flex-direction:column}.brand-word{display:inline-flex;align-items:center;justify-content:center;width:auto;min-width:62px;max-width:92px;height:28px;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:900;white-space:nowrap}.brand-hbomax{color:#6b38ff}.brand-apple{color:#111}.brand-paramount{color:#1665d8}.brand-canal{color:#111}.brand-crunchy{color:#f47521;font-size:12px}.brand-mubi{color:#111}.brand-adn{color:#e72b35;font-size:18px}.prime-word{display:block;font-family:Arial,Helvetica,sans-serif;font-size:18px;font-weight:800;line-height:19px}.prime-smile{position:relative;display:block;width:50px;height:8px;border-bottom:2px solid currentColor;border-radius:0 0 60% 60%;transform:translateY(-1px) rotate(-3deg)}.prime-smile:after{content:"";position:absolute;right:-1px;bottom:-4px;width:6px;height:6px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(-18deg)}
.modalbg{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:16px;overflow:auto}.modal{position:relative;box-sizing:border-box;width:min(460px,calc(100vw - 32px));max-width:460px;max-height:calc(100dvh - 32px);overflow:auto;padding:20px;border-radius:22px;background:var(--card-background-color)}.modal-close{position:absolute;top:10px;right:10px;width:38px;height:38px;padding:0!important;border-radius:50%!important;display:grid;place-items:center;background:rgba(127,127,127,.18)!important;color:var(--primary-text-color)!important;font-size:25px!important;line-height:1!important;z-index:2}.modal-title-row{display:flex;align-items:center;gap:10px;padding-right:44px;margin:4px 0 12px}.modal-title-row h2{flex:0 1 auto;overflow-wrap:anywhere;padding:0;margin:0}.modal-title-row .age-badge{flex:0 0 auto}.modal p{color:var(--secondary-text-color);line-height:1.45;overflow-wrap:anywhere}.modal .buttons{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;align-items:center}.service-play{margin:12px 0 16px}.service-play.unavailable{padding:10px 12px;border-radius:14px;background:var(--secondary-background-color);text-align:center}.service-play.unavailable small{display:block;margin-top:6px;color:var(--secondary-text-color)}.service-heading{display:flex;align-items:center;justify-content:center;gap:8px}.playrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:10px 0 0}.playrow button{min-width:0;min-height:76px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;padding:9px 10px!important;color:#fff!important;border:1px solid transparent!important;box-shadow:inset 0 1px 0 rgba(255,255,255,.08);backdrop-filter:blur(8px);text-align:center}.playrow button *{color:#fff!important}.playrow .play-brand{display:flex;align-items:center;justify-content:center;height:22px;margin-bottom:2px}.playrow .play-brand .brand-logo{max-width:62px;height:22px;color:#fff}.playrow .play-brand .netflix-n{color:#fff;font-size:24px;line-height:22px}.playrow .play-brand .disney-word{font-size:15px;line-height:22px;color:#fff}.playrow .play-brand .disney-arc{border-color:#fff;top:0}.playrow .play-brand .prime-word{font-size:14px;line-height:15px;color:#fff}.playrow .play-brand .prime-smile{width:40px;height:6px;border-color:#fff}.playrow .play-brand .prime-smile:after{border-color:#fff}.playrow .playcopy{min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.08;text-align:center;width:100%;transform:translateY(-3px)}.playrow .playcopy strong{font-size:.86rem;white-space:normal;text-align:center;color:#fff!important}.playrow .playcopy small{font-size:.92rem;margin-top:5px;opacity:1;font-weight:900;color:#fff!important}.playrow button.netflix{background:linear-gradient(rgba(229,9,20,.34),rgba(83,0,7,.42)),rgba(14,14,14,.82)!important;border-color:rgba(229,9,20,.55)!important}.playrow button.disney{background:linear-gradient(rgba(17,60,207,.34),rgba(5,18,61,.45)),rgba(10,18,36,.82)!important;border-color:rgba(53,104,235,.55)!important}.playrow button.prime{background:linear-gradient(rgba(0,168,225,.42),rgba(0,93,132,.38)),rgba(10,25,32,.78)!important;border-color:rgba(0,188,235,.58)!important}.playrow button:disabled{opacity:.45;cursor:not-allowed}.modal button,.modal a{box-sizing:border-box;border:0;border-radius:999px;padding:9px 13px;background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit;font-weight:800;text-decoration:none;cursor:pointer}
@media(max-width:600px){.wrap{padding:14px 11px}.decade-tabs,.category-tabs,.family-tabs{justify-content:flex-start;overflow-x:auto}.rail{grid-auto-columns:minmax(140px,44vw)}.modalbg{padding:16px}.modal{width:min(360px,calc(100vw - 32px));max-width:calc(100vw - 32px);max-height:calc(100dvh - 32px);padding:14px;border-radius:18px}.modal-close{top:8px;right:8px;width:34px;height:34px;font-size:22px!important}.modal-title-row{gap:8px;padding-right:38px;margin:4px 0 10px}.modal-title-row h2{font-size:1.3rem}.playrow{gap:8px}.playrow button{min-height:72px;padding:8px!important}}@media(max-width:360px){.playrow{grid-template-columns:1fr}.modal{width:calc(100vw - 24px);max-width:calc(100vw - 24px)}}
</style><ha-card><div class="wrap"><div class="top"><div class="title">${this._esc(this._config.title)}</div><div class="updated">${upd}</div><div class="spacer"></div><button class="refresh">${this._loading?"…":"↻"}</button></div><div class="tabs decade-tabs">${decades.map(d=>`<button class="tab ${String(this._decade)===String(d)?"active":""}" data-decade="${this._esc(d)}">${this._esc(d)}</button>`).join("")}</div><div class="tabs category-tabs">${cats.map(c=>`<button class="tab category-tab ${this._category===c?"active":""}" data-category="${this._esc(c)}"><ha-icon icon="${this._categoryIcon(c)}"></ha-icon><span>${this._esc(this._categoryLabel(c))}</span></button>`).join("")}</div>${familyTabs}<div class="source">${topCount?`Top ${this._esc(topCount)} · `:""}${this._esc(source)}</div>${body}</div></ha-card>`;
    this._bindCatalog();
  }
}
customElements.define('streaming-top-fr-catalog-card',StreamingTopFrCatalogCard);


class StreamingLocalCard extends HTMLElement {
  setConfig(c){
    this._config={title:"Streaming Local",default_category:"movies",...c};
    if(!this.shadowRoot)this.attachShadow({mode:"open"});
    this._category=String(this._config.default_category||"movies");
    this._data=null;this._loading=false;this._enriching=false;this._error=null;
    this._render();
  }
  set hass(h){
    this._hass=h;
    if(!this._data&&!this._loading)this._load(false);
  }
  getCardSize(){return 6}
  _esc(s){return String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;")}
  _categories(){
    // Keep all library sections visible, even when a category currently has
    // zero items. This makes scan/classification problems immediately visible
    // instead of silently hiding the missing category.
    return ["movies","series","animation","documentaries"];
  }
  _label(cat){return{movies:"Films",series:"Séries",animation:"Animation",documentaries:"Documentaires"}[cat]||cat}
  _icon(cat){return{movies:"mdi:filmstrip",series:"mdi:television-play",animation:"mdi:creation",documentaries:"mdi:earth"}[cat]||"mdi:movie-open"}
  _rawItems(category=this._category){
    return(this._data?.items||[]).filter(i=>i.bucket===category)
  }
  _seriesGroups(){
    const groups=new Map();
    for(const item of this._rawItems("series")){
      const fallbackTitle=String(item.parsed_title||item.title||item.filename||"").trim().toLocaleLowerCase("fr");
      const key=String(item.imdb_id||item.canonical_media_key||`series:${fallbackTitle}`).trim();
      if(!groups.has(key))groups.set(key,[]);
      groups.get(key).push(item);
    }
    const out=[];
    for(const [key,episodes] of groups.entries()){
      episodes.sort((a,b)=>
        Number(a.season??0)-Number(b.season??0)||
        Number(a.episode??0)-Number(b.episode??0)||
        String(a.relative_path||"").localeCompare(String(b.relative_path||""),"fr")
      );
      const representative=
        episodes.find(i=>i.poster&&i.rating!=null)||
        episodes.find(i=>i.poster)||
        episodes.find(i=>i.metadata_status==="matched")||
        episodes[0];
      const seasons=[...new Set(episodes.map(i=>Number(i.season??0)))].sort((a,b)=>a-b);
      out.push({
        ...representative,
        is_series_group:true,
        series_key:key,
        episodes,
        seasons,
        episode_count:episodes.length,
        season_count:seasons.length,
        season:null,
        episode:null,
        filename:null,
        relative_path:null,
        smb_uri:null,
      });
    }
    return out.sort((a,b)=>String(a.title||a.parsed_title||"").localeCompare(String(b.title||b.parsed_title||""),"fr"));
  }
  _items(){return this._category==="series"?this._seriesGroups():this._rawItems()}
  _categoryCount(cat){return cat==="series"?this._seriesGroups().length:this._rawItems(cat).length}
  _normalizeCategory(){
    const cats=this._categories();
    if(cats.length&&!cats.includes(this._category))this._category=cats[0];
  }
  async _load(refresh=false){
    if(!this._hass||this._loading)return;
    this._loading=true;this._error=null;this._render();
    try{
      this._data=await this._hass.callWS({type:"streaming_top_fr/get_local_library",refresh:Boolean(refresh)});
      this._normalizeCategory();
    }catch(e){this._error=String(e)}
    finally{this._loading=false;this._render()}
    if(this._data?.enabled&&this._data?.count>0&&!this._data?.metadata_complete&&!this._enriching){
      void this._enrich();
    }
  }
  async _enrich(){
    if(!this._hass||this._enriching)return;
    this._enriching=true;this._render();
    let retry=false;
    try{
      const result=await this._hass.callWS({type:"streaming_top_fr/enrich_local_library"});
      const currentRevision=Number(this._data?.scan_revision||0);
      const resultRevision=Number(result?.scan_revision||0);

      // Never let an enrichment started from an older filesystem snapshot
      // restore files that a later rescan has already removed or moved.
      if(resultRevision&&currentRevision&&resultRevision<currentRevision){
        retry=Boolean(this._data?.enabled&&this._data?.count>0&&!this._data?.metadata_complete);
      }else{
        this._data={...(this._data||{}),...(result||{})};
        this._normalizeCategory();
        this._error=null;
        retry=Boolean(result?.stale&&this._data?.enabled&&this._data?.count>0&&!this._data?.metadata_complete);
      }
    }catch(e){this._error=String(e)}
    finally{
      this._enriching=false;this._render();
      if(retry)void this._enrich();
    }
  }
  async _refresh(){await this._load(true)}
  _metadata(item){
    const parts=[];
    if(item.is_series_group){
      if(item.year)parts.push(String(item.year));
    }else if(item.media_type==="tv"&&item.season!=null&&item.episode!=null){
      parts.push(`S${String(item.season).padStart(2,"0")}E${String(item.episode).padStart(2,"0")}`);
    }else if(item.year){parts.push(String(item.year))}
    if(item.rating!=null){
      const n=Number(item.rating);
      parts.push(`★ ${Number.isFinite(n)?n.toFixed(1):this._esc(item.rating)}`);
    }
    if(item.age_certification)parts.push(String(item.age_certification));
    return parts.join(" · ");
  }
  _status(item){
    if(item.metadata_status==="matched")return "";
    if(item.metadata_status==="imdb_only")return '<span class="match imdb">IMDb</span>';
    if(item.metadata_status==="unmatched")return '<span class="match unmatched">À identifier</span>';
    return this._enriching?'<span class="match pending">Analyse…</span>':'';
  }
  _tile(item,index){
    const poster=item.poster
      ?`<img src="${this._esc(item.poster)}" alt="${this._esc(item.title||item.filename||"")}" loading="lazy">`
      :'<div class="poster-fallback"><ha-icon icon="mdi:movie-open-outline"></ha-icon></div>';
    const meta=this._metadata(item);
    const title=item.title||item.parsed_title||item.filename||"Sans titre";
    const seriesExtra=item.is_series_group
      ?`${item.season_count} saison${item.season_count>1?"s":""} · ${item.episode_count} épisode${item.episode_count>1?"s":""}`
      :"";
    return `<button class="media" data-index="${index}" title="${this._esc(item.filename||title)}">
      <div class="poster">${poster}${this._status(item)}</div>
      <div class="media-title">${this._esc(title)}</div>
      <div class="media-meta">${this._esc(meta)}</div>
      ${seriesExtra?`<div class="series-extra">${this._esc(seriesExtra)}</div>`:""}
    </button>`;
  }
  _seriesDetail(item,seasonValue=null){
    const old=this.shadowRoot.querySelector(".modalbg");if(old)old.remove();
    const seasons=(item.seasons||[]).length?item.seasons:[0];
    const selectedSeason=seasonValue==null?seasons[0]:Number(seasonValue);
    const episodes=(item.episodes||[]).filter(ep=>Number(ep.season??0)===selectedSeason);
    const selectedId=this._seriesSelection?.[item.series_key]||null;
    const m=document.createElement("div");m.className="modalbg";
    const title=item.title||item.parsed_title||"Sans titre";
    const meta=this._metadata(item);
    const match=item.metadata_status==="matched"
      ?"JustWatch + IMDb"
      :item.metadata_status==="imdb_only"
      ?"IMDb uniquement"
      :"Non identifié";
    const seasonTabs=seasons.map(season=>`<button class="season-tab ${Number(season)===selectedSeason?"active":""}" data-season="${season}">Saison ${season||"?"}</button>`).join("");
    const episodeRows=episodes.map((ep,index)=>{
      const epNo=ep.episode!=null?Number(ep.episode):index+1;
      const code=ep.season!=null&&ep.episode!=null
        ?`S${String(ep.season).padStart(2,"0")}E${String(ep.episode).padStart(2,"0")}`
        :`Épisode ${epNo}`;
      const selected=selectedId&&selectedId===ep.local_id;
      return `<button class="episode-row ${selected?"selected":""}" data-episode-index="${index}">
        <span class="episode-main"><strong>${this._esc(code)}</strong><small>${this._esc(ep.filename||ep.relative_path||"")}</small></span>
        <ha-icon icon="${selected?"mdi:check-circle":"mdi:play-circle-outline"}"></ha-icon>
      </button>`;
    }).join("");
    m.innerHTML=`<div class="modal series-modal">
      <button class="modal-close" aria-label="Fermer">×</button>
      <div class="modal-head">
        ${item.poster?`<img src="${this._esc(item.poster)}" alt="">`:""}
        <div><h2>${this._esc(title)}</h2><div class="modal-meta">${this._esc(meta)}</div><div class="series-summary">${item.season_count} saison${item.season_count>1?"s":""} · ${item.episode_count} épisode${item.episode_count>1?"s":""}</div></div>
      </div>
      <p>${this._esc(item.description||"Aucun synopsis disponible pour le moment.")}</p>
      <div class="details">
        <div class="detail-row"><strong>Identification</strong><span>${this._esc(match)}</span></div>
      </div>
      <div class="season-tabs">${seasonTabs}</div>
      <div class="episode-list">${episodeRows||'<div class="state">Aucun épisode détecté pour cette saison.</div>'}</div>
      <div class="episode-help">Sélectionnez l’épisode à lire. Le fichier associé sera utilisé pour la future lecture VLC.</div>
    </div>`;
    m.onclick=e=>{if(e.target===m)m.remove()};
    m.querySelector(".modal-close").onclick=()=>m.remove();
    m.querySelectorAll("[data-season]").forEach(b=>b.addEventListener("click",()=>this._seriesDetail(item,Number(b.dataset.season))));
    m.querySelectorAll("[data-episode-index]").forEach(b=>b.addEventListener("click",()=>{
      const ep=episodes[Number(b.dataset.episodeIndex)];
      if(!ep)return;
      this._seriesSelection=this._seriesSelection||{};
      this._seriesSelection[item.series_key]=ep.local_id;
      this._seriesDetail(item,selectedSeason);
    }));
    this.shadowRoot.appendChild(m);
  }
  _detail(item){
    if(item?.is_series_group){this._seriesDetail(item);return}
    const old=this.shadowRoot.querySelector(".modalbg");if(old)old.remove();
    const m=document.createElement("div");m.className="modalbg";
    const title=item.title||item.parsed_title||item.filename||"Sans titre";
    const meta=this._metadata(item);
    const parsed=item.parsed_title&&item.parsed_title!==item.title
      ?`<div class="detail-row"><strong>Nom détecté</strong><span>${this._esc(item.parsed_title)}</span></div>`:"";
    const path=item.relative_path
      ?`<div class="detail-row"><strong>Fichier</strong><span>${this._esc(item.relative_path)}</span></div>`:"";
    const match=item.metadata_status==="matched"
      ?"JustWatch + IMDb"
      :item.metadata_status==="imdb_only"
      ?"IMDb uniquement"
      :"Non identifié";
    m.innerHTML=`<div class="modal">
      <button class="modal-close" aria-label="Fermer">×</button>
      <div class="modal-head">
        ${item.poster?`<img src="${this._esc(item.poster)}" alt="">`:""}
        <div><h2>${this._esc(title)}</h2><div class="modal-meta">${this._esc(meta)}</div></div>
      </div>
      <p>${this._esc(item.description||"Aucun synopsis disponible pour le moment.")}</p>
      <div class="details">
        <div class="detail-row"><strong>Identification</strong><span>${this._esc(match)}</span></div>
        ${parsed}${path}
      </div>
    </div>`;
    m.onclick=e=>{if(e.target===m)m.remove()};
    m.querySelector(".modal-close").onclick=()=>m.remove();
    this.shadowRoot.appendChild(m);
  }
  _bind(){
    this.shadowRoot.querySelector(".refresh")?.addEventListener("click",()=>this._refresh());
    this.shadowRoot.querySelectorAll("[data-category]").forEach(b=>b.addEventListener("click",()=>{
      this._category=b.dataset.category;this._render();
    }));
    const items=this._items();
    this.shadowRoot.querySelectorAll("[data-index]").forEach(b=>b.addEventListener("click",()=>{
      const i=items[Number(b.dataset.index)];if(i)this._detail(i);
    }));
  }
  _render(){
    if(!this.shadowRoot)return;
    const d=this._data;
    const cats=this._categories();
    const items=this._items();
    const total=d?.count||0;
    const enriched=d?.enriched_count||0;
    const progress=total?Math.round((enriched/total)*100):0;
    let body="";
    if(this._error)body=`<div class="state error">${this._esc(this._error)}</div>`;
    else if(!d&&this._loading)body='<div class="state">Lecture de la vidéothèque…</div>';
    else if(d&&!d.enabled)body='<div class="state">Streaming Local est désactivé dans la configuration de l’intégration.</div>';
    else if(d?.errors?.length&&!total)body=`<div class="state error">${d.errors.map(x=>this._esc(x)).join("<br>")}</div>`;
    else if(d&&total===0)body='<div class="state">Aucun fichier vidéo détecté.</div>';
    else body=`<div class="rail">${items.map((i,n)=>this._tile(i,n)).join("")}</div>`;

    const status=this._enriching
      ?`Identification des films… ${enriched}/${total}`
      :total
      ?`${total} fichier${total>1?"s":""} · métadonnées ${progress}%`
      :"";

    this.shadowRoot.innerHTML=`<style>
      :host{display:block}
      ha-card{overflow:hidden}
      .wrap{padding:16px}
      .top{display:flex;align-items:center;gap:10px;margin-bottom:12px}
      .title{font-size:1.25rem;font-weight:800}
      .status{font-size:.82rem;color:var(--secondary-text-color)}
      .spacer{flex:1}
      button{font:inherit;color:var(--primary-text-color)}
      .refresh{width:36px;height:36px;border:0;border-radius:50%;background:var(--secondary-background-color);cursor:pointer;font-size:20px}
      .tabs{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;margin-bottom:12px}
      .tab{display:flex;align-items:center;gap:6px;border:0;border-radius:999px;padding:8px 12px;background:var(--secondary-background-color);cursor:pointer;white-space:nowrap}
      .tab.active{background:var(--primary-color);color:var(--text-primary-color,#fff)}
      .tab ha-icon{--mdc-icon-size:18px}
      .rail{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(145px,170px);gap:12px;overflow-x:auto;padding:2px 2px 10px;scroll-snap-type:x proximity}
      .media{display:block;min-width:0;padding:0;border:0;background:none;text-align:left;cursor:pointer;scroll-snap-align:start}
      .poster{position:relative;aspect-ratio:2/3;border-radius:12px;overflow:hidden;background:var(--secondary-background-color);box-shadow:0 2px 8px rgba(0,0,0,.18)}
      .poster img{width:100%;height:100%;display:block;object-fit:cover}
      .poster-fallback{width:100%;height:100%;display:grid;place-items:center;color:var(--secondary-text-color)}
      .poster-fallback ha-icon{--mdc-icon-size:48px}
      .media-title{margin-top:8px;font-weight:800;line-height:1.2;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
      .media-meta{margin-top:4px;min-height:17px;color:var(--secondary-text-color);font-size:.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .series-extra{margin-top:3px;color:var(--secondary-text-color);font-size:.75rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .match{position:absolute;top:7px;left:7px;border-radius:999px;padding:4px 7px;background:rgba(0,0,0,.72);color:#fff;font-size:.68rem;font-weight:800}
      .match.imdb{background:rgba(155,110,0,.88)}.match.unmatched{background:rgba(130,35,35,.88)}.match.pending{background:rgba(30,30,30,.72)}
      .state{padding:28px 12px;text-align:center;color:var(--secondary-text-color)}
      .error{color:var(--error-color)}
      .modalbg{position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.62);display:flex;align-items:center;justify-content:center;padding:16px;box-sizing:border-box}
      .modal{position:relative;width:min(520px,calc(100vw - 32px));max-height:calc(100dvh - 32px);overflow:auto;box-sizing:border-box;padding:20px;border-radius:20px;background:var(--card-background-color)}
      .modal-close{position:absolute;right:10px;top:10px;width:38px;height:38px;border:0;border-radius:50%;background:var(--secondary-background-color);font-size:25px;cursor:pointer}
      .modal-head{display:flex;gap:14px;padding-right:42px;align-items:flex-start}
      .modal-head img{width:88px;aspect-ratio:2/3;object-fit:cover;border-radius:9px}
      .modal h2{margin:4px 0 6px;font-size:1.35rem}.modal-meta{color:var(--secondary-text-color)}
      .modal p{line-height:1.45;color:var(--secondary-text-color)}
      .details{display:grid;gap:7px;margin-top:14px}.detail-row{display:grid;grid-template-columns:110px 1fr;gap:10px;font-size:.88rem}.detail-row span{overflow-wrap:anywhere;color:var(--secondary-text-color)}
      .series-summary{margin-top:6px;color:var(--secondary-text-color);font-size:.86rem}
      .season-tabs{display:flex;gap:8px;overflow-x:auto;margin:18px 0 12px;padding-bottom:2px}
      .season-tab{border:0;border-radius:999px;padding:8px 12px;background:var(--secondary-background-color);cursor:pointer;white-space:nowrap;font-weight:800}
      .season-tab.active{background:var(--primary-color);color:var(--text-primary-color,#fff)}
      .episode-list{display:grid;gap:7px}
      .episode-row{width:100%;display:flex;align-items:center;gap:10px;border:0;border-radius:12px;padding:10px 12px;background:var(--secondary-background-color);cursor:pointer;text-align:left}
      .episode-row.selected{outline:2px solid var(--primary-color)}
      .episode-main{min-width:0;flex:1;display:flex;flex-direction:column;gap:3px}
      .episode-main small{color:var(--secondary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .episode-row ha-icon{flex:0 0 auto;color:var(--primary-color)}
      .episode-help{margin-top:12px;color:var(--secondary-text-color);font-size:.78rem;line-height:1.35}
      @media(max-width:600px){.wrap{padding:14px 11px}.rail{grid-auto-columns:minmax(140px,44vw)}.status{display:none}.modal{padding:15px}.modal-head img{width:74px}.detail-row{grid-template-columns:1fr;gap:2px}}
    </style>
    <ha-card><div class="wrap">
      <div class="top"><div><div class="title">${this._esc(this._config.title)}</div><div class="status">${this._esc(status)}</div></div><div class="spacer"></div><button class="refresh" title="Rescanner">${this._loading?"…":"↻"}</button></div>
      ${cats.length?`<div class="tabs">${cats.map(cat=>`<button class="tab ${cat===this._category?"active":""}" data-category="${cat}"><ha-icon icon="${this._icon(cat)}"></ha-icon><span>${this._label(cat)} (${this._categoryCount(cat)})</span></button>`).join("")}</div>`:""}
      ${body}
    </div></ha-card>`;
    this._bind();
  }
}
customElements.define("streaming-local-card",StreamingLocalCard);

window.customCards=window.customCards||[];
window.customCards.push({type:'streaming-top-fr-card',name:'Streaming Top FR',description:'Streaming multi-services France via Netflix officiel + JustWatch'});
window.customCards.push({type:'streaming-top-fr-catalog-card',name:'Top Streaming FR',description:'Classements par décennie Films / Animation / Séries / Famille disponibles sur vos services'});
window.customCards.push({type:'streaming-local-card',name:'Streaming Local',description:'Vidéothèque locale Films / Séries / Animation / Documentaires avec métadonnées IMDb / JustWatch'});
console.info(`STREAMING TOP FR ${STFR_VERSION}`);
