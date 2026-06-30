#!/usr/bin/env python3
"""Local review UI for V1 **v4.0** Page-Purpose labels — project Overview + page grid +
zoomable viewer + per-page useful_for/importance/observations panel.

Reads v4 labels + pre-rendered page images from disk; writes your corrections back
(label_source=human_reviewed) to a reviewed_<permit>.json. No DB needed.

  pip install fastapi uvicorn
  python tools/review_app.py            # http://localhost:8000

  data/v1_labels_v4/lb_<permit>.json         v4.0 Claude labels
  data/v1_labels_v4/reviewed_<permit>.json   your corrections
  data/v1_pages/<permit>/<image>             rendered page PNGs (page.image references these)
  data/v1_pages/<permit>/thumbs/<image>      small thumbnails for the grid (optional)
"""
import json, os, glob
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(ROOT, "data", "v1_labels_v4")
PAGES = os.path.join(ROOT, "data", "v1_pages")
app = FastAPI()


def _load(permit):
    rev = os.path.join(LABELS, f"reviewed_{permit}.json")
    raw = os.path.join(LABELS, f"lb_{permit}.json")
    return json.load(open(rev if os.path.exists(rev) else raw))


@app.get("/api/projects")
def projects():
    out = []
    for p in sorted(glob.glob(os.path.join(LABELS, "lb_*.json"))):
        lb = json.load(open(p)); permit = lb["permit"]
        out.append({"permit": permit,
                    "category": lb.get("category"),
                    "pages": len(lb.get("pages", [])),
                    "reviewed": os.path.exists(os.path.join(LABELS, f"reviewed_{permit}.json"))})
    return out


@app.get("/api/labels/{permit}")
def labels(permit):
    return _load(permit)


@app.get("/img/{permit}/{name}")
def img(permit, name):
    f = os.path.join(PAGES, permit, name)
    return FileResponse(f) if os.path.exists(f) else JSONResponse({"err": "no image"}, status_code=404)


@app.get("/thumb/{permit}/{name}")
def thumb(permit, name):
    f = os.path.join(PAGES, permit, "thumbs", name)
    if not os.path.exists(f):
        f = os.path.join(PAGES, permit, name)
    return FileResponse(f) if os.path.exists(f) else JSONResponse({"err": "no image"}, status_code=404)


@app.post("/api/save/{permit}")
async def save(permit, request: Request):
    data = await request.json()
    os.makedirs(LABELS, exist_ok=True)
    json.dump(data, open(os.path.join(LABELS, f"reviewed_{permit}.json"), "w"), indent=1)
    return {"ok": True}


INDEX_HTML = r"""<!doctype html><html><head><meta charset=utf-8><title>V1 v4.0 review</title>
<style>
*{box-sizing:border-box} body{margin:0;font:13px/1.45 system-ui;background:#0f1115;color:#e7e9ee}
#bar{height:46px;display:flex;align-items:center;gap:12px;padding:0 14px;background:#171a21;border-bottom:1px solid #283041}
#bar b{font-size:15px} select,button,input{font:inherit}
select,input{background:#1d2230;color:#e7e9ee;border:1px solid #38415a;border-radius:6px;padding:6px 8px}
button{background:#252b3b;color:#e7e9ee;border:1px solid #38415a;border-radius:6px;padding:7px 12px;cursor:pointer}
button.ag{background:#1c5234;border-color:#2c7a4d}
button.on{background:#2b5cc4;border-color:#3b6fe0;color:#fff}
.seg{display:flex;gap:0} .seg button{border-radius:0;border-right:none} .seg button:first-child{border-radius:6px 0 0 6px}
.seg button:last-child{border-radius:0 6px 6px 0;border-right:1px solid #38415a}
#tally{margin-left:auto;color:#9bdcb0}
#wrap{display:flex;height:calc(100vh - 46px)}
#grid{width:230px;overflow:auto;background:#12151c;border-right:1px solid #283041;padding:8px;display:flex;flex-direction:column;gap:6px}
.th{display:flex;gap:8px;align-items:center;padding:5px;border-radius:7px;cursor:pointer;border:1px solid transparent}
.th:hover{background:#1b2030} .th.sel{background:#222a3b;border-color:#3b6fe0}
.th img{width:58px;height:42px;object-fit:cover;background:#000;border-radius:3px;border-left:4px solid #555}
.th small{color:#9aa3b5;font-size:11px} .th .nm{font-weight:600}
.tagdots{display:inline-flex;gap:3px;margin-left:3px}
.tdot{width:7px;height:7px;border-radius:2px;display:inline-block}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-left:4px}
#center{flex:1;overflow:auto;background:#000;position:relative}
#imgwrap{min-height:100%;display:flex;align-items:flex-start;justify-content:center}
#pg{display:block}
#zoombar{position:absolute;top:8px;right:8px;display:flex;gap:4px;background:#171a21cc;border:1px solid #283041;border-radius:8px;padding:4px;z-index:5}
#zoombar button{padding:4px 9px}
#over{flex:1;overflow:auto;padding:22px 30px;background:#0f1115}
#panel{width:360px;background:#12151c;border-left:1px solid #283041;padding:14px;overflow:auto}
.fld{margin:10px 0} .fld label{display:block;color:#9aa3b5;margin-bottom:3px;font-size:12px}
.fld select{width:100%}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:11px;border:1px solid #38415a;border-radius:11px;padding:2px 9px;cursor:pointer;color:#9aa3b5}
.chip.on{background:#2b5cc4;border-color:#3b6fe0;color:#fff} .chip.ro{cursor:default}
.tagchip{font-size:11px;border-radius:11px;padding:2px 9px;border:1px solid}
.timp{display:flex;align-items:center;gap:8px;margin:4px 0}
.timp .nm{flex:1;font-size:12px}
.ev{color:#aab2c5;font-size:12px;background:#171a21;border-radius:6px;padding:8px;margin-top:6px}
.obs{font-size:12px;background:#161a22;border:1px solid #232a36;border-radius:6px;padding:8px;margin-top:6px}
.obs table{width:100%;border-collapse:collapse} .obs td{padding:2px 4px;vertical-align:top}
.obs td.k{color:#8a93a6;white-space:nowrap;width:48%} .obs .yes{color:#7fe0a3} .obs .no{color:#737d90}
.obs h4{margin:8px 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#8a93a6}
h3{margin:4px 0 2px}
.ovh{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.ovh h1{font-size:22px;margin:0}
.badge{font-size:12px;font-weight:600;padding:3px 10px;border-radius:13px;border:1px solid}
.flag{background:#3a3416;border-color:#7a6e2c;color:#ffd86b}
.b-sf{background:#13294a;border-color:#2c5a9a;color:#8fb6ff}
.card{background:#141821;border:1px solid #283041;border-radius:10px;padding:14px 16px;margin:14px 0;max-width:1000px}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#8a93a6;margin:0 0 8px}
.reasontext{font-size:14px;line-height:1.6;color:#dfe3ea}
table.docs{width:100%;border-collapse:collapse;font-size:12.5px}
table.docs th{text-align:left;color:#8a93a6;font-weight:600;padding:5px 8px;border-bottom:1px solid #283041}
table.docs td{padding:7px 8px;border-bottom:1px solid #1c2230;vertical-align:top}
.disp{font-size:11px;padding:1px 7px;border-radius:10px;border:1px solid #38415a;white-space:nowrap}
.disp-process{background:#13361f;border-color:#2c7a4d;color:#7fe0a3}
.disp-duplicate_or_superseded{background:#2a2540;border-color:#5a4b8a;color:#c8b3ff}
.disp-raw_only{background:#23262e;color:#9aa3b5}
.tallyrow{display:flex;gap:8px;flex-wrap:wrap}
.tcell{background:#141821;border:1px solid #283041;border-radius:8px;padding:8px 12px;min-width:120px}
.tcell .n{font-size:20px;font-weight:700} .tcell .l{font-size:11px;color:#8a93a6}
.keypg{display:inline-flex;align-items:center;gap:6px;background:#171a21;border:1px solid #283041;border-radius:8px;padding:6px 10px;margin:4px 6px 0 0;cursor:pointer;font-size:12.5px}
.keypg:hover{border-color:#3b6fe0}
.kv{display:flex;gap:8px;flex-wrap:wrap}.kv .c{background:#171a21;border:1px solid #283041;border-radius:8px;padding:6px 10px;font-size:12px}
.kv .c b{color:#cfd6e2}
.muted{color:#8a93a6}
</style></head><body>
<script>if(window.innerWidth<760&&location.search.indexOf('desktop')<0)location.replace('/m');</script>
<div id=bar>
  <b>V1 review · v4.0</b>
  <select id=proj onchange="openP(this.value)"></select>
  <div class=seg><button id=mOver onclick="setMode('overview')">Overview</button><button id=mPages onclick="setMode('pages')">Pages</button></div>
  <span id=tally></span>
</div>
<div id=wrap>
  <div id=grid></div>
  <div id=center>
    <div id=zoombar>
      <button onclick="setZoom('fit')" id=zfit class=on>Fit</button>
      <button onclick="setZoom(1)">100%</button>
      <button onclick="zStep(1/1.25)">&minus;</button>
      <button onclick="zStep(1.25)">+</button>
    </div>
    <div id=imgwrap><img id=pg src="" alt="pick a project" onclick="toggleZoom()"></div>
  </div>
  <div id=over></div>
  <div id=panel></div>
</div>
<script>
const TAGS=['finish_material','room_layout','quantity_takeoff','project_context'];
const TAGCOL={finish_material:'#ffcf5c',room_layout:'#6db3ff',quantity_takeoff:'#5fd0a0',project_context:'#c08bff'};
const TAGSHORT={finish_material:'finish',room_layout:'rooms',quantity_takeoff:'qty',project_context:'context'};
const ROLES=['title_or_project_info','finish_schedule','finish_legend','finish_floor_plan','architectural_floor_plan','demo_plan','enlarged_flooring_plan','flooring_detail','spec_section','architectural_other','ceiling_rcp','mep','structural','civil_site','paperwork','not_relevant'];
const IMP=['primary','supporting','incidental'];
const MR=['likely_measurable','maybe_measurable','unlikely','unknown'];
const TIE=['quantity_takeoff','finish_material','room_layout','project_context'];
function derive(p){let ti=p.tag_importance||{},uf=p.useful_for||[];
 p.primary_uses=TIE.filter(t=>uf.includes(t)&&ti[t]=='primary');
 p.display_primary_use=p.primary_uses[0]||TIE.find(t=>uf.includes(t))||null;
 let ord={primary:0,supporting:1,incidental:2},best='incidental';
 uf.forEach(t=>{if(ord[ti[t]||'incidental']<ord[best])best=ti[t]||'incidental';});
 p.overall_importance=uf.length?best:'incidental';}
let L=null,i=0,permit=null,saveT=null,mode='overview',zoom='fit';

async function init(){let ps=await (await fetch('/api/projects')).json();
 document.getElementById('proj').innerHTML=ps.map(p=>`<option value="${p.permit}">${p.reviewed?'✓ ':''}${p.permit} · ${p.category||''} (${p.pages}pp)</option>`).join('');
 if(ps.length) openP(ps[0].permit);}
async function openP(p){permit=p;L=await (await fetch('/api/labels/'+p)).json();i=0;grid();setMode('overview');}
function pg(){return (L.pages||[])[i];}
function impColor(p){let t=p.tag_importance||{};if((p.useful_for||[]).length==0)return '#5b6478';
 let best=p.display_primary_use||(p.useful_for||[])[0];return TAGCOL[best]||'#5b6478';}

function setMode(m){mode=m;
 document.getElementById('mOver').classList.toggle('on',m=='overview');
 document.getElementById('mPages').classList.toggle('on',m=='pages');
 let pages=m=='pages';
 document.getElementById('grid').style.display=pages?'flex':'none';
 document.getElementById('center').style.display=pages?'block':'none';
 document.getElementById('panel').style.display=pages?'block':'none';
 document.getElementById('over').style.display=pages?'none':'block';
 if(pages){render();grid();} else overview();
 updTally();}
function updTally(){let r=(L.pages||[]).filter(p=>p.reviewed).length;
 document.getElementById('tally').textContent=`reviewed ${r}/${(L.pages||[]).length}`;}

/* ---------- OVERVIEW ---------- */
function tagCount(t){return (L.pages||[]).filter(p=>(p.useful_for||[]).includes(t)).length;}
function overview(){let pr=L.project||{},docs=L.documents||[];
 let prof=pr.project_profile||{},sf=pr.sf_readiness||{};
 let need=(L.pages||[]).filter(p=>p.needs_review).length;
 let drop=(L.pages||[]).filter(p=>(p.useful_for||[]).length==0).length;
 let flag=pr.needs_review?`<span class="badge flag">⚑ needs review</span>`:'';
 let sfbadge=`<span class="badge b-sf">SF: ${sf.best_method||'?'}${sf.needs_human_ruler?' · needs ruler':''}</span>`;
 let docrows=docs.map(d=>`<tr>
   <td><b>${d.doc_id||''}</b></td><td>${d.filename||''}</td>
   <td><span class="disp disp-${(d.disposition||'raw_only')}">${d.disposition||''}</span><div class=muted style="margin-top:3px">${d.document_category||''}</div></td>
   <td class=muted>${d.reason_text||''}</td></tr>`).join('');
 let tcells=TAGS.map(t=>{let n=tagCount(t);return `<div class=tcell><div class=n style="color:${TAGCOL[t]}">${n}</div><div class=l>${t}</div></div>`;}).join('')
   +`<div class=tcell><div class=n style="color:#5b6478">${drop}</div><div class=l>dropped (useful_for: [])</div></div>`;
 let keyps=(L.pages||[]).map((p,k)=>({p,k})).filter(x=>x.p.overall_importance=='primary')
   .map(x=>`<span class=keypg onclick="go(${x.k})"><span class=tdot style="width:9px;height:9px;background:${impColor(x.p)}"></span><b>${x.p.sheet_number||('p'+x.p.pdf_page_number)}</b> ${(x.p.sheet_title||'').slice(0,42)}</span>`).join('');
 let mix=prof.representation_mix||{};
 document.getElementById('over').innerHTML=`
  <div class=ovh><h1>${L.permit}</h1><span class="badge b-sf">${L.category||''}</span>${sfbadge}${flag}
    <span class=muted>${prof.project_type||''} · ${docs.length} docs · ${(L.pages||[]).length} pages · ${need} flagged</span></div>
  <div class=card><h2>SF readiness (provisional, derived)</h2>
    <div class=kv><div class=c><b>best method:</b> ${sf.best_method||'?'}</div>
      <div class=c><b>needs human ruler:</b> ${sf.needs_human_ruler?'yes':'no'}</div>
      <div class=c><b>status:</b> ${sf.status||''}</div></div>
    <div class=reasontext style="margin-top:8px">${sf.note||'<span class=muted>(no note)</span>'}</div></div>
  <div class=card><h2>Project profile (derived)</h2>
    <div class=kv>
      <div class=c><b>finish_material pages:</b> ${prof.has_finish_material_pages?'✓':'—'}</div>
      <div class=c><b>room_layout:</b> ${prof.has_room_layout_pages?'✓':'—'}</div>
      <div class=c><b>quantity_takeoff:</b> ${prof.has_quantity_takeoff_pages?'✓':'—'}</div>
      <div class=c><b>project_context:</b> ${prof.has_project_context_pages?'✓':'—'}</div>
      <div class=c><b>finish schedule:</b> ${prof.finish_schedule_location||'?'}</div>
      <div class=c><b>spec:</b> ${prof.spec_location||'?'}</div>
      <div class=c><b>representation:</b> digital ${mix.digital_text_vector||0} · vectorized ${mix.vectorized_text||0} · scanned ${mix.scanned||0}</div>
    </div></div>
  <div class=card><h2>useful_for tally</h2><div class=tallyrow>${tcells}</div></div>
  ${keyps?`<div class=card><h2>Primary pages (click to open)</h2>${keyps}</div>`:''}
  <div class=card><h2>Documents</h2>
    <table class=docs><tr><th>doc id</th><th>filename</th><th>disposition</th><th>why</th></tr>${docrows}</table></div>`;}

/* ---------- PAGES ---------- */
function grid(){let g=document.getElementById('grid');
 g.innerHTML=(L.pages||[]).map((p,k)=>{
   let dots=(p.useful_for||[]).map(t=>`<span class=tdot style="background:${TAGCOL[t]}"></span>`).join('')||'<span class=tdot style="background:#5b6478"></span>';
   return `<div class="th ${k==i?'sel':''}" onclick="go(${k})">
   <img src="/thumb/${permit}/${p.image}" loading=lazy style="border-left-color:${impColor(p)}">
   <div><div class=nm>${p.sheet_number||('p'+p.pdf_page_number)} ${p.reviewed?'<span class=dot style="background:#3fb86a"></span>':''}${p.needs_review?'<span class=dot style="background:#ff5d5d"></span>':''}</div>
   <small>${p.display_primary_use||'—'}</small><div class=tagdots>${dots}</div></div></div>`;}).join('');
 updTally();}
function go(k){i=k;if(mode!='pages')setMode('pages');render();grid();}
function opts(arr,v){return arr.map(x=>`<option ${x==v?'selected':''}>${x}</option>`).join('');}
function yn(v){let c=v=='yes'?'yes':(v=='no'?'no':'');return `<span class="${c}">${v==null?'—':v}</span>`;}
function obsRows(o){if(!o)return '';
 let gen=['room_labels_present','room_numbers_present','finish_callouts_present','table_or_schedule_present','schedule_type','drawing_index_present','area_summary_present','flooring_scope_mentioned','vendor_or_product_names_present'];
 let g=gen.filter(k=>o[k]!=null).map(k=>`<tr><td class=k>${k}</td><td>${yn(o[k])}</td></tr>`).join('');
 let sf=o.sf||{};let sfk=['sf_method','sf_confidence','written_scale_present','scale_value','scale_bar_present','dimension_strings_present','room_schedule_with_areas','stated_area','match_lines_present','multi_area_or_split_plan','vector_geometry','flooring_subset_note'];
 let s=sfk.filter(k=>sf[k]!=null).map(k=>{let v=sf[k];if(typeof v=='object')v=JSON.stringify(v);return `<tr><td class=k>${k}</td><td>${yn(v)}</td></tr>`;}).join('');
 return `<div class=obs>${g?`<h4>observations</h4><table>${g}</table>`:''}${s?`<h4>observations.sf</h4><table>${s}</table>`:''}</div>`;}
function render(){let p=pg();if(!p)return;
 let img=document.getElementById('pg');img.onload=applyZoom;img.src='/img/'+permit+'/'+p.image;
 document.getElementById('center').scrollTop=0;
 let uf=p.useful_for||[],ti=p.tag_importance||{};
 let ufchips=TAGS.map(t=>`<span class="chip ${uf.includes(t)?'on':''}" onclick="togTag('${t}')" style="${uf.includes(t)?'background:'+TAGCOL[t]+';border-color:'+TAGCOL[t]+';color:#10131a':''}">${TAGSHORT[t]}</span>`).join('');
 let improws=uf.map(t=>`<div class=timp><span class=tagchip style="border-color:${TAGCOL[t]};color:${TAGCOL[t]}">${TAGSHORT[t]}</span>
   <span class=nm>${t}</span><select onchange="setImp('${t}',this.value)">${opts(IMP,ti[t]||'supporting')}</select></div>`).join('')||'<span class=muted>dropped — useful_for: []</span>';
 let mr=uf.includes('quantity_takeoff')?`<div class=fld><label>measurement_readiness</label><select onchange="setf('measurement_readiness',this.value)">${opts(MR,p.measurement_readiness)}</select></div>`:'';
 let cs=uf.includes('project_context')?`<div class=fld><label>context_signals</label><div class=chips>${(p.context_signals||[]).map(c=>`<span class="chip ro on">${c}</span>`).join('')||'<span class=muted>none</span>'}</div></div>`:'';
 document.getElementById('panel').innerHTML=`
  <small>page ${i+1}/${L.pages.length} · ${p.sheet_number||''} · pdf p${p.pdf_page_number}</small>
  <h3>${p.sheet_title||''}</h3>
  <div class=fld><label>page_role</label><select onchange="setf('page_role',this.value)">${opts(ROLES,p.page_role)}</select></div>
  <div class=fld><label>useful_for (click to toggle)</label><div class=chips>${ufchips}</div></div>
  <div class=fld><label>primary_uses (derived from importance)</label>
    <div class=chips>${(p.primary_uses||[]).map(t=>`<span class="chip on" style="background:${TAGCOL[t]};border-color:${TAGCOL[t]};color:#10131a">${TAGSHORT[t]}</span>`).join('')||'<span class=muted>none primary</span>'}</div>
    <span class=muted style="font-size:11px">display: ${p.display_primary_use||'—'} · overall: ${p.overall_importance||'—'}</span></div>
  <div class=fld><label>tag_importance</label>${improws}</div>
  ${mr}${cs}
  ${obsRows(p.observations)}
  <div class=ev><b>evidence:</b> ${p.evidence_text||''}</div>
  ${p.reviewer_note?`<div class=ev style="border-left:3px solid #ffd86b">⚑ <b>note:</b> ${p.reviewer_note}</div>`:''}
  <div class=fld><label>your note</label><input id=note value="${(p.human_note||'').replace(/"/g,'&quot;')}" oninput="setf('human_note',this.value)"></div>
  <div style="margin-top:12px"><button class=ag onclick="agree()">✓ Agree (a)</button>
   <button onclick="go(Math.min(i+1,L.pages.length-1))">next →</button></div>`;}

/* ---------- ZOOM ---------- */
function setZoom(z){zoom=z;document.getElementById('zfit').classList.toggle('on',z=='fit');applyZoom();}
function zStep(f){let img=document.getElementById('pg');
 let cur=(zoom=='fit')?(img.clientWidth/(img.naturalWidth||1)):zoom;
 zoom=Math.max(0.1,Math.min(5,cur*f));document.getElementById('zfit').classList.remove('on');applyZoom();}
function toggleZoom(){if(zoom=='fit'){setZoom(1);}else{setZoom('fit');}}
function applyZoom(){let img=document.getElementById('pg');if(!img.naturalWidth)return;
 if(zoom=='fit'){img.style.maxWidth='100%';img.style.width='auto';img.style.cursor='zoom-in';}
 else{img.style.maxWidth='none';img.style.width=(img.naturalWidth*zoom)+'px';img.style.cursor='zoom-out';}}

function touch(p){p.label_source='human_reviewed';p.reviewed=true;}
function setf(f,v){let p=pg();p[f]=v;touch(p);render();grid();save();}
function setImp(t,v){let p=pg();p.tag_importance=p.tag_importance||{};p.tag_importance[t]=v;
 derive(p);touch(p);render();grid();save();}
function togTag(t){let p=pg();p.useful_for=p.useful_for||[];let k=p.useful_for.indexOf(t);
 p.tag_importance=p.tag_importance||{};
 if(k<0){p.useful_for.push(t);p.tag_importance[t]='supporting';}else{p.useful_for.splice(k,1);delete p.tag_importance[t];}
 derive(p);touch(p);render();grid();save();}
function agree(){let p=pg();touch(p);grid();save();go(Math.min(i+1,L.pages.length-1));}
function save(){clearTimeout(saveT);saveT=setTimeout(async()=>{
 await fetch('/api/save/'+permit,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(L)});},400);}
document.onkeydown=e=>{if(!L||mode!='pages')return;if(e.target.tagName=='INPUT'||e.target.tagName=='SELECT')return;
 if(e.key=='ArrowRight')go(Math.min(i+1,L.pages.length-1));if(e.key=='ArrowLeft')go(Math.max(i-1,0));if(e.key=='a')agree();
 if(e.key=='+'||e.key=='=')zStep(1.25);if(e.key=='-')zStep(1/1.25);if(e.key=='0')setZoom('fit');};
init();
</script></body></html>"""


MOBILE_HTML = r"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=5,user-scalable=yes">
<title>V1 review · mobile</title>
<style>
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui;background:#0f1115;color:#e7e9ee;-webkit-text-size-adjust:100%}
#top{position:sticky;top:0;z-index:10;background:#171a21;border-bottom:1px solid #283041;padding:8px 10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
select{flex:1;min-width:150px;background:#1d2230;color:#e7e9ee;border:1px solid #38415a;border-radius:8px;padding:10px;font:inherit}
.seg{display:flex}.seg button{flex:1}
button{background:#252b3b;color:#e7e9ee;border:1px solid #38415a;border-radius:8px;padding:10px 12px;font:inherit;cursor:pointer}
.seg button.on{background:#2b5cc4;border-color:#3b6fe0;color:#fff}
#main{padding:10px;max-width:680px;margin:0 auto}
.card{background:#141821;border:1px solid #283041;border-radius:12px;padding:12px;margin:0 0 12px}
.hd{display:flex;align-items:center;gap:8px}
.sn{font-size:19px;font-weight:700}
.muted{color:#8a93a6;font-size:13px}
.badge{font-size:11px;font-weight:600;padding:3px 9px;border-radius:11px;border:1px solid;margin-left:auto;white-space:nowrap}
.fd{width:11px;height:11px;border-radius:50%;display:inline-block}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.chip{font-size:12px;border-radius:12px;padding:3px 10px;border:1px solid}
.thumb{width:100%;height:210px;object-fit:contain;background:#000;border-radius:8px;margin:8px 0;display:block}
.tap{text-align:center;color:#8fb6ff;font-size:12px;margin-top:-4px}
.ev{font-size:13.5px;color:#cfd6e2;background:#171a21;border-radius:8px;padding:10px;margin:6px 0}
.obs{font-size:12.5px;color:#aab2c5;margin:5px 0}
.obs b{color:#cfd6e2}
.acts{display:flex;gap:8px;margin-top:10px}.acts button{flex:1}
.ag{background:#1c5234;border-color:#2c7a4d}.fl{background:#5a2d2d;border-color:#7a3c3f}
.note{width:100%;margin-top:8px;background:#1d2230;color:#e7e9ee;border:1px solid #38415a;border-radius:8px;padding:10px;font:inherit}
#viewer{position:fixed;inset:0;background:#000;z-index:50;display:none;flex-direction:column}
#vtop{display:flex;gap:8px;align-items:center;padding:8px;background:#0c0e12}
#vtop .t{flex:1;font-size:13px;color:#cfd6e2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#vimgwrap{flex:1;overflow:auto;-webkit-overflow-scrolling:touch}
#vimg{display:block}
a.raw{color:#8fb6ff;font-size:13px;text-decoration:none;padding:6px}
</style></head><body>
<div id=top>
 <select id=proj onchange="openP(this.value)"></select>
 <div class=seg><button id=mOver class=on onclick="setMode('over')">Overview</button><button id=mPg onclick="setMode('pg')">Pages</button></div>
</div>
<div id=main>loading…</div>
<div id=viewer>
 <div id=vtop><button onclick="closeV()">✕</button><span class=t id=vt></span>
  <button onclick="vz(1/1.4)">−</button><button onclick="vz(1.4)">+</button>
  <a class=raw id=vraw target=_blank rel=noopener>open ↗</a></div>
 <div id=vimgwrap><img id=vimg></div>
</div>
<script>
const TAGCOL={finish_material:'#ffcf5c',room_layout:'#6db3ff',quantity_takeoff:'#5fd0a0',project_context:'#c08bff'};
const SHORT={finish_material:'finish',room_layout:'rooms',quantity_takeoff:'measure',project_context:'context'};
let L=null,permit=null,mode='over',saveT=null,vw=1;
function esc(s){return (s||'').replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));}
async function init(){let ps=await (await fetch('/api/projects')).json();
 document.getElementById('proj').innerHTML=ps.map(p=>`<option value="${p.permit}">${p.reviewed?'✓ ':''}${p.permit} (${p.pages}pp)</option>`).join('');
 if(ps.length)openP(ps[0].permit);else document.getElementById('main').textContent='no projects';}
async function openP(p){permit=p;L=await(await fetch('/api/labels/'+p)).json();render();}
function setMode(m){mode=m;document.getElementById('mOver').classList.toggle('on',m=='over');document.getElementById('mPg').classList.toggle('on',m=='pg');render();}
function render(){let m=document.getElementById('main');window.scrollTo(0,0);
 m.innerHTML=(mode=='over')?overHTML():(L.pages||[]).map((p,k)=>card(p,k)).join('');}
function overHTML(){let pr=L.project||{},prof=pr.project_profile||{},sf=pr.sf_readiness||{};
 let keeps=(L.pages||[]).filter(p=>(p.useful_for||[]).length).length,drop=(L.pages||[]).length-keeps;
 let need=(L.pages||[]).filter(p=>p.needs_review).length;
 return `<div class=card><div class=sn>${L.permit}</div>
  <div class=muted>${esc(L.category||'')} · ${esc(prof.project_type||'')} · ${(L.pages||[]).length} pages</div>
  <div class=chips><span class=chip style="border-color:#2c5a9a;color:#8fb6ff">SF: ${sf.best_method||'?'}${sf.needs_human_ruler?' · needs ruler':''}</span>
   <span class=chip style="border-color:#2c7a4d;color:#7fe0a3">${keeps} keep</span>
   <span class=chip style="border-color:#3a4254;color:#8a93a6">${drop} drop</span>
   ${need?`<span class=chip style="border-color:#7a6e2c;color:#ffd86b">${need} flagged</span>`:''}</div>
  <div class=obs>${esc(sf.note||'')}</div></div>
  <div class=card><b>useful_for tally</b><div class=chips>${['finish_material','room_layout','quantity_takeoff','project_context'].map(t=>`<span class=chip style="border-color:${TAGCOL[t]};color:${TAGCOL[t]}">${SHORT[t]} ${(L.pages||[]).filter(p=>(p.useful_for||[]).includes(t)).length}</span>`).join('')}</div>
   <div class=muted style="margin-top:6px">Tap “Pages” to review each sheet.</div></div>`;}
function card(p,k){let uf=p.useful_for||[],ti=p.tag_importance||{},o=p.observations||{},sf=o.sf||{};
 let chips=uf.length?uf.map(t=>`<span class=chip style="border-color:${TAGCOL[t]};color:${TAGCOL[t]}">${SHORT[t]} · ${ti[t]||''}</span>`).join(''):`<span class=chip style="border-color:#3a4254;color:#8a93a6">dropped (useful_for: [])</span>`;
 let sb=[];if(sf.sf_method)sb.push(`<b>SF:</b> ${sf.sf_method}`);if(sf.scale_value)sb.push('scale '+esc(sf.scale_value));
 if(sf.room_schedule_with_areas=='yes')sb.push('areas in schedule');if(o.schedule_type)sb.push('schedule: '+o.schedule_type);
 let fl=p.needs_review?'<span class=fd style="background:#ff5d5d"></span>':'';let rv=p.reviewed?'<span class=fd style="background:#3fb86a"></span>':'';
 return `<div class=card id=c${k}>
  <div class=hd><span class=sn>${esc(p.sheet_number||('p'+p.pdf_page_number))}</span> ${fl}${rv}
   <span class=badge style="border-color:#3b6fe0;color:#9fc0ff">${p.display_primary_use||'—'}</span></div>
  <div class=muted>${esc(p.sheet_title||'')}</div>
  <div class=chips>${chips}</div>
  <img class=thumb src="/thumb/${permit}/${p.image}" loading=lazy onclick="openV(${k})">
  <div class=tap onclick="openV(${k})">tap sheet to zoom ⤢</div>
  <div class=ev>${esc(p.evidence_text||'')}</div>
  ${sb.length?`<div class=obs>${sb.join(' · ')}</div>`:''}
  ${p.reviewer_note?`<div class=obs style="color:#ffd86b">⚑ ${esc(p.reviewer_note)}</div>`:''}
  <div class=acts><button class=ag onclick="agree(${k})">✓ Agree</button><button class=fl onclick="flagp(${k})">⚑ Flag</button></div>
  <input class=note placeholder="note…" value="${(p.human_note||'').replace(/"/g,'&quot;')}" oninput="setNote(${k},this.value)"></div>`;}
function refresh(k){let el=document.getElementById('c'+k);if(el)el.outerHTML=card(L.pages[k],k);}
function openV(k){let p=L.pages[k];document.getElementById('vt').textContent=(p.sheet_number||'')+' '+(p.sheet_title||'');
 let im=document.getElementById('vimg');vw=1;im.style.width='100%';im.style.maxWidth='none';im.src='/img/'+permit+'/'+p.image;
 document.getElementById('vraw').href='/img/'+permit+'/'+p.image;document.getElementById('vimgwrap').scrollTop=0;
 document.getElementById('viewer').style.display='flex';}
function closeV(){document.getElementById('viewer').style.display='none';}
function vz(f){let im=document.getElementById('vimg');vw=Math.max(1,Math.min(8,vw*f));im.style.width=(vw*100)+'%';}
function touch(p){p.label_source='human_reviewed';p.reviewed=true;}
function agree(k){let p=L.pages[k];touch(p);p.needs_review=false;refresh(k);save();}
function flagp(k){let p=L.pages[k];p.needs_review=true;touch(p);refresh(k);save();}
function setNote(k,v){L.pages[k].human_note=v;touch(L.pages[k]);save();}
function save(){clearTimeout(saveT);saveT=setTimeout(()=>fetch('/api/save/'+permit,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(L)}),500);}
init();
</script></body></html>"""


@app.get("/m", response_class=HTMLResponse)
def mobile():
    return MOBILE_HTML


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


if __name__ == "__main__":
    os.makedirs(LABELS, exist_ok=True)
    os.makedirs(PAGES, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
