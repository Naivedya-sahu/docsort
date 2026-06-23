#!/usr/bin/env python3
"""
doc_handler — tag academic documents with a local (or frontier) LLM, then move by prefix.

Tag vocabulary lives in TAGS.md (single source) and is injected into the model prompt.
Classification tiers: TEXT -> 5-page ESCALATE -> VISION (+page-3) -> FILENAME.
On a hard 99UNS, an optional FRONTIER model (Claude Code CLI / OpenAI API) gives a verdict.

  python doc_handler.py "D:\\AcademicsCOPY" --vision --vision-model qwen2-vl-7b
  python doc_handler.py "D:\\AcademicsCOPY" --apply --vision --vision-model qwen2-vl-7b
  python doc_handler.py "D:\\AcademicsCOPY" --frontier claude         # Claude Code sub for hard cases
  python doc_handler.py "D:\\AcademicsCOPY" --move "D:\\Archive\\Academics" --apply

Backends: --backend local|openai (main) ; --frontier none|claude|openai (99UNS fallback).
Deps: see requirements.txt.
"""
from __future__ import annotations
import os, sys, json, csv, re, base64, argparse, subprocess, urllib.request
from config import load_config, resolve_api, resolve_location, arg_defaults

HERE=os.path.dirname(os.path.abspath(__file__))
EXT_TEXT={".pdf",".txt",".md",".docx",".pptx",".ppt",".doc"}
MIN_TEXT=80; DEEP_PAGES=5; DEEP_CAP=4000; DPI=120
STREAMS=set(); SUBJECTS=set(); TYPES=set()   # filled from TAGS.md

# ---------- tag loading (single source) ----------
def load_tags(path):
    streams={}; subjects={}; types=[]
    try: txt=open(path,encoding="utf-8").read()
    except Exception: txt=""
    def block(header):
        m=re.search(r"##\s*"+header+r".*?```tags\n(.*?)```",txt,re.S|re.I)
        return m.group(1).strip().splitlines() if m else []
    for ln in block("STREAMS"):
        if ln.strip(): streams[ln.split()[0]]=ln.strip()
    for ln in block("SUBJECTS"):
        if ln.strip(): subjects[ln.split()[0]]=ln.strip()
    m=re.search(r"##\s*TYPES.*?```tags\n(.*?)```",txt,re.S|re.I)
    if m: types=[x.split()[0] for x in m.group(1).splitlines() if x.strip()]
    if not streams: streams={"CW":"CW","GATE":"GATE","PROJ":"PROJ","RES":"RES","REC":"REC","REF":"REF"}
    if not subjects: subjects={"99UNS":"unsure","NA":"na"}
    if not types: types=["misc"]
    return streams,subjects,types

def build_system(template_path, streams, subjects, types):
    try:
        s=open(template_path,encoding="utf-8").read()
        m=re.search(r"<SYSTEM>(.*?)</SYSTEM>",s,re.S); tmpl=m.group(1) if m else s
    except Exception:
        tmpl="Reply: STREAM SUBJECT TYPE CONF.\n{{STREAMS}}\n{{SUBJECTS}}\n{{TYPES}}"
    tmpl=tmpl.replace("{{STREAMS}}","\n".join("  "+v for v in streams.values()))
    tmpl=tmpl.replace("{{SUBJECTS}}","\n".join("  "+v for v in subjects.values()))
    tmpl=tmpl.replace("{{TYPES}}"," ".join(types))
    return tmpl.strip()

# ---------- text / image extraction ----------
def pdf_text(path,pages=2,cap=2000):
    try:
        import fitz; d=fitz.open(path); t=""
        for i in range(min(pages,d.page_count)):
            t+=d[i].get_text()
            if len(t)>cap: break
        d.close(); return t[:cap]
    except Exception: return ""
def doc_text(path,cap=2000):
    e=os.path.splitext(path)[1].lower()
    try:
        if e==".pdf": return pdf_text(path,2,cap)
        if e in (".txt",".md"): return open(path,encoding="utf-8",errors="replace").read()[:cap]
        if e==".docx":
            import docx; return "\n".join(p.text for p in docx.Document(path).paragraphs)[:cap]
        if e==".pptx":
            from pptx import Presentation
            return " ".join(s.text for sl in Presentation(path).slides for s in sl.shapes
                             if getattr(s,'has_text_frame',False))[:cap]
    except Exception: return ""
    return ""
def page_png(path,page=0,dpi=None):
    try:
        import fitz; d=fitz.open(path)
        if d.page_count==0: return None
        if d.page_count<=page: page=0
        b=d[page].get_pixmap(dpi=dpi or DPI).tobytes("png"); d.close(); return b
    except Exception: return None

# ---------- backends ----------
def _http(url,payload,headers):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=headers)
    return json.load(urllib.request.urlopen(req,timeout=180))

def available_models(api):
    try:
        r=json.load(urllib.request.urlopen(api.replace("/chat/completions","/models"),timeout=8))
        return [m.get("id") for m in r.get("data",[])]
    except Exception: return []

def resolve_model(api,want,prefer_vision=False):
    """If 'want' isn't loaded on the server, fall back to a loaded model (vision-preferring).
    Returns (model_id, server_reachable)."""
    av=available_models(api)
    if not av: return want, False
    if want in av: return want, True
    pick=None
    if prefer_vision:
        pick=next((m for m in av if ("vl" in m.lower() or "vision" in m.lower())),None)
    pick=pick or next((m for m in av if "embed" not in m.lower()), av[0])
    return pick, True

def llm(a,backend,system,user_text,image_png=None):
    """Return raw model text. backend: local | openai | claude."""
    if backend in ("local","openai"):
        if image_png:
            content=[{"type":"text","text":user_text},
                     {"type":"image_url","image_url":{"url":"data:image/png;base64,"+base64.b64encode(image_png).decode()}}]
        else:
            content=user_text
        msgs=[{"role":"system","content":system},{"role":"user","content":content}]
        if backend=="local":
            model=a.vision_model if image_png else a.model
            r=_http(a.api,{"model":model,"temperature":0,"max_tokens":16,"messages":msgs},
                    {"Content-Type":"application/json"})
        else:
            key=os.environ.get("OPENAI_API_KEY","")
            model=a.openai_model
            r=_http("https://api.openai.com/v1/chat/completions",
                    {"model":model,"temperature":0,"max_tokens":16,"messages":msgs},
                    {"Content-Type":"application/json","Authorization":"Bearer "+key})
        return r["choices"][0]["message"]["content"]
    if backend=="claude":   # Claude Code CLI — uses the Claude subscription, text only
        prompt=system+"\n\n"+user_text+"\nReply with ONLY the 4 tokens."
        try:
            out=subprocess.run(["claude","-p",prompt],capture_output=True,text=True,timeout=120)
            return out.stdout
        except Exception as e: return "99UNS "+str(e)[:20]
    return ""

def parse(out):
    o=(out or "").upper()
    st=next((s for s in sorted(STREAMS,key=len,reverse=True) if re.search(r'\b'+re.escape(s)+r'\b',o)),"CW")
    su=next((c for c in sorted(SUBJECTS,key=len,reverse=True) if c in o),"99UNS")
    ty=next((t for t in TYPES if t.upper() in o),"misc")
    cf="high" if "HIGH" in o else "low"
    return st,su,ty,cf

def classify(a,sysp,full,fn,rel):
    ispdf=full.lower().endswith(".pdf")
    snip=doc_text(full)
    u=lambda txt:f"Filename: {fn}\nFolder: {rel}\nText:\n{txt[:DEEP_CAP]}\n\nAnswer (STREAM SUBJECT TYPE CONF):"
    if len(snip.strip())>=MIN_TEXT:
        st,su,ty,cf=parse(llm(a,a.backend,sysp,u(snip))); src="text"
        if su=="99UNS" and ispdf:
            deep=pdf_text(full,DEEP_PAGES,DEEP_CAP)
            if len(deep)>len(snip):
                r=parse(llm(a,a.backend,sysp,u(deep)))
                if r[1]!="99UNS": st,su,ty,cf,src=(*r,"text5"); snip=deep
        if su=="99UNS" and a.frontier!="none":
            r=parse(llm(a,a.frontier,sysp,u(snip)))
            if r[1]!="99UNS": return (*r,"frontier:"+a.frontier)
        return st,su,ty,cf,src
    if a.vision and ispdf and (png:=page_png(full,0)):
        un="(handwritten/scanned page) Answer (STREAM SUBJECT TYPE CONF):"
        st,su,ty,cf=parse(llm(a,a.backend,sysp,f"Filename: {fn}\nFolder: {rel}\n"+un,png)); src="vision"
        if su=="99UNS" and (p3:=page_png(full,2)):
            r=parse(llm(a,a.backend,sysp,f"Filename: {fn}\nFolder: {rel}\n(page 3) "+un,p3))
            if r[1]!="99UNS": return (*r,"vision3")
        return st,su,ty,cf,src
    r=parse(llm(a,a.backend,sysp,u("")))
    if r[1]=="99UNS" and a.frontier!="none":
        rf=parse(llm(a,a.frontier,sysp,u("")))
        if rf[1]!="99UNS": return (*rf,"frontier:"+a.frontier)
    return (*r,"filename")

def move_by_prefix(root,dest,apply):
    pat=re.compile(r'^\[([A-Z]+)-([0-9A-Z]+)\]\s+(.*)$'); n=0; rows=[]
    for dp,_,fns in os.walk(root):
        for fn in fns:
            m=pat.match(fn)
            if not m: continue
            newp=os.path.join(dest,m.group(1),m.group(2),m.group(3))
            rows.append((os.path.join(dp,fn),newp)); n+=1
            if apply:
                os.makedirs(os.path.join(dest,m.group(1),m.group(2)),exist_ok=True)
                try: os.rename(os.path.join(dp,fn),newp)
                except Exception as e: print("move-fail:",fn,e)
    log=os.path.join(dest if apply else root,"_move_log.csv")
    try:
        os.makedirs(os.path.dirname(log),exist_ok=True)
        with open(log,"w",encoding="utf-8",newline="") as g: csv.writer(g).writerows([("from","to")]+rows)
    except Exception: pass
    print(f"{'MOVED' if apply else 'DRY-RUN move'}: {n} files -> {dest}")
    return n

def iter_targets(root):
    for dp,_,fns in os.walk(root):
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in EXT_TEXT and not fn.startswith("["):
                yield dp,fn

def setup(a):
    global STREAMS,SUBJECTS,TYPES
    s,su,ty=load_tags(a.tags); STREAMS=set(s); SUBJECTS=set(su); TYPES=set(ty)
    return build_system(a.prompt,s,su,ty)

def add_args(ap):
    ap.add_argument("root",nargs="?",default=None,help="folder to process (or use --location)")
    ap.add_argument("--config",default=None,help="path to config.json (else config.json beside script)")
    ap.add_argument("--host",default=None,help="override model host: a name from config 'hosts' or a raw URL")
    ap.add_argument("--location",default=None,help="named location from config 'locations'")
    ap.add_argument("--api",default=None)
    ap.add_argument("--model",default=None)
    ap.add_argument("--vision",action="store_true",default=None)
    ap.add_argument("--vision-model",default=None)
    ap.add_argument("--backend",default=None,choices=["local","openai"])
    ap.add_argument("--frontier",default=None,choices=["none","claude","openai"])
    ap.add_argument("--openai-model",default=None)
    ap.add_argument("--tags",default=os.path.join(HERE,"TAGS.md"))
    ap.add_argument("--prompt",default=os.path.join(HERE,"system_prompt.md"))
    ap.add_argument("--apply",action="store_true",default=None)
    ap.add_argument("--move",default=None,help="destination root; or @archive to use config archive_root")
    ap.add_argument("--log",default=None)

def main():
    ap=argparse.ArgumentParser(); add_args(ap)
    pre,_=ap.parse_known_args()
    cfg=load_config(pre.config)
    ad,glb=arg_defaults(cfg); ap.set_defaults(**ad)
    a=ap.parse_args()
    global MIN_TEXT,DEEP_PAGES,DEEP_CAP,DPI
    MIN_TEXT,DEEP_PAGES,DEEP_CAP,DPI=glb["MIN_TEXT"],glb["DEEP_PAGES"],glb["DEEP_CAP"],glb["DPI"]
    if a.host: a.api=resolve_api(cfg,a.host)
    if a.backend=="local":                       # adapt to whatever model is loaded
        m,up=resolve_model(a.api,a.model)
        if not up: print(f"[warn] model server unreachable at {a.api}")
        elif m!=a.model: print(f"[model] '{a.model}' not loaded -> '{m}'"); a.model=m
        if a.vision:
            vm,up=resolve_model(a.api,a.vision_model,prefer_vision=True)
            if up and vm!=a.vision_model: print(f"[vision] '{a.vision_model}' not loaded -> '{vm}'"); a.vision_model=vm
    root=resolve_location(cfg,a.location) if a.location else a.root
    if not root: ap.error("give a ROOT path or --location NAME (see config 'locations')")
    a.root=root
    dest=cfg.get("archive_root") if a.move=="@archive" else a.move
    if dest: move_by_prefix(a.root,dest,bool(a.apply)); return
    sysp=setup(a); rows=[]; n=0
    for dp,fn in iter_targets(a.root):
        full=os.path.join(dp,fn); rel=os.path.relpath(dp,a.root)
        st,su,ty,cf,src=classify(a,sysp,full,fn,rel)
        new=f"[{st}-{su}] {fn}"; rows.append((full,fn,new,st,su,ty,cf,src)); n+=1
        print(f"{st:5}{su:7}{ty:10}{cf:5}{src:14}{fn[:46]}")
        if a.apply:
            try: os.rename(full,os.path.join(dp,new))
            except Exception as e: print("  rename-fail:",e)
    logp=a.log or os.path.join(a.root,"_doc_handler_log.csv")
    with open(logp,"w",encoding="utf-8",newline="") as g:
        w=csv.writer(g); w.writerow(["path","old","new","stream","subject","type","conf","source"]); w.writerows(rows)
    print(f"\n{'APPLIED' if a.apply else 'DRY-RUN'}: {n} files. log: {logp}")
    if not a.apply: print("Review log (conf=low, source=filename/vision/frontier), then --apply.")

if __name__=="__main__": main()
