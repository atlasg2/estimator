#!/usr/bin/env python3
"""
Phase 0 coordinate-extraction spike.

Proves we can render a construction-PDF page, extract its text and vector
geometry with correct coordinates, transform PDF points -> rendered pixels, and
draw an overlay that lines up with the real page.

NO AWS, NO DB, NO ML. Local files only. The single thing this must get right is
the PDF-point -> pixel coordinate transform (verified by eyeballing the overlay).

Usage:
  python scripts/spike_coordinates.py --pdf <file.pdf> --page 17 --render-dpi 150
"""
import argparse, json, os, re, sys
import fitz  # PyMuPDF
from PIL import Image, ImageDraw

SOFT_CAP = 10000      # warn-only: flags dense pages, does not drop anything
HARD_CAP = 250000     # safety ceiling only (real sheets run ~25k–95k vectors)


def hexcolor(c):
    if not c:
        return None
    try:
        return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in c[:3])
    except Exception:
        return None


def extract_text(page, mat, page_number):
    """Every text span with bbox in BOTH pdf points and pixels."""
    out = []
    d = page.get_text("dict")
    for bi, block in enumerate(d.get("blocks", [])):
        if block.get("type", 0) != 0:      # 0 = text, 1 = image
            continue
        for li, line in enumerate(block.get("lines", [])):
            for si, span in enumerate(line.get("spans", [])):
                txt = span.get("text", "")
                if not txt.strip():
                    continue
                r = fitz.Rect(span["bbox"])
                pr = r * mat               # transform to pixel space
                out.append({
                    "text": txt,
                    "bbox_pdf": [round(v, 2) for v in r],
                    "bbox_px": [round(v, 1) for v in pr],
                    "source": "pymupdf_text_layer",
                    "page_number": page_number,
                    "block_index": bi, "line_index": li, "span_index": si,
                    "rotation": page.rotation,
                })
    return out


def extract_vectors(page, mat, page_number, hard_cap=HARD_CAP):
    """Every drawing primitive with geometry in pdf points and pixels."""
    out = []
    counts = {"line": 0, "rect": 0, "curve": 0, "quad": 0}
    drawings = page.get_drawings()
    ei = 0
    for pi, path in enumerate(drawings):
        stroke = hexcolor(path.get("color"))
        fill = hexcolor(path.get("fill"))
        width = path.get("width")
        dashes = path.get("dashes")
        for ii, item in enumerate(path.get("items", [])):
            op = item[0]
            geom_pdf = None
            etype = None
            if op == "l":                       # line p1->p2
                etype = "line"; counts["line"] += 1
                pts = [item[1], item[2]]
                geom_pdf = [[p.x, p.y] for p in pts]
            elif op == "re":                    # rectangle
                etype = "rect"; counts["rect"] += 1
                r = item[1]
                geom_pdf = [[r.x0, r.y0], [r.x1, r.y0], [r.x1, r.y1], [r.x0, r.y1]]
            elif op == "qu":                    # quad
                etype = "quad"; counts["quad"] += 1
                q = item[1]
                geom_pdf = [[q.ul.x, q.ul.y], [q.ur.x, q.ur.y],
                            [q.lr.x, q.lr.y], [q.ll.x, q.ll.y]]
            elif op == "c":                     # bezier (store endpoints+controls)
                etype = "curve"; counts["curve"] += 1
                pts = [item[1], item[2], item[3], item[4]]
                geom_pdf = [[p.x, p.y] for p in pts]
            else:
                continue
            geom_px = [[round((fitz.Point(x, y) * mat).x, 1),
                        round((fitz.Point(x, y) * mat).y, 1)] for x, y in geom_pdf]
            out.append({
                "entity_type": etype,
                "path_index": pi, "item_index": ii,
                "geometry_pdf": [[round(x, 2), round(y, 2)] for x, y in geom_pdf],
                "geometry_px": geom_px,
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


def draw_overlay(base_png, text_items, vec_items, out_png, max_vectors):
    img = Image.open(base_png).convert("RGB")
    dr = ImageDraw.Draw(img)
    # red vector lines (capped)
    for v in vec_items[:max_vectors]:
        g = v["geometry_px"]
        if v["entity_type"] in ("rect", "quad"):
            dr.line(g + [g[0]], fill=(220, 0, 0), width=2)
        elif len(g) >= 2:
            dr.line(g, fill=(220, 0, 0), width=2)
    # blue text boxes (on top)
    for t in text_items:
        x0, y0, x1, y1 = t["bbox_px"]
        dr.rectangle([x0, y0, x1, y1], outline=(0, 80, 255), width=2)
    img.save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--page", type=int, required=True, help="1-based page number")
    ap.add_argument("--render-dpi", type=int, default=150)
    ap.add_argument("--output-dir", default="./spike_output")
    ap.add_argument("--max-overlay-vectors", type=int, default=250000)
    ap.add_argument("--hard-cap", type=int, default=HARD_CAP,
                    help="max vector entities to extract (use a huge number to disable)")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    doc = fitz.open(args.pdf)
    pno = args.page - 1
    page = doc[pno]

    zoom = args.render_dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    base = re.sub(r'[^A-Za-z0-9]+', '_', os.path.splitext(os.path.basename(args.pdf))[0])[:40]
    stem = os.path.join(args.output_dir, f"{base}_page_{args.page:03d}")

    # 1. render page image
    pix = page.get_pixmap(matrix=mat)
    page_png = stem + ".png"
    pix.save(page_png)

    # 2. extract text + vectors
    text_items = extract_text(page, mat, args.page)
    vec_items, counts, truncated = extract_vectors(page, mat, args.page, args.hard_cap)

    # 3. overlay
    overlay_png = stem + "_overlay.png"
    draw_overlay(page_png, text_items, vec_items, overlay_png, args.max_overlay_vectors)

    # 4. write json artifacts
    json.dump(text_items, open(stem + "_text.json", "w"))
    json.dump(vec_items, open(stem + "_vectors.json", "w"))

    full_text = page.get_text("text")
    weird = sum(1 for ch in full_text if ord(ch) == 0xFFFD or (ord(ch) < 32 and ch not in "\n\r\t"))
    weird_ratio = round(weird / max(len(full_text), 1), 4)
    n_vec = len(vec_items)
    rep = ("scanned_image_page" if (len(full_text.strip()) < 40 and len(page.get_images()) > 0)
           else "digital_text_vector_page" if n_vec > 50 else "light_vector_page")
    warnings = []
    if n_vec >= SOFT_CAP:
        warnings.append(f"vector_soft_cap_exceeded ({n_vec} >= {SOFT_CAP})")
    if truncated:
        warnings.append(f"vectors_truncated at HARD_CAP {HARD_CAP}")

    summary = {
        "pdf_path": args.pdf, "page_number": args.page,
        "render_dpi": args.render_dpi,
        "width_px": pix.width, "height_px": pix.height,
        "width_pdf_points": round(page.rect.width, 2),
        "height_pdf_points": round(page.rect.height, 2),
        "rotation": page.rotation,
        "text_block_count": len(text_items),
        "full_text_length": len(full_text),
        "weird_character_ratio": weird_ratio,
        "has_embedded_text": len(full_text.strip()) > 0,
        "vector_entity_count": n_vec,
        "line_count": counts["line"], "rect_count": counts["rect"],
        "curve_count": counts["curve"], "quad_count": counts["quad"],
        "image_object_count": len(page.get_images()),
        "vector_soft_cap_exceeded": n_vec >= SOFT_CAP,
        "vectors_truncated": truncated,
        "page_representation_type": rep,
        "coordinate_transform_json": {
            "render_dpi": args.render_dpi, "zoom": zoom,
            "page_rect": [round(v, 2) for v in page.rect],
            "rotation": page.rotation,
            "rendered_width_px": pix.width, "rendered_height_px": pix.height,
            "pdf_to_px_matrix": [mat.a, mat.b, mat.c, mat.d, mat.e, mat.f],
            "notes": ["pixel = pdf_point * matrix; rotation handled by fitz render+coords"],
        },
        "warnings": warnings,
        "outputs": {
            "page_image": page_png, "text_json": stem + "_text.json",
            "vector_json": stem + "_vectors.json", "overlay_image": overlay_png,
        },
    }
    json.dump(summary, open(stem + "_summary.json", "w"), indent=2)

    print(json.dumps({k: summary[k] for k in (
        "page_number", "rotation", "width_px", "height_px",
        "text_block_count", "vector_entity_count", "line_count", "rect_count",
        "curve_count", "page_representation_type", "warnings")}, indent=2))
    print("overlay ->", overlay_png)


if __name__ == "__main__":
    main()
