#!/usr/bin/env python3
"""V1 deterministic verifier: cross-check the labeler's output against the evidence and
flag contradictions for review. Cheap, runs on every project before/with the adversarial
agent. Biased to catch dangerous FALSE NEGATIVES on flooring pages.

  python scripts/verify_classification.py --evidence evidence.json --labels labels.json --out flags.json
"""
import argparse, json, re

FLOOR_TERMS = re.compile(r'\b(finish schedule|finish legend|floor plan|flooring|room finish|'
                         r'\bvct\b|\blvt\b|carpet|resilient|ceramic|porcelain|quarry tile|'
                         r'rubber floor|sheet vinyl|base schedule|finish plan)\b', re.I)
ARCH_NAME = re.compile(r'\b(arch|architectural|finish|floor plan|interior|spec|project manual|'
                       r'a-?\d{2,3}|cd drawings|permit drawings)\b', re.I)
DANGER_ROLES = {"finish_floor_plan", "finish_schedule_or_legend",
                "project_manual_or_spec", "flooring_detail"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ev = json.load(open(args.evidence))
    lb = json.load(open(args.labels))
    # index evidence: (docId,page) -> page evidence ; docId -> doc
    pe = {}
    de = {}
    for d in ev["documents"]:
        de[d["docId"]] = d
        for p in d.get("pages", []):
            pe[(d["docId"], p["page"])] = p
    disp = {d["docId"]: d.get("disposition") for d in lb.get("documents", [])}

    flags = []

    def flag(kind, sev, where, msg):
        flags.append({"kind": kind, "severity": sev, "where": where, "message": msg})

    # project / doc / page unknowns -> review
    if lb.get("project", {}).get("decision") == "unknown_review_needed":
        flag("project_unknown", "review", lb["permit"], "project decision unknown")
    for d in lb.get("documents", []):
        if d.get("disposition") == "unknown_review_needed" or d.get("needs_review"):
            flag("doc_unknown", "review", d.get("docId"), f"doc disposition {d.get('disposition')}")
        # raw_only but the name looks architectural/finish/spec
        if d.get("disposition") == "raw_only":
            name = de.get(d.get("docId"), {}).get("name", "")
            if ARCH_NAME.search(name or ""):
                flag("rawonly_looks_arch", "high", d.get("docId"),
                     f"raw_only but name suggests plans/finish/spec: {name[:60]}")

    for p in lb.get("pages", []):
        key = (p.get("docId"), p.get("page"))
        evp = pe.get(key, {})
        text = evp.get("text", "") or ""
        tl = evp.get("text_len", 0) or 0
        vc = evp.get("vector_count") or 0
        usefulness = p.get("page_usefulness")
        role = p.get("page_role")

        if p.get("needs_review") or usefulness == "unknown_review_needed" or role == "unknown":
            flag("page_unknown", "review", key, "page flagged unknown/needs_review")

        # DANGEROUS: page called not_flooring but its text screams flooring
        if usefulness == "not_flooring" and FLOOR_TERMS.search(text):
            m = FLOOR_TERMS.search(text)
            flag("false_negative_risk", "high", key,
                 f"not_flooring but text contains '{m.group(0)}'")

        # role says flooring but flooring_relevant=false -> contradiction
        if role in DANGER_ROLES and p.get("flooring_relevant") == "false":
            flag("role_relevance_conflict", "high", key,
                 f"role={role} but flooring_relevant=false")

        # possible vectorized text: lots of vectors, almost no text
        if vc and vc > 2000 and tl < 40:
            flag("possible_vectorized_text", "medium", key,
                 f"vectors~{vc} but text_len={tl} — labels may be outlines; verify by image")

        # scanned / no text at all
        if tl == 0 and evp.get("image_object_count"):
            flag("scanned_no_text", "medium", key, "no text layer (scanned) — OCR later")

    out = {"permit": lb.get("permit"), "n_flags": len(flags),
           "n_high": sum(1 for f in flags if f["severity"] == "high"), "flags": flags}
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"{lb.get('permit')}: {out['n_flags']} flags ({out['n_high']} high) -> {args.out}")


if __name__ == "__main__":
    main()
