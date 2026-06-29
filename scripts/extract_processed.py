#!/usr/bin/env python3
"""Background full-extraction driver (runs on EC2, in-region).

Polls the DB for permits that have document_labels.disposition='process' but are not yet
extracted, downloads those process docs, and runs the full extraction (image + text JSON +
vector JSON -> S3 + plan_pages/page_artifacts). Idempotent; loops until drained.

  DATABASE_URL=... S3_BUCKET_NAME=... python scripts/extract_processed.py
"""
import os, re, json, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg
from app.ingest import process_project, slugify

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
DB = os.environ["DATABASE_URL"]


def download(doc_id, dest):
    if os.path.exists(dest) and open(dest, "rb").read(5) == b"%PDF-":
        return True
    try:
        data = urllib.request.urlopen(urllib.request.Request(
            f"https://onestopapp.nola.gov/GetDocument.aspx?DocID={doc_id}",
            headers={"User-Agent": UA}), timeout=180).read()
        open(dest, "wb").write(data)
        return data[:5] == b"%PDF-"
    except Exception:
        return False


def pending():
    with psycopg.connect(DB, connect_timeout=30) as c, c.cursor() as cur:
        cur.execute("""
          SELECT dl.permit_num,
                 json_agg(json_build_object('docId', dl.doc_id, 'name', dl.doc_name))
          FROM document_labels dl
          WHERE dl.disposition = 'process'
            AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.slug = lower(dl.permit_num))
          GROUP BY dl.permit_num
        """)
        return cur.fetchall()


def main():
    empty = 0
    while empty < 40:                      # patient: ~60 min with nothing new before exit
        todo = pending()
        if not todo:
            empty += 1; time.sleep(90); continue
        empty = 0
        for permit, docs in todo:
            proj = f"data/nola/{permit}"
            os.makedirs(proj, exist_ok=True)
            manifest = {"permitNum": permit, "documents": []}
            process_ids = []
            for d in docs:
                did, name = d["docId"], d.get("name") or str(d["docId"])
                fn = f"{did}__{re.sub(r'[^A-Za-z0-9._ -]', '_', name)[:55]}.pdf"
                ok = download(did, os.path.join(proj, fn))
                manifest["documents"].append({"docId": did, "name": name,
                                              "file": fn if ok else None, "isPdf": bool(ok),
                                              "classification": "keep"})
                if ok:
                    process_ids.append(str(did))
            json.dump(manifest, open(os.path.join(proj, "manifest.json"), "w"))
            try:
                rep = process_project(proj, only_docids=process_ids, workers=8)
                print(f"EXTRACTED {permit}: {rep['pages']} pages", flush=True)
            except Exception as e:
                print(f"ERROR {permit}: {str(e)[:80]}", flush=True)
        time.sleep(10)
    print("extraction driver: no more pending, exiting", flush=True)


if __name__ == "__main__":
    main()
