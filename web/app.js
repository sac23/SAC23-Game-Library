'use strict';
const PATHS = {
  grid: document.querySelector('#gameGrid'), banner: document.querySelector('#banner'), hero: document.querySelector('#hero'),
  stats: document.querySelector('#stats'), modal: document.querySelector('#modalHost'), nav: document.querySelector('#nav'),
  toast: document.querySelector('#toastHost')
};
const app = {
  games: [], folders: [], stats: {}, filter: 'all', sort: 'title', search: '', lastScan: null, lastScanProgress: false,
  busyArtwork: false, shownScanError: false, isDemo: false, settings: {}, currentModal: '', selectedId: null, version: '1.0', dataLoaded: false
};
const ICONS = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
  gamepad: '<line x1="6" y1="12" x2="10" y2="12"/><line x1="8" y1="10" x2="8" y2="14"/><line x1="15" y1="13" x2="15.01" y2="13"/><line x1="18" y1="11" x2="18.01" y2="11"/><path d="M6 6h12a5 5 0 0 1 4.8 4l1 7a3 3 0 0 1-5 3l-2-2H7l-2 2a3 3 0 0 1-5-3l1-7a5 5 0 0 1 5-4Z" transform="translate(1 -2) scale(.91)"/>',
  heart: '<path d="M20.8 4.7a5.5 5.5 0 0 0-7.8 0L12 5.8l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.5a5.5 5.5 0 0 0 0-7.8Z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  'folder-plus': '<path d="M3 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M12 11v7m-3.5-3.5h7"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15.1l1.1.8-1.8 3.1-1.3-.6a8 8 0 0 1-2.5 1.5l-.2 1.4h-3.6l-.2-1.4a8 8 0 0 1-2.5-1.5l-1.3.6-1.8-3.1 1.1-.8a8 8 0 0 1 0-3l-1.1-.8 1.8-3.1 1.3.6a8 8 0 0 1 2.5-1.5l.2-1.4h3.6l.2 1.4a8 8 0 0 1 2.5 1.5l1.3-.6 1.8 3.1-1.1.8a8 8 0 0 1 0 3Z"/>',
  'sliders-horizontal': '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="17" x2="20" y2="17"/><circle cx="9" cy="7" r="2" fill="#1d3752"/><circle cx="16" cy="17" r="2" fill="#1d3752"/>',
  sparkles: '<path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Zm7 12 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15ZM4 2l.8 2.2L7 5l-2.2.8L4 8l-.8-2.2L1 5l2.2-.8L4 2Z"/>',
  'hard-drive': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 13h18m-4 3h.01m-4 0h.01"/>',
  'arrow-down-wide-narrow': '<path d="M3 7h18M6 12h12m-9 5h6"/>',
  'refresh-cw': '<path d="M20 6v5h-5M4 18v-5h5"/><path d="M6.6 8A7 7 0 0 1 19.9 11M4.1 13A7 7 0 0 0 17.4 16"/>',
  play: '<polygon points="7 4 20 12 7 20 7 4" stroke-linejoin="round"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4m10-8h4m-4 8h4"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M3 6h18m-2 0-1 14H6L5 6m3 0V4h8v2m-6 4v7m4-7v7"/>',
  external: '<path d="M14 4h6v6m0-6L10 14"/><path d="M19 14v5H5V5h5"/>',
  file: '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M13 2v7h7"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 11v6m0-10h.01"/>',
  edit: '<path d="M12 20h9M3 17l12-12 4 4L7 21H3v-4Z"/><path d="m13 7 4 4"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  layers: '<path d="m12 2 10 6-10 6L2 8l10-6Zm-10 11 10 6 10-6M2 18l10 5 10-5"/>',
  shield: '<path d="M12 2 3 6v6c0 6 4 9 9 10 5-1 9-4 9-10V6l-9-4Z"/><path d="m8 12 3 3 5-6"/>',
  database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.6 4 3 9 3s9-1.4 9-3V5M3 12c0 1.6 4 3 9 3s9-1.4 9-3"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
  star: '<path d="m12 2 3 6.2 6.8 1-4.9 4.7 1.1 6.8L12 17.5l-6 3.2 1.1-6.8-4.9-4.7 6.8-1L12 2Z"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5-10 10"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  video: '<rect x="3" y="5" width="14" height="14" rx="2"/><path d="m17 10 4-3v10l-4-3"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  'circle-help': '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2.2-2.5 4m0 4h.01"/>'
};
function icon(name, size=20){return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.file}</svg>`}
function replaceStaticIcons(){document.querySelectorAll('[data-icon]').forEach(node=>{node.innerHTML=icon(node.dataset.icon)})}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function safeUrl(url){try{const u=new URL(String(url));return ['http:','https:'].includes(u.protocol)?u.href:''}catch{return ''}}
function fmtBytes(n){n=Math.max(0,Number(n)||0);if(!n)return '0 B';const units=['B','KB','MB','GB','TB'];let j=0;while(n>=1024&&j<units.length-1){n/=1024;j++}return (n>=100?n.toFixed(0):n>=10?n.toFixed(1):n.toFixed(2)).replace(/\.0+$/,'')+' '+units[j]}
function formatDate(time){return time?new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric'}).format(new Date(time*1000)):'Not available'}
function showName(g){return g.custom_title || g.identified_title || g.title || 'Untitled game'}
function videoId(u){try{const v=new URL(u);let id='';if(v.hostname==='youtu.be'||v.hostname.endsWith('.youtu.be'))id=v.pathname.slice(1).split('/')[0];else if(v.hostname==='youtube.com'||v.hostname==='www.youtube.com'||v.hostname==='m.youtube.com'||v.hostname==='youtube-nocookie.com'||v.hostname==='www.youtube-nocookie.com')id=v.searchParams.get('v')||(/\/(?:embed|shorts|live)\/([a-zA-Z0-9_-]+)/.exec(v.pathname)||[])[1]||'';return /^[A-Za-z0-9_-]{11}$/.test(id)?id:null}catch{return null}}
function yts(title,platform){return 'https://www.youtube.com/results?search_query='+encodeURIComponent(`${title} ${platform==='UNKNOWN'?'PlayStation':platform} official trailer`)}
const sampleNames = [
 {title:'Cyberpunk 2077',platform:'PS5',id:'demo-1',steamId:1091500,size:0},
 {title:'Elden Ring',platform:'PS5',id:'demo-2',steamId:1245620,size:0},
 {title:'God of War Ragnarök',platform:'PS5',id:'demo-3',steamId:2322010,size:0},
 {title:'Horizon Forbidden West',platform:'PS5',id:'demo-4',steamId:2420110,size:0},
 {title:'Ghost of Tsushima',platform:'PS4',id:'demo-5',steamId:2215430,size:0},
 {title:'Marvel’s Spider-Man Remastered',platform:'PS5',id:'demo-6',steamId:1817070,size:0}
].map((g,i)=>({...g,cover_url:`https://cdn.cloudflare.steamstatic.com/steam/apps/${g.steamId}/library_600x900_2x.jpg`,files:[],file_count:0,update_count:0,dlc_count:0,game_count:0,updated_at:0,preview:true,style:i}));
const gradients=[
 'linear-gradient(155deg,#d8524e 0%,#671d3a 48%,#132f52 100%)',
 'linear-gradient(145deg,#998a69 0%,#494b4e 54%,#182033 100%)',
 'linear-gradient(150deg,#6f9faf 0%,#1e607e 56%,#0c2035 100%)',
 'linear-gradient(145deg,#7d544e 0%,#3f334a 44%,#151b2a 100%)',
 'linear-gradient(150deg,#37769e 0%,#19334e 45%,#101925 100%)',
 'linear-gradient(150deg,#a06951 0%,#4b375c 52%,#1d2439 100%)',
 'linear-gradient(150deg,#9b5965,#3d4f78 60%,#121e33)',
 'linear-gradient(150deg,#478787,#334579 60%,#1b203f)'
];
function colorIndex(g){let sum=0;for(const c of showName(g))sum=(sum*31+c.charCodeAt(0))>>>0;return g.style ?? sum%gradients.length}
function getCoverSrc(g){
 if(g.preview)return safeUrl(g.cover_url);
 if(g.cover_available)return `/api/image/${encodeURIComponent(g.id)}?v=${g.cover_revision||0}`;
 return ''; // Never count inaccessible remote URLs as loaded cover art.
}
function cardCover(g,hero=false){
 const url=getCoverSrc(g),title=showName(g),missing=!url;
 return `<div class="cover-gradient cover-fallback" style="--cover:${gradients[colorIndex(g)]}">
   <span class="fallback-glyph">${icon('image',30)}</span>
   <span class="fallback-title">${esc(title)}</span>
   <span class="fallback-hint">${g.preview?'SAMPLE GAME':'COVER NOT MATCHED YET'}</span>
  </div>${url?`<img class="game-cover ${g.cover_quality==='icon'?'game-cover-icon':''}" src="${esc(url)}" alt="${esc(title)} game cover" loading="lazy" onerror="this.hidden=true;this.parentElement.classList.add('missing-art')">`:''}`;
}
function gameById(id){return (app.games.length?app.games:sampleNames).find(x=>x.id===id) || sampleNames.find(x=>x.id===id)}
function allVisibleGames(){
 let list=app.games.length?app.games:(app.folders.length?[]:sampleNames);
 list=list.filter(g=>app.filter==='all'||(app.filter==='favorites'?!!g.favorite:app.filter==='missing'?!getCoverSrc(g):g.platform.toLowerCase()===app.filter));
 const q=app.search.trim().toLowerCase();
 if(q)list=list.filter(g=>(showName(g)+' '+(g.title_id||'')+' '+(g.files||[]).map(f=>f.path).join(' ')).toLowerCase().includes(q));
 list=[...list];
 if(app.sort==='recent')list.sort((a,b)=>(b.updated_at||0)-(a.updated_at||0));
 else if(app.sort==='largest')list.sort((a,b)=>(b.size||0)-(a.size||0));
 else if(app.sort==='smallest')list.sort((a,b)=>(a.size||0)-(b.size||0));
 else list.sort((a,b)=>showName(a).localeCompare(showName(b)));
 return list;
}
async function api(route,method='GET',body){const opts={method,headers:{}};if(method!=='GET'){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body||{})}let res;try{res=await fetch(route,opts)}catch(e){throw new Error('Cannot reach the local game-library server. Check that the launcher is still open.')}let data;try{data=await res.json()}catch{throw new Error('Unexpected server response')}if(!res.ok||data.ok===false)throw new Error(data.error||'Request failed');return data}
function toast(message,kind='ok'){const div=document.createElement('div');div.className='toast '+kind;div.textContent=message;PATHS.toast.appendChild(div);setTimeout(()=>div.remove(),4600)}
function renderNav(){
 const counts={all:app.games.length,ps4:app.stats.ps4||0,ps5:app.stats.ps5||0,
 favorites:app.stats.favorites||0,missing:Math.max(0,(app.stats.games||0)-(app.stats.covers||0))};
 const entries=[['all','grid','All games'],['ps4','gamepad','PlayStation 4'],
 ['ps5','gamepad','PlayStation 5'],['favorites','heart','Favorites'],['missing','image','Missing artwork']];
 PATHS.nav.innerHTML=entries.map(([id,sym,label])=>`<button class="nav-item ${app.filter===id?'active':''}" data-tab="${id}">${icon(sym)}<span>${label}</span><span class="nav-count">${counts[id]}</span></button>`).join('');
 document.querySelector('#folderNumber').textContent=app.folders.length;
 document.querySelector('#sideFiles').textContent=`${app.stats.files||0} file items indexed`;
 document.querySelector('#sideStorage').textContent=fmtBytes(app.stats.bytes);
 document.querySelector('#storageBar').style.width=Math.min(100,((app.stats.bytes||0)/(1024**4))*100)+'%';
 document.querySelector('#versionNumber').textContent='v'+app.version;
}
function renderBanner(){
 if(!app.games.length&&!app.folders.length){
 PATHS.banner.innerHTML=`<div class="banner hero-tip">${icon('sparkles')}<span><strong>Welcome to the new visual library.</strong> These are sample games. Add your actual folders and covers will be looked up automatically.</span><button class="ghost-btn" data-action="folders">Add folder ${icon('arrow')}</button></div>`;
 return;
 }
 const games=app.stats.games||0,covers=app.stats.covers||0,trailers=app.stats.trailers||0;
 PATHS.banner.innerHTML=app.folders.length?`<div class="banner success coverage-banner">
  <span class="coverage-emblem">${icon('shield',18)}</span>
  <span><strong>${covers} of ${games} covers saved on your PC</strong> · ${Math.max(0,games-covers)} still missing · ${trailers} trailers linked. PKG files untouched.</span>
  <button class="ghost-btn" data-action="cover-inbox">${icon('folder',14)} Cover Inbox</button><button class="ghost-btn" data-action="cover-report">${icon('download',14)} Cover report</button><button class="ghost-btn" data-action="metadata">${icon('refresh-cw',15)} Find missing covers</button>
 </div>`:'';
}
function renderHero(){
 let list=allVisibleGames();
 let g=list.find(x=>x.favorite&&getCoverSrc(x))||list.find(x=>getCoverSrc(x))||list[0]||null;
 const art=g?getCoverSrc(g):'';
 const isReal=!!g&&!g.preview;
 PATHS.hero.innerHTML=`<div class="hero hero-v2">
 <div class="hero-art" ${art?`style="background-image:url('${esc(art.replace(/'/g,'%27'))}')"`:''}></div>
 <div class="hero-content">
  <div class="featured-pill">${isReal?'NOW IN YOUR COLLECTION':'SAC23 GAME LIBRARY 2.0'}</div>
  <h1>${g?esc(showName(g)):'Your games. Your collection.'}</h1>
  <p>${isReal?'One click to view the game, watch its trailer, and find all of its files.':'Beautiful game covers, playable trailers and all your PlayStation titles together.'}</p>
  <div class="hero-actions">
  <button class="primary-btn" data-action="${isReal?'detail':'folders'}" ${isReal?`data-id="${esc(g.id)}"`:''}>${icon(isReal?'play':'folder-plus')} ${isReal?'Watch preview':'Add game folders'}</button>
  <button class="outline-btn" data-action="${isReal?'metadata':'settings'}">${icon('sparkles')} ${isReal?'Get game artwork':'Artwork options'}</button>
  </div>
 </div><div class="hero-meta">PS<span>4</span> / PS<span>5</span></div>
 </div>`;
}
function renderStats(){const a=app.stats;const stats=[['gamepad','Games indexed',a.games||0,'Your collection',''],['layers','PS4 titles',a.ps4||0,'PlayStation 4','purple'],['gamepad','PS5 titles',a.ps5||0,'PlayStation 5','teal'],['hard-drive','Total on disk',fmtBytes(a.bytes||0),`${a.files||0} game file items`,'gold']];PATHS.stats.innerHTML=stats.map(([i,label,val,sub,color])=>`<div class="stat-card"><div class="stat-icon ${color}">${icon(i)}</div><div class="stat-body"><span class="stat-label">${esc(label)}</span><strong class="stat-value">${esc(val)}</strong><span class="stat-sub">${esc(sub)}</span></div></div>`).join('')}
function gameCard(g,index){
 const trailer=!!videoId(g.trailer_url),name=showName(g);
 return `<article class="game-card" data-action="detail" data-id="${esc(g.id)}" tabindex="0" role="button" aria-label="Preview ${esc(name)}" style="animation-delay:${Math.min(index,15)*16}ms">
 <div class="cover-wrap ${getCoverSrc(g)?'':'missing-art'} ${g.cover_quality==='icon'?'icon-art':''}">
  ${cardCover(g)}
  <span class="platform-badge ${g.platform.toLowerCase()}">${esc(g.platform==='UNKNOWN'?'GAME':g.platform)}</span>
  ${g.preview?'<span class="platform-badge sample">DEMO</span>':''}
  ${g.preview?'':`<button class="fav-card ${g.favorite?'favorite':''}" data-action="favorite" data-id="${esc(g.id)}" title="${g.favorite?'Remove favorite':'Add favorite'}" aria-label="Toggle favorite">${icon('star')}</button>`}
  <div class="cover-hover-label">${icon('play',25)}<span>VIEW PREVIEW</span></div>
 </div>
 <div class="game-info"><h3 title="${esc(name)}">${esc(name)}</h3>
 <div><span>${g.preview?'Demo game':fmtBytes(g.size)}</span>
 <span class="game-variants">${trailer?`${icon('video',12)} Trailer`:g.dlc_count?`${g.dlc_count} DLC`:g.update_count?`${g.update_count} update${g.update_count===1?'':'s'}`:g.preview?'Cover preview':'Base game'}</span></div>
 </div></article>`;
}
function renderGrid(){
 const all=allVisibleGames(),names={all:'All Games',ps4:'PlayStation 4',ps5:'PlayStation 5',favorites:'Favorites',missing:'Missing Artwork'};
 const title=names[app.filter]||'Your Games';
 document.querySelector('#pageName').textContent=title==='All Games'?'My Library':title;
 document.querySelector('#listTitle').textContent=title;
 document.querySelector('#resultCount').textContent=`${all.length} ${all.length===1?'title':'titles'}`;
 PATHS.grid.innerHTML=all.map(gameCard).join('');
 document.querySelector('#emptyState').innerHTML=all.length?'':`<div class="no-results">${icon('search')}<h3>${app.filter==='missing'?'All matched covers are here!':'Nothing to display'}</h3><p>${app.filter==='favorites'?'Star a game to save it here.':app.search?'Try a different game title.':app.filter==='missing'?'All indexed games currently have a cover image.':'Add a game folder to begin.'}</p><div class="empty-actions"><button class="primary-btn" data-action="folders">${icon('folder-plus')} Add folder</button><button class="outline-btn" data-tab="all">View all</button></div></div>`;
}
function render(){app.isDemo=!app.games.length&&!app.folders.length;renderNav();renderBanner();renderHero();renderStats();renderGrid()}
async function loadLibrary(){const d=await api('/api/library');app.games=d.games||[];app.stats=d.stats||{};app.folders=d.folders||[];app.lastScan=d.last_scan;app.version=d.version||'1.0';app.dataLoaded=true;render()}
function modal(title,subtitle,body,footer='',width=''){app.currentModal=title;PATHS.modal.innerHTML=`<div class="modal-backdrop" data-action="close-backdrop"><section class="modal-window ${width}" role="dialog" aria-modal="true" aria-label="${esc(title)}"><header class="modal-top"><div><small>${esc(subtitle)}</small><h2>${esc(title)}</h2></div><button class="close-modal" data-action="close" aria-label="Close">${icon('close')}</button></header><div class="modal-body">${body}</div>${footer?`<footer class="modal-actions">${footer}</footer>`:''}</section></div>`;document.body.style.overflow='hidden'}
function closeModal(){PATHS.modal.innerHTML='';app.currentModal='';app.detailOpenId=null;document.body.style.overflow=''}
function browseHelp(){return `<div class="tip-box">${icon('shield')}<div><strong>Zero risk to your games.</strong> This app reads filenames, game metadata and sizes. It never unpacks, renames, moves, deletes or changes PS4/PS5 PKGs, archives or game folders. Your existing folder structure stays exactly as it is.</div></div>`}
function showFolders(){const folderRows=app.folders.length?app.folders.map(x=>`<div class="folder-item"><div class="item-icon">${icon('folder')}</div><div class="path-block"><strong title="${esc(x.path)}">${esc(x.path)}</strong><small>${esc(x.platform==='AUTO'?'Automatic PS4 / PS5 detection':x.platform+' only')}</small></div><button class="remove-btn" title="Remove from library" data-action="remove-folder" data-id="${esc(x.id)}">${icon('trash')}</button></div>`).join(''):'<p class="field-hint">No folders added. Choose a drive or a folder containing your games.</p>';modal('Your game folders','SCAN SETTINGS',`<p style="font-size:12px;color:#91a9c5;line-height:1.6;margin-top:0">Point the library at one or more locations on your PC, including external drives and network shares. Subfolders are scanned automatically.</p><div class="folder-list">${folderRows}</div><div class="horizontal-line"></div><form id="addFolderForm"><label class="field-label" for="folderPath">FOLDER LOCATION</label><div class="field-row"><input class="field-control" name="folderPath" id="folderPath" placeholder="E:\\PS4 or S:\\PS5_Games" autocomplete="off"><button class="outline-btn" type="button" data-action="browse-folder">${icon('folder')} Browse</button></div><label class="field-label" for="folderPlatform">CONSOLE TYPE</label><div class="field-row"><select class="field-control" name="platform" id="folderPlatform"><option value="AUTO">Auto detect PS4 / PS5</option><option value="PS4">This folder is PS4</option><option value="PS5">This folder is PS5</option></select><button class="primary-btn" type="submit">${icon('plus')} Add folder & scan</button></div></form>${browseHelp()}`,`<div><button class="ghost-btn" data-action="scan">${icon('refresh-cw')} Rescan library</button></div><div><button class="outline-btn" data-action="close">Done</button></div>`,'medium')}
async function showSettings(){
 try{app.settings=(await api('/api/settings')).settings||{}}catch(e){toast(e.message,'error')}
 const s=app.settings;
 app.detailOpenId=null;
 modal('Artwork & previews','AUTOMATIC COVER MATCHING',`
 <div class="settings-intro">${icon('sparkles',22)}<div><strong>Artwork is copied to your PC automatically.</strong><p>The app checks PS4 PKG icons and small cover images inside ZIP archives without modifying your files, then matches known PlayStation title IDs, reuses artwork already in your library and tries official PlayStation Store imagery, the public PS4 boxart archive, Steam, GOG and Wikipedia. Unmatched games are listed in Cover report. For the last stubborn titles, open Cover Inbox, save cover files as Game Name.jpg or CUSA12345.png, then click Find missing covers. No account is needed for the primary sources.</p></div></div>
 <form id="settingsForm">
  <label class="toggle-line"><span><strong>Automatically search for game covers</strong><small>Rechecks your games after each scan; actual images, not empty cover links, count as matches.</small></span><input type="checkbox" id="autoArtwork" ${s.auto_artwork!==false?'checked':''}></label>
  <label class="toggle-line"><span><strong>Automatically find YouTube trailers</strong><small>Uses public search results. Links can be edited for individual games.</small></span><input type="checkbox" id="autoTrailers" ${s.auto_trailers!==false?'checked':''}></label>
  <label class="toggle-line"><span><strong>Use Wikipedia as an additional source</strong><small>Best-effort fallback for games not found on Steam.</small></span><input type="checkbox" id="wikiFallback" ${s.wiki_fallback!==false?'checked':''}></label>
  <div class="horizontal-line"></div><p class="settings-key-heading">OPTIONAL PROVIDERS FOR HARD-TO-FIND GAMES</p>
  <label class="field-label" for="sgdbKey">STEAMGRIDDB API KEY — EXTRA PORTRAIT COVERS</label>
  <input class="field-control" id="sgdbKey" type="password" name="steamgriddb_key" value="${esc(s.steamgriddb_key||'')}" placeholder="Optional">
  <label class="field-label" for="rawgKey">RAWG API KEY — ADDITIONAL GAME ARTWORK</label>
  <input class="field-control" id="rawgKey" type="password" name="rawg_key" value="${esc(s.rawg_key||'')}" placeholder="Optional">
  <label class="field-label" for="ytKey">YOUTUBE DATA API KEY — RELIABLE TRAILER SEARCH FALLBACK</label>
  <input class="field-control" id="ytKey" type="password" name="youtube_key" value="${esc(s.youtube_key||'')}" placeholder="Optional">
  <p class="field-hint">API keys are optional and saved on this PC. You can always set a local JPG/PNG cover or paste a YouTube video URL in a game's Edit menu.</p>
  <div class="links-inline"><a href="https://www.steamgriddb.com/profile/preferences/api" target="_blank" rel="noopener noreferrer">SteamGridDB key ${icon('external')}</a><a href="https://rawg.io/apidocs" target="_blank" rel="noopener noreferrer">RAWG key ${icon('external')}</a></div>
 </form>`,
 `<div><button class="ghost-btn" data-action="export">${icon('download')} Export library</button></div><div><button class="outline-btn" data-action="close">Cancel</button><button class="primary-btn" data-action="save-settings">${icon('check')} Save</button></div>`,'medium');
}
function openDetail(gid,requestLookup=true){
 const g=gameById(gid);if(!g){toast('Game is no longer in the library','error');return}
 app.selectedId=gid;app.detailOpenId=gid;
 const preview=!!g.preview,name=showName(g),vid=videoId(g.trailer_url||'');
 const youtubeSearch=yts(name,g.platform), source=safeUrl(g.source_url||'');
 const content=g.files&&g.files.length?g.files.map(f=>`<div class="file-row">
 <span class="file-item-icon">${icon(f.kind==='Folder'?'folder':'file')}</span>
 <div class="file-main"><strong title="${esc(f.path)}">${esc(f.path.split(/[\/]/).pop())}</strong><small title="${esc(f.path)}">${esc(f.path)}</small></div>
 <span class="file-tag ${f.category.toLowerCase()}">${esc(f.category)}</span><span class="file-size">${fmtBytes(f.size)}</span>
 <button class="file-open" data-action="open-path" data-path="${esc(f.path)}" title="Show in File Explorer">${icon('external')}</button></div>`).join(''):'<p class="field-hint">No installed files in sample mode. Add a folder to view game files.</p>';
 const trailer=vid?`<iframe class="video-frame video-live" src="https://www.youtube-nocookie.com/embed/${vid}?autoplay=1&mute=1&playsinline=1&rel=0" title="${esc(name)} YouTube trailer" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" loading="eager" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>`:
 `<div class="video-unavailable">${icon('video',39)}<h3>Finding a preview for ${esc(name)}</h3><p>${preview?'A trailer can be added to any game in your library.':'Automatic YouTube matching runs in the background. Some games may need a manual video link.'}</p><div class="video-buttons"><button class="outline-btn" data-action="enrich-one" data-id="${esc(gid)}">${icon('refresh-cw')} Retry preview</button><a class="outline-btn" href="${esc(youtubeSearch)}" target="_blank" rel="noopener noreferrer">${icon('search')} Search YouTube</a></div></div>`;
 const coverInfo=g.source?`<p class="cover-attribution">Cover: ${source?`<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">${esc(g.source)}</a>`:esc(g.source)}</p>`:'';
 modal(name,`${g.platform} • ${preview?'SAMPLE GAME':'YOUR COLLECTION'}`,`
  <div class="cinema-layout">
   <aside class="cinema-sidebar"><div class="cinema-cover">${cardCover(g)}</div>
    <div class="cinema-platform"><span class="kbd-pill">${esc(g.platform)}</span>${g.title_id?`<span class="kbd-pill">${esc(g.title_id)}</span>`:''}</div>
    <h3>${esc(name)}</h3>
    <div class="cinema-totals"><span>${icon('hard-drive',16)} ${preview?'Preview':fmtBytes(g.size||0)}</span><span>${icon('layers',16)} ${g.file_count||0} files</span></div>
    ${coverInfo}
   </aside>
   <section class="cinema-main"><div class="cinema-kicker"><span class="playing-dot"></span>${vid?'YOUTUBE GAME PREVIEW':'GAME TRAILER'}</div>
    <div class="cinema-player">${trailer}</div>
    <div class="cinema-after-video"><div><strong>${vid?'Watch the game right here':'Preview not matched yet'}</strong>
     <p>${vid?'Your trailer is loaded directly in this popup. Press play or unmute on the player.':'Automatic search works best with clear game names. You can edit the title or paste a YouTube URL.'}</p></div>
     ${vid?`<a class="video-youtube-link" href="https://www.youtube.com/watch?v=${vid}" target="_blank" rel="noopener noreferrer">${icon('external',15)} YouTube</a>`:''}
    </div>
    <div class="cinema-tools">
    ${preview?'':`<button class="outline-btn" data-action="edit" data-id="${esc(gid)}">${icon('edit')} Edit cover / trailer</button>`}
    ${preview?'':`<button class="outline-btn" data-action="enrich-one" data-id="${esc(gid)}">${icon('sparkles')} Find artwork</button>`}
    ${preview?'':`<button class="outline-btn" data-action="favorite" data-id="${esc(gid)}">${icon('star')} ${g.favorite?'Favorite ✓':'Favorite'}</button>`}
    </div>
   </section>
  </div>
  <div class="asset-breakdown"><div><span>${icon('gamepad',17)} BASE</span><strong>${g.game_count||0}</strong></div><div><span>${icon('refresh-cw',17)} UPDATES</span><strong>${g.update_count||0}</strong></div><div><span>${icon('layers',17)} DLC</span><strong>${g.dlc_count||0}</strong></div><div><span>${icon('hard-drive',17)} TOTAL SIZE</span><strong>${preview?'—':fmtBytes(g.size)}</strong></div></div>
  <div class="section-header">${icon('folder',18)} Your game files <span>${g.file_count||0} items</span></div>
  <div class="file-table">${content}</div>
  ${g.cover_error&&!getCoverSrc(g)?`<p class="field-hint"><strong>Cover issue:</strong> ${esc(g.cover_error)}. You can fix the title or choose a local image.</p>`:''}${g.metadata_error?`<p class="field-hint">Video lookup: ${esc(g.metadata_error)}</p>`:''}
  `,
  `<div><small class="footer-safety">${icon('shield',15)} Read-only game catalog</small></div><div><button class="outline-btn" data-action="close">Close</button></div>`, 'cinema-modal');
 if(requestLookup&&!preview&&(!vid||!getCoverSrc(g))){
   if(!app.previewLookups)app.previewLookups=new Set();
   if(!app.previewLookups.has(gid)){
    app.previewLookups.add(gid);api('/api/enrich','POST',{id:gid}).catch(()=>{});
   }
 }
}
function openEdit(gid){app.detailOpenId=null;const g=gameById(gid);if(!g||g.preview){toast('Connect a folder first to edit actual games','error');return}app.selectedId=gid;modal('Edit game','CUSTOMIZE YOUR LIBRARY',`<form id="editGameForm" class="edit-grid"><div class="edit-full"><label class="field-label" for="editTitle">DISPLAY NAME</label><input class="field-control" id="editTitle" name="custom_title" value="${esc(g.custom_title||g.title)}" placeholder="Game title"></div><div class="edit-full"><label class="field-label" for="editCover">COVER ART URL (JPG, PNG, WEBP)</label><input class="field-control" id="editCover" name="cover_url" value="${esc(g.cover_url||'')}" placeholder="https://.../game-cover.jpg"></div><div class="edit-full"><label class="field-label" for="editCoverPath">OR CHOOSE A LOCAL COVER IMAGE</label><div class="edit-cover-row"><input class="field-control" id="editCoverPath" name="custom_cover" value="${esc(g.custom_cover||'')}" placeholder="C:\\Users\\You\\Pictures\\game-cover.jpg"><button class="outline-btn" data-action="browse-cover" type="button">${icon('image')} Browse</button></div><p class="field-hint">A local cover overrides the URL. To use the URL instead, clear the local cover field.</p></div><div class="edit-full"><label class="field-label" for="editTrailer">YOUTUBE VIDEO URL</label><input class="field-control" id="editTrailer" name="trailer_url" value="${esc(g.trailer_url||'')}" placeholder="https://www.youtube.com/watch?v=..."><p class="field-hint">Paste a YouTube video link and it becomes a playable trailer in the details view.</p><a href="${esc(yts(showName(g),g.platform))}" target="_blank" rel="noopener noreferrer" style="font-size:11px">Find on YouTube ${icon('external')}</a></div><div><label class="field-label" for="editYear">YEAR</label><input class="field-control" id="editYear" name="year" value="${esc(g.year||'')}" placeholder="2024"></div><div><label class="field-label" for="editGenre">GENRE</label><input class="field-control" id="editGenre" name="genre" value="${esc(g.genre||'')}" placeholder="Action adventure"></div><div class="edit-full"><label class="field-label" for="editDescription">DESCRIPTION / NOTES</label><textarea class="field-control" id="editDescription" name="description" placeholder="Notes about this game">${esc(g.description||'')}</textarea></div></form>`,`<div><button class="ghost-btn" data-action="close">Cancel</button></div><div><button class="primary-btn" data-action="save-edit" data-id="${esc(gid)}">${icon('check')} Save game</button></div>`,'medium')}
function openTrailer(gid){openDetail(gid)}
async function favoriteGame(gid){const g=gameById(gid);if(!g||g.preview)return;try{await api('/api/game/update','POST',{id:gid,favorite:!g.favorite});g.favorite=!g.favorite;app.stats.favorites=app.games.filter(x=>x.favorite).length;render();if(app.currentModal){openDetail(gid)}else toast(g.favorite?'Added to Favorites':'Removed from Favorites')}catch(e){toast(e.message,'error')}}
async function scanNow(){try{const d=await api('/api/scan','POST');toast(d.started?'Scanning your PlayStation folders...':'Scan is already running');pollStatus()}catch(e){toast(e.message,'error')}}
async function enrichNow(gid){
 if(!app.games.length){toast('First add your PS4/PS5 game folders','error');return}
 try{
  const d=await api('/api/enrich','POST',gid?{id:gid}:{force:true,missing_only:true,artwork_only:true});
  toast(d.started?(gid?'Refreshing this game’s artwork and trailer…':'Finding covers for only the unmatched games…'):'Artwork lookup is already running.');
  pollStatus();
 }catch(e){toast(e.message,'error')}
}
async function addFolder(form){const path=form.folderPath.value.trim(),platform=form.platform.value;if(!path){toast('Choose or paste a folder path first','error');return}try{await api('/api/folders/add','POST',{path,platform});closeModal();await loadLibrary();toast('Folder added. Scanning its games now...');pollStatus()}catch(e){toast(e.message,'error')}}
async function removeFolder(id){if(!confirm('Remove this folder from the library index? Your game files will stay untouched.'))return;try{await api('/api/folders/remove','POST',{id});await loadLibrary();showFolders();toast('Folder removed from the catalog. Game files untouched.');pollStatus()}catch(e){toast(e.message,'error')}}
async function saveSettings(){
 const f=document.querySelector('#settingsForm');if(!f)return;
 try{
 await api('/api/settings','POST',{
  steamgriddb_key:f.steamgriddb_key.value.trim(),rawg_key:f.rawg_key.value.trim(),youtube_key:f.youtube_key.value.trim(),
  wiki_fallback:document.querySelector('#wikiFallback').checked,
  auto_artwork:document.querySelector('#autoArtwork').checked,
  auto_trailers:document.querySelector('#autoTrailers').checked
 });
 closeModal();toast('Artwork settings saved.');
 if(app.games.length)enrichNow();
 }catch(e){toast(e.message,'error')}
}
async function saveEdit(id){const f=document.querySelector('#editGameForm');if(!f)return;const payload={id};for(const k of ['custom_title','cover_url','custom_cover','trailer_url','year','genre','description'])payload[k]=f.elements[k].value.trim();if(payload.trailer_url&&!videoId(payload.trailer_url)){toast('Please enter a valid YouTube video URL','error');return}try{await api('/api/game/update','POST',payload);await loadLibrary();openDetail(id);toast('Game customized successfully')}catch(e){toast(e.message,'error')}}
let isStatusPolling=false;
let lastRefresh=0;
async function pollStatus(){
 if(isStatusPolling)return;isStatusPolling=true;
 try{
  const status=await api('/api/status');const scan=status.scan||{},en=status.enrich||{};
  const active=status.active_lookups||[];
  const revisionChanged=app.seenRevision!==undefined&&app.seenRevision!==(status.revision||0);
  app.seenRevision=status.revision||0;
  const scanJustFinished=app.lastScanProgress&&!scan.running;
  const artJustFinished=app.busyArtwork&&!en.running;
  app.lastScanProgress=!!scan.running;app.busyArtwork=!!en.running;
  const isActive=!!(scan.running||en.running||active.length);
  if(scan.running){
   const folder=scan.current?scan.current.split(/[\/]/).slice(-2).join('/'):'your folders';
   PATHS.banner.innerHTML=`<div class="banner progress-banner">${icon('refresh-cw')}<span><strong>Scanning games…</strong> ${scan.matched_files||0} game files found. ${esc(folder)}</span><span class="lookup-spinner"></span></div>`;
  }else if(en.running){
   PATHS.banner.innerHTML=`<div class="banner progress-banner">${icon('sparkles')}<span><strong>Searching game covers…</strong> ${en.done||0} of ${en.total||0} titles checked. ${esc(en.message||'')}</span><div class="banner-progress"><div style="width:${en.total?Math.max(5,100*en.done/en.total):0}%"></div></div></div>`;
  }else if(!isActive&&app.dataLoaded){renderBanner()}
  const needRefresh=revisionChanged||scanJustFinished||artJustFinished||((en.running||active.length)&&Date.now()-lastRefresh>2900);
  if(needRefresh){
   lastRefresh=Date.now();
   const detailId=app.detailOpenId,old=detailId?gameById(detailId):null;
   const signature=old?String(old.trailer_url||'')+'|'+String(old.cover_cached||false)+'|'+String(old.cover_url||'')+'|'+String(old.custom_cover||'') :'';
   await loadLibrary();
   const next=detailId?gameById(detailId):null;
   if(detailId&&next&&app.detailOpenId===detailId){
    const newSignature=String(next.trailer_url||'')+'|'+String(next.cover_cached||false)+'|'+String(next.cover_url||'')+'|'+String(next.custom_cover||'');
    if(signature!==newSignature){openDetail(detailId,false)}
   }
   if(scanJustFinished&&scan.errors?.length)toast(scan.errors.slice(0,2).join('; '),'error');
   else if(scanJustFinished)toast(`Finished scanning: ${app.games.length} games indexed`);
   if(artJustFinished){
    toast(`${app.stats.covers||0} cover images saved. ${Math.max(0,(app.stats.games||0)-(app.stats.covers||0))} still missing — use Cover report for errors.`);
   }
  }
 }catch(e){console.warn('Status check:',e)}finally{isStatusPolling=false}
}
async function onClick(e){const clicked=e.target.closest('[data-action], [data-tab]');if(!clicked)return;const action=clicked.dataset.action,tab=clicked.dataset.tab;if(tab){app.filter=tab;render();return}if(!action)return;const id=clicked.dataset.id;
  if(action==='close'){closeModal();return}
  if(action==='close-backdrop'){if(e.target===clicked)closeModal();return}
  if(action==='folders'){showFolders();return}
  if(action==='settings'){showSettings();return}
  if(action==='detail'){openDetail(id);return}
  if(action==='edit'){openEdit(id);return}
  if(action==='trailer'){openTrailer(id);return}
  if(action==='favorite'){await favoriteGame(id);return}
  if(action==='scan'){await scanNow();return}
  if(action==='metadata'){await enrichNow(null);return}
  if(action==='enrich-one'){await enrichNow(id);return}
  if(action==='remove-folder'){await removeFolder(id);return}
  if(action==='save-settings'){await saveSettings();return}
  if(action==='save-edit'){await saveEdit(id);return}
  if(action==='cover-inbox'){try{const d=await api('/api/cover-inbox/open','POST');toast('Cover Inbox opened. Use Game Name.jpg or CUSA12345.png, then retry missing covers.')}catch(err){toast(err.message,'error')}return}
  if(action==='cover-report'){window.location.href='/api/cover-report';toast('Artwork report downloaded: see missing titles and exact errors');return}
  if(action==='export'){window.location.href='/api/export';toast('Library list export started');return}
  if(action==='browse-folder'){try{clicked.disabled=true;const d=await api('/api/folders/browse','POST');if(d.path){document.querySelector('#folderPath').value=d.path}else toast('Folder selection canceled. You can paste a path manually.')}catch(err){toast(err.message,'error')}finally{clicked.disabled=false}return}
  if(action==='browse-cover'){try{clicked.disabled=true;const d=await api('/api/cover/browse','POST');if(d.path)document.querySelector('#editCoverPath').value=d.path}catch(err){toast(err.message,'error')}finally{clicked.disabled=false}return}
  if(action==='open-path'){try{await api('/api/open','POST',{path:clicked.dataset.path})}catch(err){toast(err.message,'error')}return}
}
document.addEventListener('click',onClick);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&app.currentModal)closeModal();if(e.key==='Enter'&&e.target.matches('.game-card,[data-action="trailer"][role="button"]')){e.preventDefault();e.target.click()}});
document.addEventListener('submit',e=>{if(e.target.id==='addFolderForm'){e.preventDefault();addFolder(e.target)}if(e.target.id==='settingsForm'){e.preventDefault();saveSettings()}if(e.target.id==='editGameForm'){e.preventDefault();saveEdit(app.selectedId)}});
document.querySelector('#sortInput').addEventListener('change',e=>{app.sort=e.target.value;renderGrid()});
document.querySelector('#searchInput').addEventListener('input',e=>{app.search=e.target.value;renderGrid()});

replaceStaticIcons();loadLibrary().catch(e=>toast(e.message,'error')).finally(pollStatus);setInterval(pollStatus,1500);
