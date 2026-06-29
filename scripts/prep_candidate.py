#!/usr/bin/env python3
"""V1 prep: turn one permit's document list into an EVIDENCE bundle for the labeler.

Deterministic, no LLM. Downloads every document (raw always kept), and for each extracts
cheap per-page text + a vector-path count + sheet-number/title guesses, rendering a low-res
thumbnail ONLY for pages whose text is too thin to classify. Output = one evidence JSON.

  python scripts/prep_candidate.py --in candidate.json --out evidence.json --workdir /tmp/prep

candidate.json: {"permit":"...","metadata":{...},"documents":[{"docId":123,"name":"..."}]}
"""
import argparse, json, os, re, time, urllib.request
import fitz

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
TEXT_CAP = 1800          # chars of page text to include in evidence (enough to classify)
THIN_TEXT = 40           # below this, render a thumbnail so the labeler can look
SHEET_RE = re.compile(r'\b([A-Z]{1,3}-?\d{2,3}(?:\.\d+)?)\b')   # A101, A-101, G000, FS201


def download(doc_id, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 100:
        return open(dest, "rb").read(5) == b"%PDF-"
    url = f"https://onestopapp.nola.gov/GetDocument.aspx?DocID={doc_id}"
    for i in range(3):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120).read()
            open(dest, "wb").write(data)
            return data[:5] == b"%PDF-"
        except Exception:
            if i == 2:
                return None
            time.sleep(3 * (i + 1))


def sheet_guess(text):
    """Best-effort sheet number + title from page text (a HINT, not the decision)."""
    head = " ".join(text.split())[:200]
    m = SHEET_RE.search(head)
    num = m.group(1) if m else None
    # title = the wordy bit near the sheet number, capped
    title = head[:80] if head else None
    return num, title


def prep_doc(doc_id, name, path, thumbdir):
    out = {"docId": doc_id, "name": name, "is_pdf": False, "pages": []}
    try:
        d = fitz.open(path)
    except Exception as e:
        out["error"] = str(e)[:60]; return out
    out["is_pdf"] = True
    out["size_bytes"] = os.path.getsize(path)
    out["page_count"] = d.page_count
    for i in range(d.page_count):
        p = d[i]
        text = p.get_text("text")
        tl = len(text.strip())
        vcount = None
        if tl < 200:        # only count vectors where vectorized-text is a real risk (slow op)
            try:
                vcount = sum(len(path_.get("items", [])) for path_ in p.get_drawings())
            except Exception:
                vcount = None
        num, title = sheet_guess(text)
        page = {"page": i + 1, "text_len": tl, "vector_count": vcount,
                "sheet_number": num, "sheet_title": title,
                "text": text[:TEXT_CAP], "text_truncated": tl > TEXT_CAP}
        if tl < THIN_TEXT:                          # thin/scanned -> give the labeler an image
            try:
                z = 1100.0 / max(p.rect.width, p.rect.height)
                tp = os.path.join(thumbdir, f"{doc_id}_p{i+1:03d}.png")
                p.get_pixmap(matrix=fitz.Matrix(z, z)).save(tp)
                page["thumbnail"] = tp
                page["image_object_count"] = len(p.get_images())
            except Exception:
                pass
        out["pages"].append(page)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="/tmp/prep")
    ap.add_argument("--only-docs", help="comma-separated DocIDs to download+read; others are "
                                         "recorded name-only (skipped by the name-triage, kept raw)")
    args = ap.parse_args()

    cand = json.load(open(args.infile))
    permit = cand["permit"]
    only = set(s.strip() for s in args.only_docs.split(",")) if args.only_docs else None
    rawdir = os.path.join(args.workdir, permit, "raw")
    thumbdir = os.path.join(args.workdir, permit, "thumbs")
    os.makedirs(rawdir, exist_ok=True); os.makedirs(thumbdir, exist_ok=True)

    evidence = {"permit": permit, "metadata": cand.get("metadata", {}), "documents": []}
    for doc in cand["documents"]:
        doc_id, name = doc["docId"], doc["name"]
        if only is not None and str(doc_id) not in only:        # excluded by name-triage
            evidence["documents"].append({"docId": doc_id, "name": name,
                                          "skipped_by_name_triage": True, "is_pdf": None})
            continue
        dest = os.path.join(rawdir, f"{doc_id}.pdf")
        ok = download(doc_id, dest)
        if not ok:
            evidence["documents"].append({"docId": doc_id, "name": name, "is_pdf": False,
                                          "error": "download_failed" if ok is None else "not_pdf"})
            continue
        evidence["documents"].append(prep_doc(doc_id, name, dest, thumbdir))

    json.dump(evidence, open(args.out, "w"), indent=1)
    nd = len(evidence["documents"]); npg = sum(len(d.get("pages", [])) for d in evidence["documents"])
    print(f"{permit}: {nd} docs, {npg} pages -> {args.out}")


if __name__ == "__main__":
    main()
