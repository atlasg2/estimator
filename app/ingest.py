"""
Phase 1 ingestion worker: local project folder -> S3 artifacts + RDS metadata.

Idempotent (re-runnable). Stores measured facts only. Vector geometry is stored
in PDF coordinates (pixels derived on demand from the per-page transform). Text +
vector JSON are gzipped. Pages can be processed in parallel (--workers); each
worker process owns its DB connection + S3 client (psycopg/boto3 are not fork-safe
to share).

  python scripts/run_ingestion.py --project-dir data/nola/25-19247-RNVS \
      --docs 8400627,8400631 --workers 4
"""
import gzip, hashlib, json, os, re, time
import multiprocessing as mp
import boto3, psycopg
from psycopg.types.json import Jsonb

from . import config as C
from .extract import extract_page

JSON_META = {"content_encoding": "gzip", "logical_format": "json"}


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

def s3_put(s3, key, data, content_type, encoding=None):
    extra = {"ContentEncoding": encoding} if encoding else {}
    s3.put_object(Bucket=C.S3_BUCKET, Key=key, Body=data, ContentType=content_type, **extra)
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
            s3_object_key=EXCLUDED.s3_object_key, page_count=EXCLUDED.page_count, updated_at=now()
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
        INSERT INTO page_artifacts (page_id, artifact_type, s3_object_key, file_size_bytes, content_type, metadata_json)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (page_id, artifact_type) DO UPDATE SET
            s3_object_key=EXCLUDED.s3_object_key, file_size_bytes=EXCLUDED.file_size_bytes,
            metadata_json=EXCLUDED.metadata_json, updated_at=now()""",
        (page_id, atype, key, size, ctype, Jsonb(meta) if meta else None))


# ---------- per-page unit (extract -> gzip -> upload -> db) ----------
def _process_page(cur, s3, dpdf, pno, project_id, file_id, proc_prefix, file_slug, render_dpi):
    t0 = time.perf_counter()
    res = extract_page(dpdf[pno], pno + 1, render_dpi=render_dpi)
    s = res["summary"]; tm = dict(res["timings"])
    base = f"{proc_prefix}/{file_slug}"; n = f"page_{pno+1:03d}"

    t = time.perf_counter()
    txt_gz = gzip.compress(json.dumps(res["text_items"]).encode())
    vec_gz = gzip.compress(json.dumps(res["vec_items"]).encode())
    tm["json_gzip_seconds"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    k_img = s3_put(s3, f"{base}/pages/{n}.png", res["page_png"], "image/png")
    k_txt = s3_put(s3, f"{base}/text/{n}_text.json.gz", txt_gz, "application/json", "gzip")
    k_vec = s3_put(s3, f"{base}/vectors/{n}_vectors.json.gz", vec_gz, "application/json", "gzip")
    tm["s3_upload_seconds"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    page_id = upsert_page(cur, project_id, file_id, s)
    upsert_artifact(cur, page_id, "page_image", k_img, len(res["page_png"]), "image/png")
    upsert_artifact(cur, page_id, "text_json", k_txt, len(txt_gz), "application/json",
                    {**JSON_META, "coordinate_space": "pdf+px"})
    upsert_artifact(cur, page_id, "vector_json", k_vec, len(vec_gz), "application/json",
                    {**JSON_META, "coordinate_space": "pdf"})
    tm["db_write_seconds"] = round(time.perf_counter() - t, 3)
    tm["total_page_seconds"] = round(time.perf_counter() - t0, 3)
    return s["vector_entity_count"], tm


def _worker_chunk(args):
    """Runs in a forked process: owns its DB connection + S3 client + PDF handle."""
    pdf_path, page_numbers, project_id, file_id, proc_prefix, file_slug, render_dpi = args
    import fitz
    dpdf = fitz.open(pdf_path)
    s3 = s3_client()
    out = []
    with psycopg.connect(C.DATABASE_URL) as conn:
        for pno in page_numbers:
            with conn.cursor() as cur:
                vc, tm = _process_page(cur, s3, dpdf, pno, project_id, file_id,
                                       proc_prefix, file_slug, render_dpi)
            conn.commit()
            out.append((pno, vc, tm))
    return out


# ---------- main ----------
def _agg_timings(all_tm):
    if not all_tm:
        return {}
    keys = [k for k in all_tm[0] if k.endswith("_seconds")]
    return {k: round(sum(t.get(k, 0) for t in all_tm), 1) for k in keys}


def process_project(project_dir, only_docids=None, max_pages=None, workers=1, force=False):
    import fitz
    manifest = json.load(open(os.path.join(project_dir, "manifest.json")))
    permit = manifest["permitNum"]; slug = slugify(permit)
    raw_prefix = f"{C.S3_RAW_PREFIX}/{slug}"; proc_prefix = f"{C.S3_PROCESSED_PREFIX}/{slug}"
    only = set(str(x) for x in only_docids) if only_docids else None
    s3 = s3_client()
    report = {"project": permit, "files": [], "pages": 0, "timings": {}}
    all_tm = []

    with psycopg.connect(C.DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO processing_runs (run_type, status, worker_version) VALUES ('project_ingest','running',%s) RETURNING id", (C.WORKER_VERSION,))
        run_id = cur.fetchone()[0]
        project_id = upsert_project(cur, slug, manifest.get("address", permit), raw_prefix, proc_prefix)
        conn.commit()

    for doc in manifest["documents"]:
        if not doc.get("isPdf") or "file" not in doc:
            continue
        local = os.path.join(project_dir, doc["file"])
        if not os.path.exists(local):
            continue
        file_slug = str(doc["docId"]); sha = sha256_file(local); size = os.path.getsize(local)
        raw_key = f"{raw_prefix}/documents/{file_slug}.pdf"
        with open(local, "rb") as fh:                    # raw always uploaded (source of truth)
            s3_put(s3, raw_key, fh.read(), "application/pdf")

        is_plan = (file_slug in only) if only is not None else (doc.get("classification") in C.PLAN_CLASSES)
        pages = fitz.open(local).page_count
        with psycopg.connect(C.DATABASE_URL) as conn, conn.cursor() as cur:
            file_id = upsert_file(cur, project_id, doc, doc["file"], raw_key, file_slug, size, sha, pages)
            if not is_plan:
                cur.execute("UPDATE project_files SET processing_status='skipped_not_plan' WHERE id=%s", (file_id,))
            conn.commit()
        finfo = {"doc": doc["name"], "pages": pages, "processed_pages": 0, "plan": is_plan}
        if not is_plan:
            report["files"].append(finfo); continue

        todo = list(range(min(pages, max_pages) if max_pages else pages))
        if workers <= 1:
            dpdf = fitz.open(local)
            with psycopg.connect(C.DATABASE_URL) as conn:
                for pno in todo:
                    with conn.cursor() as cur:
                        _, tm = _process_page(cur, s3, dpdf, pno, project_id, file_id, proc_prefix, file_slug, C.RENDER_DPI)
                    conn.commit(); all_tm.append(tm); report["pages"] += 1; finfo["processed_pages"] += 1
        else:
            chunks = [todo[i::workers] for i in range(workers)]            # round-robin balances dense pages
            jobs = [(local, ch, project_id, file_id, proc_prefix, file_slug, C.RENDER_DPI) for ch in chunks if ch]
            with mp.Pool(workers) as pool:
                for res in pool.map(_worker_chunk, jobs):
                    for _pno, _vc, tm in res:
                        all_tm.append(tm); report["pages"] += 1; finfo["processed_pages"] += 1

        with psycopg.connect(C.DATABASE_URL) as conn, conn.cursor() as cur:
            cur.execute("UPDATE project_files SET processing_status='processed' WHERE id=%s", (file_id,))
            conn.commit()
        report["files"].append(finfo)

    report["timings"] = _agg_timings(all_tm)
    if all_tm:
        report["avg_page_seconds"] = round(sum(t["total_page_seconds"] for t in all_tm) / len(all_tm), 2)
    with psycopg.connect(C.DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("UPDATE processing_runs SET status='succeeded', finished_at=now() WHERE id=%s", (run_id,))
        conn.commit()
    return report
