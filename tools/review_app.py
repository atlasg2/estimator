#!/usr/bin/env python3
"""Local review UI for V1 labels — see each plan page + Claude's v3 call, Agree/Fix, save.

No DB needed: reads the raw Claude labels + pre-rendered page images from disk, writes your
corrected labels back to disk (label_source=human_reviewed). Sync to RDS separately.

  pip install fastapi uvicorn
  python tools/review_app.py            # http://localhost:8000  (open the forwarded port)

Files:
  data/v1_labels/lb_<permit>.json         raw Claude labels (label_source=claude, reviewed=false)
  data/v1_labels/reviewed_<permit>.json   your corrections   (label_source=human_reviewed, reviewed=true)
  data/v1_pages/<permit>/<image>          pre-rendered page PNGs (page.image references these)
"""
import json, os, glob
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(ROOT, "data", "v1_labels")
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
                    "decision": lb.get("project", {}).get("decision"),
                    "type": lb.get("project", {}).get("category", ""),
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


@app.post("/api/save/{permit}")
async def save(permit, request: Request):
    data = await request.json()
    os.makedirs(LABELS, exist_ok=True)
    json.dump(data, open(os.path.join(LABELS, f"reviewed_{permit}.json"), "w"), indent=1)
    return {"ok": True}


INDEX_HTML = """<!doctype html><html><head><meta charset=utf-8><title>V1 label review</title>
<style>
 body{margin:0;font:14px system-ui;background:#111;color:#eee}
 #wrap{display:flex;height:100vh}
 #side{width:230px;background:#181818;overflow:auto;border-right:1px solid #333;padding:8px}
 #side div{padding:6px;cursor:pointer;border-radius:4px}#side div:hover{background:#222}
 #main{flex:1;display:flex}
 #imgwrap{flex:1;overflow:auto;background:#000;display:flex;align-items:center;justify-content:center}
 #imgwrap img{max-width:100%;max-height:100vh}
 #panel{width:340px;background:#181818;border-left:1px solid #333;padding:14px;overflow:auto}
 .k{color:#8ab4f8}.crit{color:#ff6b6b;font-weight:700}.use{color:#ffd166}.not{color:#888}
 button{background:#2a2a2a;color:#eee;border:1px solid #444;border-radius:5px;padding:7px 12px;cursor:pointer;margin:3px 0}
 button.ag{background:#1b4d2b}button.fx{background:#5a2d2d}
 select,input{width:100%;background:#222;color:#eee;border:1px solid #444;border-radius:4px;padding:5px;margin:3px 0}
 .ev{color:#aaa;font-size:12px;margin:6px 0}.tag{display:inline-block;background:#222;border:1px solid #444;border-radius:10px;padding:1px 7px;margin:1px;font-size:11px}
 #tally{color:#9f9;font-size:12px}
</style></head><body><div id=wrap>
<div id=side><b>Projects</b><div id=plist></div></div>
<div id=main>
 <div id=imgwrap><img id=pg src="" alt="select a project"></div>
 <div id=panel><div id=meta></div></div>
</div></div>
<script>
const USE=['critical_flooring','useful_flooring','maybe_flooring','not_flooring','unknown_review_needed'];
const ROLE=['finish_floor_plan','finish_schedule','finish_legend','project_manual_or_spec','flooring_detail','enlarged_flooring_plan','architectural_floor_plan','title_or_project_info','general_notes','architectural_other','not_relevant','unknown'];
let L=null,i=0,permit=null,agreed=0,fixed=0;
async function init(){let ps=await (await fetch('/api/projects')).json();
 document.getElementById('plist').innerHTML=ps.map(p=>`<div onclick="open_('${p.permit}')">${p.reviewed?'✓ ':''}${p.permit}<br><small>${p.decision||''} · ${p.pages}pp</small></div>`).join('');}
async function open_(p){permit=p;L=await (await fetch('/api/labels/'+p)).json();i=0;agreed=0;fixed=0;render();}
function pg(){return (L.pages||[])[i];}
function render(){let p=pg();if(!p){document.getElementById('meta').innerHTML='<b>'+permit+'</b><br>Project: '+(L.project.decision)+'<br>'+(L.project.reason_text||'')+'<br><br>No process pages.';document.getElementById('pg').src='';return;}
 document.getElementById('pg').src=p.image?('/img/'+permit+'/'+p.image):'';
 let u=p.page_usefulness,c=u&&u.startsWith('critical')?'crit':u&&u.startsWith('useful')?'use':'not';
 let rc=(p.reason_codes||[]).map(x=>'<span class=tag>'+x+'</span>').join(' ');
 document.getElementById('meta').innerHTML=`
  <b>${permit}</b> &nbsp; <span id=tally>✓${agreed} ✗${fixed}</span><br>
  <small>page ${i+1}/${L.pages.length} · sheet ${p.sheet_number||'?'} · pdf p${p.pdf_page_number}</small>
  <h3>${p.sheet_title||''}</h3>
  <div>usefulness: <span class=${c}>${u}</span></div>
  <div>role: <span class=k>${p.page_role}</span></div>
  <div>flooring_relevant: ${p.flooring_relevant} · conf: ${p.confidence}</div>
  <div>${rc}</div>
  <div class=ev>why: ${p.evidence_text||''}</div>
  ${p.needs_review?'<div style="color:#ff6b6b">⚑ needs_review</div>':''}
  <hr>
  <button class=ag onclick="agree()">✓ Agree (a)</button>
  <button class=fx onclick="fix()">✗ Fix (f)</button>
  <div id=fixbox></div>
  <hr><button onclick="prev()">← prev</button> <button onclick="next()">next →</button>
  <button onclick="save()" style="float:right">Save</button>`;}
function agree(){let p=pg();p.label_source='human_reviewed';p.reviewed=true;agreed++;next();}
function fix(){let p=pg();
 document.getElementById('fixbox').innerHTML=`
  usefulness <select id=fu>${USE.map(x=>`<option ${x==p.page_usefulness?'selected':''}>${x}</option>`).join('')}</select>
  role <select id=fr>${ROLE.map(x=>`<option ${x==p.page_role?'selected':''}>${x}</option>`).join('')}</select>
  <input id=fn placeholder="note (why you changed it)">
  <button class=ag onclick="applyfix()">apply</button>`;}
function applyfix(){let p=pg();p.page_usefulness=document.getElementById('fu').value;p.page_role=document.getElementById('fr').value;
 p.human_note=document.getElementById('fn').value;p.label_source='human_reviewed';p.reviewed=true;fixed++;next();}
function next(){if(i<L.pages.length-1){i++;render();}else save();}
function prev(){if(i>0){i--;render();}}
async function save(){await fetch('/api/save/'+permit,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(L)});
 document.getElementById('tally').innerHTML='saved ✓ '+agreed+' fixed '+fixed;}
document.onkeydown=e=>{if(!L)return;if(e.key=='ArrowRight')next();if(e.key=='ArrowLeft')prev();if(e.key=='a')agree();if(e.key=='f')fix();};
init();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return INDEX_HTML


if __name__ == "__main__":
    os.makedirs(LABELS, exist_ok=True)
    os.makedirs(PAGES, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
