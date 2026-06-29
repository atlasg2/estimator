#!/usr/bin/env python3
"""Ingest one project folder into S3 + RDS.

  python scripts/run_ingestion.py --project-dir data/nola/25-19247-RNVS \
      --docs 8400627,8400631 --workers 4 --max-pages 5
"""
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ingest import process_project


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--docs", help="comma-separated DocIDs to process (overrides manifest classification)")
    ap.add_argument("--workers", type=int, default=1, help="parallel page workers")
    ap.add_argument("--max-pages", type=int, default=None, help="cap pages per file (for fast benchmarks)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    only = [d.strip() for d in args.docs.split(",")] if args.docs else None
    t0 = time.perf_counter()
    report = process_project(args.project_dir, only_docids=only, max_pages=args.max_pages,
                             workers=args.workers, force=args.force)
    wall = time.perf_counter() - t0
    print(json.dumps(report, indent=2))
    print(f"\n{report['project']}: {report['pages']} pages in {wall:.1f}s wall "
          f"({args.workers} workers), avg {report.get('avg_page_seconds','?')}s/page (cpu)")
    print("phase totals (cpu-seconds summed across pages):", report["timings"])


if __name__ == "__main__":
    main()
