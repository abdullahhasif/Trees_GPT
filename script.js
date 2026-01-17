// script.js - Final Version with Control Positioning

// --- Configuration ---
const API_URL = "http://127.0.0.1:5001/query";
const NYC_LAT = 40.7128; const NYC_LNG = -74.0060; const INITIAL_ZOOM = 11;

// --- DOM Elements ---
const queryInput = document.getElementById('query-input');
const queryButton = document.getElementById('query-button');
const statusMessage = document.getElementById('status-message');
const treeCountElement = document.getElementById('tree-count');
const speciesCountElement = document.getElementById('species-count');
const avgDiameterElement = document.getElementById('avg-diameter');
const speciesBarsElement = document.getElementById('species-bars');
const statusBarsElement = document.getElementById('status-bars');
const exampleTags = document.querySelectorAll('.example-tag');

// --- Map Initialization ---
let map = null; let treeLayer = null; let legendControl = null;
let currentGeoJsonData = null; let mapClickPopup = null; let baseLayerControl = null;

// --- Styling Functions (Unchanged) ---
const statusColors = { 'Good': '#2ecc71', 'Excellent': '#27ae60', 'Fair': '#f1c40f', 'Poor': '#e67e22', 'Dead': '#e74c3c', 'Stump': '#95a5a6', 'Default': '#3498db' };
function getStatusColor(status) { if (!status) return statusColors['Default']; if (statusColors[status]) return statusColors[status]; const n = status.toLowerCase(); for (const [k, v] of Object.entries(statusColors)) { if (k.toLowerCase() === n) return v; } return statusColors['Default']; }
function getCircleMarkerRadius(dbh) { if (dbh === null || dbh === undefined || isNaN(dbh) || dbh <= 0) return 5; if (dbh < 5) return 5; if (dbh < 10) return 6; if (dbh < 15) return 7; if (dbh < 20) return 8; if (dbh < 25) return 10; if (dbh < 30) return 12; if (dbh < 40) return 14; return 16; }
function createCustomPopup(p) { if (!p) return ''; let s = p.spc_common||'Unknown'; if (s.includes(',')){ const pts = s.split(',').map(pt=>pt.trim());s=pts[1]+' '+pts[0];s=s.toLowerCase().split(' ').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join(' ');} let b=p.boroname;if(b==='5')b='Staten Island'; return `<div class="custom-popup"><div class="custom-popup-header">${s}</div><div class="custom-popup-content"><div class="popup-label">Status:</div><div class="popup-value">${p.status||'Unknown'}</div><div class="popup-label">Diameter:</div><div class="popup-value">${p.tree_dbh?p.tree_dbh+' inches':'Unknown'}</div><div class="popup-label">Address:</div><div class="popup-value">${p.address||'Unknown'}</div><div class="popup-label">Borough:</div><div class="popup-value">${b||'Unknown'}</div></div></div>`;}

// --- Map Functions ---
function initializeMap() {
    if (map) return;
    map = L.map('map', { zoomControl: false, minZoom: 10, maxZoom: 18 }) // Disable default zoom control
           .setView([NYC_LAT, NYC_LNG], INITIAL_ZOOM);

    const cartoLight = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '© OSM contributors © CARTO', maxZoom: 20 });
    const cartoDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { attribution: '© OSM contributors © CARTO', maxZoom: 20 });
    cartoLight.addTo(map);

    const baseMaps = { "Light Grayscale": cartoLight, "Dark Grayscale": cartoDark };

    // --- Add Controls in Specific Positions ---
    if (baseLayerControl) map.removeControl(baseLayerControl);
    baseLayerControl = L.control.layers(baseMaps, null, { position: 'topright', collapsed: true }).addTo(map); // Basemaps top-right

    L.control.zoom({ position: 'topleft' }).addTo(map); // Zoom top-left

    createLegend(); // Legend position set inside this function (bottomleft)
    setupMapClickHandler();
    updateStatusMessage('Enter query or click example');
    console.log("Map initialized with controls positioned.");
}

function createLegend() {
    if (legendControl) map.removeControl(legendControl);
    legendControl = L.control({ position: 'bottomleft' }); // Set legend position here
    legendControl.onAdd = function(map) { const div = L.DomUtil.create('div', 'custom-legend');
        div.innerHTML += '<h4>Status</h4>';
        for (const status in statusColors) { if (status !== 'Default') { div.innerHTML += `<div class="legend-item"><i class="legend-color" style="background:${statusColors[status]}"></i> ${status}</div>`; } }
        div.innerHTML += '<br><div class="legend-scale"><p>Tree Diameter</p><div class="scale-circles"><div class="scale-circle" style="width: 10px; height: 10px;"></div><div class="scale-circle" style="width: 16px; height: 16px;"></div><div class="scale-circle" style="width: 24px; height: 24px;"></div></div><div class="scale-labels"><span>Small</span><span>Med</span><span>Large</span></div></div>';
        return div;
     };
    legendControl.addTo(map);
}

function setupMapClickHandler() { /* ... unchanged ... */
    if (!map) return; map.on('click', (e) => { const lat=e.latlng.lat.toFixed(5), lng=e.latlng.lng.toFixed(5); const pc=`Lat: ${lat}<br>Lng: ${lng}`; if(mapClickPopup) map.closePopup(mapClickPopup); mapClickPopup=L.popup({closeButton:true,autoClose:true}).setLatLng(e.latlng).setContent(pc).openOn(map);}); console.log("Map click listener added.");}
function displayTrees(geojsonData) { /* ... unchanged ... */
    currentGeoJsonData=geojsonData; if(treeLayer && map.hasLayer(treeLayer)) map.removeLayer(treeLayer); treeLayer=null;
    if (!geojsonData?.features?.length){updateStatusMessageWithLimit("No matching trees found.",geojsonData);updateStats(null);return;}
    treeLayer=L.markerClusterGroup({spiderfyOnMaxZoom:true,showCoverageOnHover:true,zoomToBoundsOnClick:true,disableClusteringAtZoom:17});
    const gl=L.geoJSON(geojsonData,{pointToLayer:(f,l)=>{const p=f.properties||{},d=parseFloat(p.tree_dbh),s=p.status;return L.circleMarker(l,{radius:getCircleMarkerRadius(d),fillColor:getStatusColor(s),color:"#fff",weight:1,opacity:1,fillOpacity:0.8});},onEachFeature:(f,l)=>{if(f.properties)l.bindPopup(createCustomPopup(f.properties),{maxWidth:300,minWidth:250,className:'custom-popup-container'});}});
    treeLayer.addLayer(gl);map.addLayer(treeLayer);console.log(`Displayed ${geojsonData.features.length} via MarkerCluster.`);updateStats(geojsonData);updateStatusMessageWithLimit(`Displaying clustered results.`,geojsonData);
    try{if(treeLayer.getBounds().isValid())map.fitBounds(treeLayer.getBounds().pad(0.1));} catch(e){console.warn("Could not fit bounds:",e);}
}

// --- Stats Analysis Functions (Unchanged) ---
function updateStats(geojsonData) { /* ... unchanged ... */
    const t=geojsonData?.features;if(!t||t.length===0){treeCountElement.textContent="0";speciesCountElement.textContent="0";avgDiameterElement.textContent="--";speciesBarsElement.innerHTML="<p class='no-data'>No data</p>";statusBarsElement.innerHTML="<p class='no-data'>No data</p>";return;}
    const tc=t.length;treeCountElement.textContent=tc.toLocaleString();const sc={},stc={};let td=0;let vdc=0;
    t.forEach(tr=>{const p=tr.properties;if(!p)return;const sp=p.spc_common;if(sp)sc[sp]=(sc[sp]||0)+1;const st=p.status||'Default';stc[st]=(stc[st]||0)+1;const dbh=parseFloat(p.tree_dbh);if(!isNaN(dbh)&&dbh>0){td+=dbh;vdc++;}});
    const usc=Object.keys(sc).length;speciesCountElement.textContent=usc.toLocaleString();avgDiameterElement.textContent=(vdc>0)?`${(td/vdc).toFixed(1)} in`:"--";updateSpeciesChart(sc);updateStatusChart(stc);
}
function updateStatusChart(statusCounts) { /* ... unchanged ... */
    statusBarsElement.innerHTML="";const ss=Object.entries(statusCounts).sort((a,b)=>b[1]-a[1]);if(ss.length===0){statusBarsElement.innerHTML="<p class='no-data'>No status data.</p>";return;}
    ss.forEach(([s,c])=>{const cl=getStatusColor(s);const i=document.createElement('div');i.className='status-list-item';i.innerHTML=`<div class="status-details"><span class="status-color-box" style="background-color:${cl};"></span><span class="status-name">${s==='Default'?'Unknown':s}</span></div><span class="status-count">${c.toLocaleString()}</span>`;statusBarsElement.appendChild(i);});
}
function updateSpeciesChart(speciesCounts) { /* ... unchanged ... */
    speciesBarsElement.innerHTML="";const ss=Object.entries(speciesCounts).sort((a,b)=>b[1]-a[1]).slice(0,5);if(ss.length===0){speciesBarsElement.innerHTML="<p class='no-data'>No species data.</p>";return;}const mc=ss[0][1];
    ss.forEach(([s,c])=>{let dn=s;if(s.includes(',')){const p=s.split(',').map(pt=>pt.trim());dn=p[1]+' '+p[0];dn=dn.toLowerCase().split(' ').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join(' ');}const pct=(c/mc*100).toFixed(1);const b=document.createElement('div');b.className='species-bar';const fs=`width:${pct}%; background-color:var(--primary-light);`;b.innerHTML=`<div class="species-bar-header"><div class="species-bar-name" title="${dn}">${dn}</div><div class="species-bar-count">${c.toLocaleString()}</div></div><div class="species-bar-progress"><div class="species-bar-fill" style="${fs}"></div></div>`;speciesBarsElement.appendChild(b);});
}

// --- Status Message & Main Query (Unchanged) ---
function updateStatusMessageWithLimit(message, geojsonData) { /* ... unchanged ... */
    let fm=message;const m=geojsonData?.metadata;if(m?.results_limited===true){const dc=geojsonData?.features?.length??0;fm=`Displaying first ${dc.toLocaleString()} clustered results (out of ${m.original_count.toLocaleString()} found).`;}else if(geojsonData?.features?.length>0){const fc=geojsonData.features.length;if(message.includes('clustered results')){fm=`Displaying ${fc.toLocaleString()} clustered results.`;}else{fm=`Displaying ${fc.toLocaleString()} results.`;}}statusMessage.style.opacity='0';setTimeout(()=>{statusMessage.textContent=fm;statusMessage.style.opacity='1';},300);
}
async function queryAndDisplayTrees(queryFromHash=null) { /* ... unchanged ... */
    const uq=queryFromHash||queryInput.value.trim();if(!uq){updateStatusMessageWithLimit("Please enter query.",null);return;}if(queryFromHash)queryInput.value=uq;window.location.hash=encodeURIComponent(uq);updateStatusMessageWithLimit("Processing...",null);queryButton.disabled=true;queryButton.innerHTML='<i class="fas fa-spinner fa-spin"></i>';try{const fp=fetch(API_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:uq}),});const r=await fp;if(!r.ok){let e=`API Error: ${r.status}`;try{const d=await r.json();e+=` - ${d.error||'Unknown'}`;}catch(e){}throw new Error(e);}const g=await r.json();console.log("API response:",g);if(g?.type==="FeatureCollection")displayTrees(g);else throw new Error("Invalid GeoJSON response.");}catch(e){console.error("Query API error:",e);let ed=`Error: ${e.message.split('.')[0]}`;if(e.message.includes('Network')||e.message.includes('fetch'))ed="Network Error: Check API.";updateStatusMessageWithLimit(ed,null);if(treeLayer&&map.hasLayer(treeLayer))map.removeLayer(treeLayer);treeLayer=null;updateStats(null);}finally{queryButton.disabled=false;queryButton.innerHTML='<i class="fas fa-arrow-right"></i>';}
}

// --- Event Listeners & Permalink (Unchanged) ---
queryButton.addEventListener('click',()=>queryAndDisplayTrees());queryInput.addEventListener('keypress',(e)=>{if(e.key==='Enter')queryAndDisplayTrees();});exampleTags.forEach(t=>{t.addEventListener('click',function(){const q=this.getAttribute('data-query');if(q)queryAndDisplayTrees(q);});});function handleHashChange(){const h=window.location.hash.substring(1);if(h){const dq=decodeURIComponent(h);if(dq!==queryInput.value)queryAndDisplayTrees(dq);}}window.addEventListener('hashchange',handleHashChange,false);

// --- Initialize ---
document.addEventListener('DOMContentLoaded',()=>{initializeMap();handleHashChange();});