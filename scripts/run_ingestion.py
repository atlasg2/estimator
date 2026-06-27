#!/usr/bin/env python3
"""Ingest one project folder into S3 + RDS.

  python scripts/run_ingestion.py --project-dir data/nola/25-19247-RNVS
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ingest import process_project


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    report = process_project(args.project_dir, force=args.force)
    print(json.dumps(report, indent=2))
    print(f"\n{report['project']}: {report['pages']} pages processed")


if __name__ == "__main__":
    main()
