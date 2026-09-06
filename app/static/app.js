'use strict';
const $ = s => document.querySelector(s);
const esc = x => String(x ?? '—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stamp = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Time not supplied';
const config = {
 earth:['Earthquakes','◉','#fa927b'], aviation:['Flights','✈','#78baff'], marine:['Marine','◈','#68d9c4'],
 space:['Satellites','◎','#c7a0ff'], weather:['Weather','☀','#edb75e'], air:['Air quality','≋','#a4d782'],
 traffic:['Road traffic','⇄','#f7cc76'], signals:['Global signals','⌁','#f299c3'], cams:['Live cameras','▣','#9faecc']
};
const state = {}, enabled = new Set(['earth','signals','space','weather','aviation','marine','traffic']), pending = new Set();
let globe, generation=0, records=[], satelliteRecords=[];
const markerPaths={aviation:'M12 2L14 9L22 14V16L14 13L14 19L17 21V23L12 21L7 23V21L10 19V13L2 16V14L10 9Z',marine:'M5 10V5H10V2H14V5H19V10L22 12L19 20H5L2 12ZM7 7V10L12 8L17 10V7ZM4 22L8 21L12 22L16 21L20 22',space:'M9 8H15V16H9ZM1 6H6V18H1ZM18 6H23V18H18ZM6 11H9M15 11H18M12 3V8M12 16V21'};
function markerSVG(layer){return '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="'+markerPaths[layer]+'" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linejoin="round"/></svg>';}
for(const key of Object.keys(markerPaths))config[key][1]=markerSVG(key);
function markerElement(item){
 const button=document.createElement('button');button.className='entity-marker';button.style.cssText='color:'+config[item.layer][2]+';background:#0c1420dd;border:1px solid currentColor;border-radius:50%;width:34px;height:34px;padding:4px;display:grid;place-items:center;box-shadow:0 0 12px #0008;pointer-events:auto';
 button.innerHTML=markerSVG(item.layer);button.title=item.title+' · '+item.source;button.setAttribute('aria-label',button.title);button.onclick=()=>showDetail(item);return button;
}
const coords = {Hyderabad:[17.385,78.487],Mumbai:[19.076,72.878],'New Delhi':[28.614,77.209],Chennai:[13.083,80.271],Bengaluru:[12.972,77.595],Kolkata:[22.573,88.364]};
function safeLink(url) { try {const u=new URL(url);return u.protocol==='https:'?u.href:null;}catch{return null;} }
function initGlobe() {
 if(!window.Globe){$('#globe').innerHTML='<div class="globe-message">3D library could not load. All available records remain accessible below.</div>';return;}
 try {
 const host=$('#globe'); host.innerHTML='';
 globe=new Globe(host).backgroundColor('rgba(0,0,0,0)').globeImageUrl('https://cdn.jsdelivr.net/npm/three-globe@2.45.2/example/img/earth-blue-marble.jpg')
 .bumpImageUrl('https://cdn.jsdelivr.net/npm/three-globe@2.45.2/example/img/earth-topology.png')
 .atmosphereColor('#719fbf').atmosphereAltitude(.16)
 .pointLat('lat').pointLng('lng').pointAltitude(d=>d.altitude||(d.layer==='traffic'?.0001:.008)).pointRadius(d=>d.layer==='space'?.16:d.layer==='traffic'?.01:.13)
 .pointColor(d=>config[d.layer][2]).pointLabel(d=>esc(d.title)+'<br>'+esc(d.source)).onPointClick(showDetail)
 .pathPoints('path').pathPointLat('latitude').pathPointLng('longitude').pathColor(()=> '#f7cc76').pathStroke(3).pathTransitionDuration(0)
 .pointsTransitionDuration(0);
 globe.htmlLat('lat').htmlLng('lng').htmlAltitude(d=>d.altitude||.008).htmlElement(markerElement);
 globe.pointOfView({lat:20,lng:70,altitude:2.25});
 globe.controls().autoRotateSpeed=.3;
 new ResizeObserver(()=>{globe.width(host.clientWidth).height(host.clientHeight);}).observe(host);
 } catch {$('#globe').innerHTML='<div class="globe-message">WebGL unavailable. Use the searchable evidence list below.</div>';globe=null;}
}
function propagateSatellites(){
 satelliteRecords=[];
 if(!window.satellite || !enabled.has('space'))return;
 for(const entry of state.space?.items||[]){
  try{
   const sat=satellite.twoline2satrec(entry.tle1,entry.tle2), epoch=new Date((sat.jdsatepoch-2440587.5)*86400000);
   if(Math.abs(Date.now()-epoch.getTime())>14*86400000)continue;
   const date=new Date(), pv=satellite.propagate(sat,date);
   if(!pv.position)continue;
   const geo=satellite.eciToGeodetic(pv.position,satellite.gstime(date));
   const lat=satellite.degreesLat(geo.latitude),lng=satellite.degreesLong(geo.longitude);
   if(!Number.isFinite(lat)||!Number.isFinite(lng))continue;
   satelliteRecords.push({title:entry.title,id:entry.title,lat,lng,altitude:Math.max(.015,geo.height/6371),altitude_km:Math.round(geo.height),time:date.toISOString(),epoch:epoch.toISOString(),source:entry.source||'CelesTrak · SGP4 estimate',url:entry.url||'https://celestrak.org/NORAD/elements/',layer:'space'});
  }catch{ /* A bad element record does not disable other satellites. */ }
 }
}
function render(){
 propagateSatellites();
 records=Object.keys(config).filter(k=>enabled.has(k)&&k!=='space').flatMap(k=>state[k]?.items||[]).concat(satelliteRecords);
 const query=$('#search').value.trim().toLowerCase();
 records=records.filter(x=>String(x.title).toLowerCase().includes(query));
 if(globe){const icons=records.filter(x=>markerPaths[x.layer]).slice(0,500), iconSet=new Set(icons);globe.htmlElementsData(icons);globe.pointsData(records.filter(x=>!iconSet.has(x)));globe.pathsData(enabled.has('traffic')?(state.traffic?.items||[]).filter(x=>x.path?.length>1):[]);}
 $('#visible-count').textContent=records.length;
 $('#layers').innerHTML=Object.entries(config).map(([key,[name,icon,color]])=>'<button class="layer" data-layer="'+key+'" aria-pressed="'+enabled.has(key)+'" style="--color:'+color+'"><span class="icon">'+icon+'</span><span class="copy">'+name+'<small>'+esc(pending.has(key)?'Loading…':state[key]?.status||'Select to load')+'</small></span><span class="count">'+(key==='space'?satelliteRecords.length:(state[key]?.items?.length??'—'))+'</span></button>').join('');
 $('#layers').querySelectorAll('button').forEach(b=>b.onclick=()=>toggle(b.dataset.layer));
 $('#sources').innerHTML=Object.entries(state).map(([key,data])=>'<button style="width:100%;background:transparent;text-align:left" data-source="'+key+'" class="source-row '+(['available','connected'].includes(data.status)?'good':'')+'"><b>'+config[key][0]+'</b><span>'+esc(data.status)+'</span></button>').join('');
 $('#sources').querySelectorAll('button').forEach(b=>b.onclick=()=>showCoverage(b.dataset.source));
 const filter=$('#event-filter').value;
 const shown=records.filter(x=>filter==='all'||x.layer===filter).sort((a,b)=>(Date.parse(b.time)||0)-(Date.parse(a.time)||0)).slice(0,80);
 $('#events').innerHTML=shown.length?shown.map((x,i)=>'<button class="event" data-record="'+i+'" style="--color:'+config[x.layer][2]+'"><div class="category">'+config[x.layer][0]+'</div><b>'+esc(x.title)+'</b><small>'+esc(x.source)+'<br>'+esc(stamp(x.time))+'</small></button>').join(''):'<div class="empty">'+(pending.size?'Loading selected feeds…':'No matching records. Enable a layer or clear the search. Empty coverage does not mean nothing is happening.')+'</div>';
 $('#events').querySelectorAll('button').forEach(b=>b.onclick=()=>showDetail(shown[+b.dataset.record]));
 const failed=Object.values(state).filter(s=>['unavailable','stale','provider_rejected'].includes(s.status)).length;
 $('#status').textContent=pending.size?'Loading '+pending.size+' feed(s)…':failed?failed+' feed(s) stale / unavailable':'Sources checked · '+new Date().toLocaleTimeString();
 renderLocal();
 const watch=(state.earth?.items||[]).filter(x=>x.magnitude>=5);
 $('#watchlist').innerHTML=watch.map((x,i)=>'<button class="watch" data-watch="'+i+'">'+esc(x.title)+'</button>').join('')||'<p class="muted">'+(state.earth?.status==='available'?'No M5+ events in the loaded past-hour feed.':'Earthquake feed not available for assessment.')+'</p>';
 $('#watchlist').querySelectorAll('button').forEach(b=>b.onclick=()=>showDetail(watch[+b.dataset.watch]));
}
function transportStatus(key){
 const data=state[key];
 if(pending.has(key)&&!data)return 'Loading source…';
 if(!data)return 'Waiting to load';
 if(data.status==='not_configured')return 'Server key missing';
 if(data.status==='provider_rejected')return 'Provider rejected connection';
 if(data.status==='unavailable')return data.reason||'Provider unavailable';
 if(data.status==='stale')return 'Cached data · source currently unavailable';
 if(['connecting','reconnecting'].includes(data.status))return data.status==='connecting'?'Connecting to AISStream…':'Reconnecting to AISStream…';
 if(!data.items?.length)return key==='marine'?'Waiting for vessel reports in coverage':'No reports returned in this coverage';
 return data.items.length+' '+(key==='aviation'?'aircraft in cached snapshot':key==='marine'?'vessel reports':'road segment sample');
}
function renderLocal(){
 const weather=state.weather?.items?.[0],air=state.air?.items?.[0],w=weather?.metrics||{},a=air?.metrics||{};
 const values=[['Temperature',w.temperature_2m,'°C'],['Wind',w.wind_speed_10m,'km/h'],['Rain',w.precipitation,'mm'],['US AQI',a.us_aqi,'']];
 $('#local').innerHTML='<div class="metrics">'+values.map(([name,value,unit])=>'<div class="metric"><strong>'+esc(value??'—')+' <small>'+unit+'</small></strong><small>'+name+'</small></div>').join('')+'</div>';
 const complete=state.weather?.status==='available'&&['temperature_2m','wind_speed_10m','precipitation'].every(k=>typeof w[k]==='number');
 const flags=[];if(w.temperature_2m>=40)flags.push('High heat');if(w.wind_speed_10m>=45)flags.push('Strong winds');if(w.precipitation>=10)flags.push('Heavy precipitation');
 $('#local').innerHTML+='<div class="risk">'+(!complete?'Local assessment incomplete: weather missing or stale.':flags.length?esc(flags.join(' · '))+' · illustrative weather triggers':'No configured weather threshold exceeded. This is not an all-clear.')+'</div><p class="muted">Weather valid: '+esc(stamp(weather?.time))+'<br>Air valid: '+esc(stamp(air?.time))+'<br>Model estimates · US AQI is not Indian AQI.</p>';
 const t=state.traffic?.items?.[0];
 if(t)$('#local').innerHTML+='<div class="note">Road sample: '+esc(t.metrics.currentSpeed)+' / '+esc(t.metrics.freeFlowSpeed)+' km/h free-flow. One segment only.</div>';
 $('#local').innerHTML+='<div class="section-head"><h2>Transport coverage</h2></div>'+['aviation','marine','traffic'].map(key=>'<button class="watch" data-transport="'+key+'"><b style="color:'+config[key][2]+'">'+config[key][1]+' '+config[key][0]+'</b><br>'+esc(transportStatus(key))+'<small style="display:block;color:var(--muted)">'+(key==='aviation'?(state.aviation?.items?.[0]?.source?.startsWith('adsb.lol')?'250 nm radius · snapshots cached 2 min':'City region · snapshots cached 30 min'):key==='marine'?'Selected sea sectors · expires after 10 min':'City center · one sampled road')+' · '+(enabled.has(key)?'Layer on':'Layer off')+'</small></button>').join('');
 $('#local').querySelectorAll('[data-transport]').forEach(b=>b.onclick=()=>{const key=b.dataset.transport;enabled.add(key);const item=state[key]?.items?.[0];if(item)showDetail(item);else showCoverage(key);render();});
}
async function loadLayer(key){
 if(pending.has(key))return;
 pending.add(key);render();
 const version=generation, cityScoped=['weather','air','traffic','aviation'].includes(key);
 try{
  const response=await fetch('/api/layers/'+key+'?city='+encodeURIComponent($('#city').value),{signal:AbortSignal.timeout(45000)});
  if(!response.ok)throw Error('Source unavailable');
  const data=await response.json();
  if(!cityScoped||version===generation)state[key]=data;
 }catch{if(!cityScoped||version===generation)state[key]={status:'unavailable',items:[],coverage:'Request failed or timed out. Try Refresh.'};}
 finally{pending.delete(key);render();if(version!==generation&&['weather','air','traffic','aviation'].includes(key)&&(enabled.has(key)||['weather','air'].includes(key)))loadLayer(key);}
}
function toggle(key){
 if(enabled.has(key)){enabled.delete(key);render();return;}
 enabled.add(key);
 if(state[key]){render();if(key==='cams')showCoverage(key);}else loadLayer(key).then(()=>{if(key==='cams')showCoverage(key);});
}
function showCoverage(key){
 const data=state[key]||{};
 $('#detail').innerHTML='<div class="eyebrow">SOURCE COVERAGE</div><h2>'+config[key][0]+'</h2><p>'+esc(data.coverage||'Source request has not completed.')+'</p><p class="note">'+esc(data.status||'Loading')+(data.reason?' · '+esc(data.reason):'')+'</p>'+ (data.links||[]).map(l=>safeLink(l.url)?'<p><a target="_blank" rel="noopener noreferrer" href="'+esc(safeLink(l.url))+'">'+esc(l.title)+' ↗</a></p>':'').join('');
 if(data.diagnostics)$('#detail').innerHTML+='<div class="note">Stream messages: '+esc(data.diagnostics.messages)+'<br>Accepted position reports: '+esc(data.diagnostics.positions)+'<br>Last message: '+esc(stamp(data.diagnostics.last_message_at))+'</div>';
 openDrawer();
}
function openDrawer(){if(!$('#drawer').open)$('#drawer').showModal();}
function showDetail(item){
 const source=state[item.layer]||{},url=safeLink(item.url);
 const details={...item.metrics,altitude_km:item.altitude_km,altitude_m:item.altitude_m,speed_kn:item.speed_kn,speed_ms:item.speed_ms,element_epoch:item.epoch,received_at:item.received_at};
 $('#detail').innerHTML='<div class="eyebrow">'+config[item.layer][0].toUpperCase()+' / EVIDENCE</div><h2>'+esc(item.title)+'</h2><p class="muted">'+esc(source.coverage)+'</p><dl><dt>Latitude / longitude</dt><dd>'+Number(item.lat).toFixed(3)+' / '+Number(item.lng).toFixed(3)+'</dd><dt>Record time</dt><dd>'+esc(stamp(item.time))+'</dd><dt>Source</dt><dd>'+esc(item.source)+'</dd><dt>Fetched</dt><dd>'+esc(stamp(source.fetched_at))+'</dd>'+Object.entries(details).filter(([k,v])=>v!=null&&!['time','interval'].includes(k)).map(([k,v])=>'<dt>'+esc(k.replaceAll('_',' '))+'</dt><dd>'+esc(v)+' '+esc(item.units?.[k]||'')+'</dd>').join('')+'</dl><div class="note">Confidence: not independently assessed. Check source age, coverage, and official guidance.</div>'+(url?'<p><a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">Open original source ↗</a></p>':'');
 openDrawer();
 if(globe)globe.pointOfView({lat:item.lat,lng:item.lng,altitude:item.layer==='traffic'?.01:1.7},700);
}
async function refresh(){ $('#refresh').disabled=true;await Promise.all([...new Set([...enabled,'weather','air'])].map(loadLayer));$('#refresh').disabled=false; }
$('#event-filter').innerHTML+=Object.entries(config).map(([k,v])=>'<option value="'+k+'">'+v[0]+'</option>').join('');
$('#refresh').onclick=refresh;$('#search').oninput=render;$('#event-filter').onchange=render;
$('#close').onclick=()=>$('#drawer').close();
$('#city').onchange=async()=>{generation++;for(const key of ['weather','air','traffic','aviation'])delete state[key];$('#home').click();render();await refresh();};
$('#home').onclick=()=>{const [lat,lng]=coords[$('#city').value];if(globe)globe.pointOfView({lat,lng,altitude:1.9},800);};
$('#rotate').onclick=()=>{if(!globe)return;const value=!globe.controls().autoRotate;globe.controls().autoRotate=value;$('#rotate').setAttribute('aria-pressed',value);$('#rotate').textContent=value?'Ⅱ Pause':'▶ Rotate';};
for(const [id,factor] of [['zoom-in',.8],['zoom-out',1.25]])$('#'+id).onclick=()=>{if(globe)globe.pointOfView({altitude:Math.max(.3,Math.min(5,globe.pointOfView().altitude*factor))},300);};
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();$('#search').focus();}});
initGlobe();refresh();
setInterval(()=>{if(!document.hidden&&enabled.has('marine'))loadLayer('marine');},15000);
setInterval(()=>{if(!document.hidden&&enabled.has('space'))render();},10000);
setInterval(()=>{if(!document.hidden)refresh();},120000);
