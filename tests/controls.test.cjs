const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function boot(webgl=true) {
  const nodes=new Map(), calls=[], classes=new Set();
  function node(key='') {
    if(nodes.has(key))return nodes.get(key);
    const element={value:key==='#city'?'Hyderabad':key==='#event-filter'?'all':'',innerHTML:'',textContent:'',style:{},hidden:false,disabled:false,clientWidth:800,clientHeight:600,children:[],attributes:{},querySelectorAll:()=>[],querySelector:()=>null,addEventListener(){},setAttribute(k,v){this.attributes[k]=String(v);},insertAdjacentHTML(){},appendChild(x){this.children.push(x);},click(){this.onclick?.();},showModal(){this.open=true;},close(){this.open=false;},focus(){}};
    nodes.set(key,element);return element;
  }
  const controls={autoRotate:false}, view={lat:20,lng:70,altitude:2.25};
  let api;api=new Proxy({}, {get(_,key){if(key==='controls')return ()=>controls;if(key==='lights')return ()=>[];if(key==='globeMaterial')return ()=>({});if(key==='pointOfView')return opts=>{if(!opts)return view;Object.assign(view,opts);calls.push([key,opts]);return api;};return (...args)=>{calls.push([key,...args]);return api;};}});
  const context={console,document:{querySelector:node,createElement:()=>node('element'+Math.random()),addEventListener(){},activeElement:{tagName:'BODY'},body:{classList:{toggle(key){if(classes.has(key)){classes.delete(key);return false;}classes.add(key);return true;}}}},Globe:webgl?function(){return api;}:undefined,ResizeObserver:class{observe(){}},fetch:()=>new Promise(()=>{}),setInterval(){},AbortSignal,URL};
  context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/app.js','utf8'),context);
  return {node,calls,classes,controls,view,context};
}

test('day/night, icon size and expand controls toggle both ways',()=>{
 const b=boot();b.node('#earth-style').click();assert.match(b.calls.at(-1)[1],/earth-night/);b.node('#earth-style').click();assert.match(b.calls.at(-1)[1],/earth-blue-marble/);
 for(const [id,cls] of [['marker-size','larger-icons'],['expand-view','expanded-globe']]){b.node('#'+id).click();assert.ok(b.classes.has(cls));b.node('#'+id).click();assert.ok(!b.classes.has(cls));}
});
test('zoom, rotate and home controls update the globe',()=>{
 const b=boot();b.node('#zoom-in').click();assert.ok(b.view.altitude<2.25);b.node('#zoom-out').click();assert.equal(b.view.altitude,2.25);b.node('#rotate').click();assert.equal(b.controls.autoRotate,true);b.node('#rotate').click();assert.equal(b.controls.autoRotate,false);
 vm.runInContext("following={id:'test',layer:'aviation'}",b.context);b.node('#home').click();assert.equal(vm.runInContext('following',b.context),null);assert.equal(b.view.lat,17.385);
});
test('no WebGL disables controls instead of leaving inert buttons',()=>{
 const b=boot(false);for(const id of ['home','rotate','zoom-in','zoom-out','earth-style'])assert.equal(b.node('#'+id).disabled,true);
});
test('detail text is escaped and follow button exists for an aircraft',()=>{
 const b=boot();vm.runInContext("showDetail({title:'<script>bad</script>',id:'abc',layer:'aviation',lat:17,lng:78,source:'test',time:null})",b.context);
 assert.ok(b.node('#detail').innerHTML.includes('&lt;script&gt;'));assert.equal(b.node('#detail').children[0].textContent,'Follow incoming position updates');
});

test('map labels enable tiles, credit the source, and stop rotation',()=>{
 const b=boot();b.node('#rotate').click();b.node('#map-detail').click();
 const tile=b.calls.find(x=>x[0]==='globeTileEngineUrl');
 assert.equal(tile[1](3,4,5),'https://tile.openstreetmap.org/5/3/4.png');
 assert.equal(b.node('#map-attribution').hidden,false);
 assert.equal(b.controls.autoRotate,false);
 assert.equal(b.node('#rotate').disabled,true);
 b.node('#map-detail').click();
 assert.equal(b.calls.filter(x=>x[0]==='globeTileEngineUrl').at(-1)[1],null);
 assert.equal(b.node('#map-attribution').hidden,true);
 assert.equal(b.node('#rotate').disabled,false);
});
test('camera drawer contains the official player and source link',()=>{
 const b=boot();vm.runInContext("showCoverage('cams')",b.context);
 assert.match(b.node('#detail').innerHTML,/youtube.com\/embed\/awQzjn72bI0/);
 assert.ok(b.node('#drawer').open);
});
