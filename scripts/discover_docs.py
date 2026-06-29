#!/usr/bin/env python3
"""Discover a permit's document list (filenames + DocIDs) via the NOLA portal.

Direct PrmtView fetch -> gets BOTH the doc list and the DocIDs (WebFetch can't).
Writes results INCREMENTALLY after every permit (never lose partial work).

  python scripts/discover_docs.py --chunk chunk.json --out result.json [--sleep 2]

chunk.json: [{"permit": "...", "ref": "..."}, ...]
"""
import argparse, json, os, re, time, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"


def fetch(ref, tries=3):
    url = f"https://onestopapp.nola.gov/PrmtView.aspx?ref={ref}"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace"), None
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 429:                       # rate-limited: stop, caller decides
                return None, "ratelimit"
            if i == tries - 1:
                return None, str(e)[:40]
            time.sleep(3 * (i + 1))


def parse_docs(html):
    docs = []
    for m in re.finditer(r'<li[^>]*>(.*?)</li>', html, re.S | re.I):
        li = m.group(1)
        dm = re.search(r'DocRedirect\((\d+)\)', li)
        if not dm:
            continue
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', li)).strip()
        fm = re.search(r'(.+?\.pdf)', text, re.I)
        name = fm.group(1).strip() if fm else text[:90]
        docs.append({"docId": int(dm.group(1)), "name": name})
    return docs


def db_writeback(conn, permit, docs):
    """Write the raw doc list into candidates.documents_json + mark discovered."""
    from psycopg.types.json import Jsonb
    with conn.cursor() as cur:
        cur.execute("UPDATE candidates SET documents_json=%s, status='discovered', "
                    "updated_at=now() WHERE permit_num=%s", (Jsonb(docs), permit))
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--db", action="store_true", help="also write to RDS (uses DATABASE_URL)")
    args = ap.parse_args()

    conn = None
    if args.db:
        import psycopg
        conn = psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=20)

    items = json.load(open(args.chunk))
    results = json.load(open(args.out)) if os.path.exists(args.out) else []
    done = {r["ref"] for r in results}

    for it in items:
        if it["ref"] in done:
            continue
        html, err = fetch(it["ref"])
        if err == "ratelimit":
            print(f"RATELIMIT at {it['ref']} — stopping, {len(results)} saved so far")
            break
        if err:
            rec = {**it, "error": err, "docs": []}
        else:
            rec = {**it, "docs": parse_docs(html), "error": None}   # raw truth only
            if conn:
                db_writeback(conn, it["permit"], rec["docs"])
        results.append(rec)
        json.dump(results, open(args.out, "w"), indent=1)           # INCREMENTAL save
        print(f"  {it['permit']:18} {len(rec['docs']):2} docs  "
              f"{'ERR ' + rec['error'] if rec.get('error') else ''}")
        time.sleep(args.sleep)

    if conn:
        conn.close()
    print(f"done: {len(results)}/{len(items)} saved -> {args.out}")


if __name__ == "__main__":
    main()
