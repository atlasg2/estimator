#!/usr/bin/env python3
"""Insert ONE project's label file into RDS (idempotent). Run on EC2 by the store loop.

  python scripts/store_one.py --file lb_25-13446-RNVS.json --run-label v1-gate2
"""
import argparse, json, os, psycopg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--run-label", default="v1-gate2")
    args = ap.parse_args()
    lb = json.load(open(args.file)); permit = lb["permit"]
    conn = psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=30); cur = conn.cursor()

    cur.execute("SELECT id FROM classification_runs WHERE run_label=%s AND stage='v1a-claude' LIMIT 1", (args.run_label,))
    r = cur.fetchone()
    if r:
        run_id = r[0]
    else:
        cur.execute("""INSERT INTO classification_runs (run_label,stage,model,prompt_version,status)
                       VALUES (%s,'v1a-claude','claude-opus-4-8','project-packet-builder-v2','running') RETURNING id""",
                    (args.run_label,))
        run_id = cur.fetchone()[0]
    # idempotent: clear any prior labels for this permit in this run
    for t in ("project_labels", "document_labels", "page_labels"):
        cur.execute(f"DELETE FROM {t} WHERE classification_run_id=%s AND permit_num=%s", (run_id, permit))

    pr = lb["project"]
    cur.execute("""INSERT INTO project_labels (classification_run_id,permit_num,decision,confidence,evidence_text,reason,needs_review,label_source)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'claude')""",
                (run_id, permit, pr["decision"], pr.get("confidence"), pr.get("evidence"), pr.get("reason"), pr.get("needs_review", False)))
    for d in lb.get("documents", []):
        cur.execute("""INSERT INTO document_labels (classification_run_id,permit_num,doc_id,doc_name,disposition,confidence,evidence_text,reason,needs_review,label_source)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'claude')""",
                    (run_id, permit, str(d["docId"]), d.get("name"), d["disposition"], d.get("confidence"), d.get("evidence"), d.get("reason"), d.get("needs_review", False)))
    for p in lb.get("pages", []):
        cur.execute("""INSERT INTO page_labels (classification_run_id,permit_num,doc_id,pdf_page_number,sheet_number,sheet_title,page_usefulness,page_role,flooring_relevant,confidence,evidence_text,needs_review,label_source)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'claude')""",
                    (run_id, permit, str(p["docId"]), p["page"], p.get("sheet_number"), p.get("sheet_title"), p.get("page_usefulness"), p.get("page_role"), p.get("flooring_relevant"), p.get("confidence"), p.get("evidence"), p.get("needs_review", False)))
    conn.commit()
    print(f"{permit}: stored {len(lb.get('documents',[]))} docs, {len(lb.get('pages',[]))} pages under run {run_id}")


if __name__ == "__main__":
    main()
