"""
Phase 1 ingestion worker: local project folder -> S3 artifacts + RDS metadata.

Idempotent (re-runnable). Per page it stores the rendered image, text JSON,
vector JSON, overlay, and full metadata INCLUDING quality/confidence flags, so
the dataset always records when a page is not fully trustworthy.

  python scripts/run_ingestion.py --project-dir data/nola/25-19247-RNVS
"""
import hashlib, io, json, os, re
import boto3, psycopg
from psycopg.types.json import Jsonb

from . import config as C
from .extract import extract_page


# ---------- helpers ----------
def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def s3_client():
    return boto3.client("s3", region_name=C.AWS_REGION)

def s3_put(s3, key, data, content_type):
    s3.put_object(Bucket=C.S3_BUCKET, Key=key, Body=data, ContentType=content_type)
    return key


# ---------- db upserts ----------
def upsert_project(cur, slug, name, raw_prefix, proc_prefix):
    cur.execute("""
        INSERT INTO projects (slug, name, source, s3_raw_prefix, s3_processed_prefix)
        VALUES (%s, %s, 'nola_onestop', %s, %s)
        ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, updated_at=now()
        RETURNING id""", (slug, name, raw_prefix, proc_prefix))
    return cur.fetchone()[0]

def upsert_file(cur, project_id, doc, rel_path, s3_key, file_slug, size, sha, pages):
    cur.execute("""
        INSERT INTO project_files (project_id, source_document_id, original_file_name,
            relative_path, s3_object_key, file_slug, file_type, file_size_bytes,
            sha256, page_count, processing_status)
        VALUES (%s,%s,%s,%s,%s,%s,'pdf',%s,%s,%s,'pending')
        ON CONFLICT (project_id, sha256) DO UPDATE SET
            s3_object_key=EXCLUDED.s3_object_key, page_count=EXCLUDED.page_count,
            updated_at=now()
        RETURNING id""",
        (project_id, str(doc.get("docId")), doc["name"], rel_path, s3_key,
         file_slug, size, sha, pages))
    return cur.fetchone()[0]

def upsert_page(cur, project_id, file_id, s):
    cur.execute("""
        INSERT INTO plan_pages (project_id, file_id, pdf_page_number, width_px, height_px,
            render_dpi, width_pdf_points, height_pdf_points, rotation, coordinate_transform_json,
            has_embedded_text, text_block_count, full_text_length, weird_character_ratio,
            has_vectors, vector_entity_count, line_count, rect_count, curve_count,
            image_object_count, vector_soft_cap_exceeded, vectors_truncated,
            page_representation_type, processing_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'processed')
        ON CONFLICT (file_id, pdf_page_number) DO UPDATE SET
            vector_entity_count=EXCLUDED.vector_entity_count,
            page_representation_type=EXCLUDED.page_representation_type,
            coordinate_transform_json=EXCLUDED.coordinate_transform_json,
            processing_status='processed', updated_at=now()
        RETURNING id""",
        (project_id, file_id, s["page_number"], s["width_px"], s["height_px"],
         s["render_dpi"], s["width_pdf_points"], s["height_pdf_points"], s["rotation"],
         Jsonb(s["coordinate_transform_json"]), s["has_embedded_text"], s["text_block_count"],
         s["full_text_length"], s["weird_character_ratio"], s["vector_entity_count"] > 0,
         s["vector_entity_count"], s["line_count"], s["rect_count"], s["curve_count"],
         s["image_object_count"], s["vector_soft_cap_exceeded"], s["vectors_truncated"],
         s["page_representation_type"]))
    return cur.fetchone()[0]

def upsert_artifact(cur, page_id, atype, key, size, ctype, meta=None):
    cur.execute("""
        INSERT INTO page_artifacts (page_id, artifact_type, s3_object_key, file_size_bytes,
            content_type, metadata_json)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (page_id, artifact_type) DO UPDATE SET
            s3_object_key=EXCLUDED.s3_object_key, file_size_bytes=EXCLUDED.file_size_bytes,
            metadata_json=EXCLUDED.metadata_json, updated_at=now()""",
        (page_id, atype, key, size, ctype, Jsonb(meta) if meta else None))

def log_event(cur, run_id, project_id, level, etype, msg, file_id=None, page_id=None, meta=None):
    cur.execute("""
        INSERT INTO ingestion_events (processing_run_id, project_id, file_id, page_id,
            event_type, event_level, message, metadata_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (run_id, project_id, file_id, page_id, etype, level, msg, Jsonb(meta) if meta else None))


# ---------- main ----------
def process_project(project_dir, force=False):
    manifest = json.load(open(os.path.join(project_dir, "manifest.json")))
    permit = manifest["permitNum"]
    slug = slugify(permit)
    raw_prefix = f"{C.S3_RAW_PREFIX}/{slug}"
    proc_prefix = f"{C.S3_PROCESSED_PREFIX}/{slug}"

    s3 = s3_client()
    report = {"project": permit, "files": [], "pages": 0}

    with psycopg.connect(C.DATABASE_URL, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO processing_runs (run_type, status, worker_version)
                           VALUES ('project_ingest','running',%s) RETURNING id""",
                        (C.WORKER_VERSION,))
            run_id = cur.fetchone()[0]
            project_id = upsert_project(cur, slug, manifest.get("address", permit),
                                        raw_prefix, proc_prefix)
            conn.commit()

            for doc in manifest["documents"]:
                if not doc.get("isPdf") or "file" not in doc:
                    continue
                local = os.path.join(project_dir, doc["file"])
                if not os.path.exists(local):
                    continue
                file_slug = f"{doc['docId']}"
                sha = sha256_file(local)
                size = os.path.getsize(local)
                raw_key = f"{raw_prefix}/documents/{file_slug}.pdf"
                # upload raw (always — source of truth)
                with open(local, "rb") as fh:
                    s3_put(s3, raw_key, fh.read(), "application/pdf")

                is_plan = doc.get("classification") in C.PLAN_CLASSES
                import fitz
                d = fitz.open(local)
                pages = d.page_count
                file_id = upsert_file(cur, project_id, doc, doc["file"], raw_key,
                                      file_slug, size, sha, pages)
                conn.commit()
                finfo = {"doc": doc["name"], "classification": doc.get("classification"),
                         "pages": pages, "processed_pages": 0, "plan": is_plan}

                if not is_plan:
                    cur.execute("UPDATE project_files SET processing_status='skipped_not_plan' WHERE id=%s", (file_id,))
                    log_event(cur, run_id, project_id, "info", "file_skipped",
                              f"{doc['name']} classified {doc.get('classification')}", file_id=file_id)
                    conn.commit(); report["files"].append(finfo); continue

                for pno in range(pages):
                    res = extract_page(d[pno], pno + 1, render_dpi=C.RENDER_DPI)
                    s = res["summary"]
                    base = f"{proc_prefix}/{file_slug}"
                    n = f"page_{pno+1:03d}"
                    k_img = s3_put(s3, f"{base}/pages/{n}.png", res["page_png"], "image/png")
                    k_txt = s3_put(s3, f"{base}/text/{n}_text.json",
                                   json.dumps(res["text_items"]).encode(), "application/json")
                    k_vec = s3_put(s3, f"{base}/vectors/{n}_vectors.json",
                                   json.dumps(res["vec_items"]).encode(), "application/json")

                    page_id = upsert_page(cur, project_id, file_id, s)
                    upsert_artifact(cur, page_id, "page_image", k_img, len(res["page_png"]), "image/png")
                    upsert_artifact(cur, page_id, "text_json", k_txt, None, "application/json")
                    upsert_artifact(cur, page_id, "vector_json", k_vec, None, "application/json")
                    if res["overlay_png"]:
                        k_ov = s3_put(s3, f"{base}/overlays/{n}_overlay.png", res["overlay_png"], "image/png")
                        upsert_artifact(cur, page_id, "overlay_image", k_ov, len(res["overlay_png"]), "image/png")
                    report["pages"] += 1; finfo["processed_pages"] += 1
                    conn.commit()

                cur.execute("UPDATE project_files SET processing_status='processed' WHERE id=%s", (file_id,))
                conn.commit()
                report["files"].append(finfo)

            cur.execute("UPDATE processing_runs SET status='succeeded', finished_at=now() WHERE id=%s", (run_id,))
            conn.commit()
    return report
