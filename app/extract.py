"""
Canonical page extraction — the proven Phase 0 logic, refactored to return
in-memory data (bytes + dicts) so the ingestion worker can push to S3/RDS.

Returns, per page: rendered PNG bytes, text items (+coords), vector items
(+coords), an overlay PNG, and a summary that includes the coordinate transform
AND quality/confidence flags (so we always know when a page is NOT trustworthy).
"""
import io, time
import fitz
from PIL import Image, ImageDraw

SOFT_CAP = 10000        # warn-only threshold (flags dense pages)
HARD_CAP = 250000       # safety ceiling only (real sheets run ~25k-95k)


def hexcolor(c):
    if not c:
        return None
    try:
        return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in c[:3])
    except Exception:
        return None


def extract_text(page, mat, page_number):
    out = []
    for bi, block in enumerate(page.get_text("dict").get("blocks", [])):
        if block.get("type", 0) != 0:
            continue
        for li, line in enumerate(block.get("lines", [])):
            for si, span in enumerate(line.get("spans", [])):
                if not span.get("text", "").strip():
                    continue
                r = fitz.Rect(span["bbox"]); pr = r * mat
                out.append({
                    "text": span["text"],
                    "bbox_pdf": [round(v, 2) for v in r],
                    "bbox_px": [round(v, 1) for v in pr],
                    "source": "pymupdf_text_layer", "page_number": page_number,
                    "block_index": bi, "line_index": li, "span_index": si,
                    "rotation": page.rotation,
                })
    return out


def extract_vectors(page, mat, page_number, hard_cap=HARD_CAP):
    out = []
    counts = {"line": 0, "rect": 0, "curve": 0, "quad": 0}
    ei = 0
    for pi, path in enumerate(page.get_drawings()):
        stroke, fill = hexcolor(path.get("color")), hexcolor(path.get("fill"))
        width, dashes = path.get("width"), path.get("dashes")
        for ii, item in enumerate(path.get("items", [])):
            op = item[0]; geom = None; etype = None
            if op == "l":
                etype = "line"; counts["line"] += 1
                geom = [[item[1].x, item[1].y], [item[2].x, item[2].y]]
            elif op == "re":
                etype = "rect"; counts["rect"] += 1
                r = item[1]; geom = [[r.x0, r.y0], [r.x1, r.y0], [r.x1, r.y1], [r.x0, r.y1]]
            elif op == "qu":
                etype = "quad"; counts["quad"] += 1
                q = item[1]
                geom = [[q.ul.x, q.ul.y], [q.ur.x, q.ur.y], [q.lr.x, q.lr.y], [q.ll.x, q.ll.y]]
            elif op == "c":
                etype = "curve"; counts["curve"] += 1
                geom = [[p.x, p.y] for p in (item[1], item[2], item[3], item[4])]
            else:
                continue
            out.append({
                "entity_type": etype, "path_index": pi, "item_index": ii,
                "geometry_pdf": [[round(x, 2), round(y, 2)] for x, y in geom],
                "stroke_width": width,
                "color": stroke, "fill_color": fill,
                "dash_pattern": dashes if dashes and dashes != "[] 0" else None,
                "is_closed": path.get("closePath", False),
                "source": "pymupdf_get_drawings",
                "page_number": page_number, "entity_index": ei,
            })
            ei += 1
            if ei >= hard_cap:
                return out, counts, True
    return out, counts, False


def build_overlay(png_bytes, text_items, vec_items, mat, max_vectors=HARD_CAP):
    """Derive pixel coords on demand from stored geometry_pdf + the transform."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    dr = ImageDraw.Draw(img)
    for v in vec_items[:max_vectors]:
        g = [tuple(fitz.Point(x, y) * mat) for x, y in v["geometry_pdf"]]
        if v["entity_type"] in ("rect", "quad"):
            dr.line(g + [g[0]], fill=(220, 0, 0), width=2)
        elif len(g) >= 2:
            dr.line(g, fill=(220, 0, 0), width=2)
    for t in text_items:
        dr.rectangle(t["bbox_px"], outline=(0, 80, 255), width=2)
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def classify_representation(full_text, n_vec, n_img):
    """Derived label from measured facts (recomputable; nothing baked-in).
    NOT a trustworthiness judgment — just 'what kind of page is this'."""
    has_text = len(full_text.strip()) > 0
    if not has_text and n_img > 0:
        return "scanned_image_page"
    if n_vec > 50:
        return "digital_text_vector_page"
    if has_text:
        return "text_only_page"
    return "light_vector_page"


def extract_page(page, page_number, render_dpi=150, hard_cap=HARD_CAP,
                 make_overlay=False, max_overlay_vectors=HARD_CAP):
    """Full extraction for one page. Returns dict of bytes + json-able data.

    Overlays are QA-only and regenerable from the stored image+JSON, so they are
    OFF by default (they are the slowest/heaviest step). Pass make_overlay=True
    for spot-checks."""
    zoom = render_dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    timings = {}
    t = time.perf_counter()
    pix = page.get_pixmap(matrix=mat)
    page_png = pix.tobytes("png")
    timings["render_seconds"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    text_items = extract_text(page, mat, page_number)
    timings["text_extract_seconds"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    vec_items, counts, truncated = extract_vectors(page, mat, page_number, hard_cap)
    timings["vector_extract_seconds"] = round(time.perf_counter() - t, 3)

    overlay_png = build_overlay(page_png, text_items, vec_items, mat, max_overlay_vectors) if make_overlay else None

    full_text = page.get_text("text")
    weird = sum(1 for ch in full_text if ord(ch) == 0xFFFD or (ord(ch) < 32 and ch not in "\n\r\t"))
    weird_ratio = round(weird / max(len(full_text), 1), 4)
    n_vec, n_img = len(vec_items), len(page.get_images())
    rep = classify_representation(full_text, n_vec, n_img)

    summary = {
        "page_number": page_number, "render_dpi": render_dpi,
        "width_px": pix.width, "height_px": pix.height,
        "width_pdf_points": round(page.rect.width, 2),
        "height_pdf_points": round(page.rect.height, 2),
        "rotation": page.rotation,
        "text_block_count": len(text_items), "full_text_length": len(full_text),
        "weird_character_ratio": weird_ratio,
        "has_embedded_text": len(full_text.strip()) > 0,
        "vector_entity_count": n_vec, "line_count": counts["line"],
        "rect_count": counts["rect"], "curve_count": counts["curve"],
        "quad_count": counts["quad"], "image_object_count": n_img,
        "vector_soft_cap_exceeded": n_vec >= SOFT_CAP, "vectors_truncated": truncated,
        "page_representation_type": rep,
        "coordinate_transform_json": {
            "render_dpi": render_dpi, "zoom": zoom,
            "page_rect": [round(v, 2) for v in page.rect], "rotation": page.rotation,
            "rendered_width_px": pix.width, "rendered_height_px": pix.height,
            "pdf_to_px_matrix": [mat.a, mat.b, mat.c, mat.d, mat.e, mat.f],
            "notes": ["pixel = pdf_point * matrix"],
        },
    }
    return {
        "page_png": page_png, "overlay_png": overlay_png,
        "text_items": text_items, "vec_items": vec_items, "summary": summary,
        "timings": timings,
    }
