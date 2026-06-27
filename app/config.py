"""Central config — read from env with sane defaults."""
import os

AWS_REGION = os.environ.get("AWS_REGION", "us-east-2")
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "estimator-plans-673611060332")
S3_RAW_PREFIX = os.environ.get("S3_RAW_PREFIX", "raw")
S3_PROCESSED_PREFIX = os.environ.get("S3_PROCESSED_PREFIX", "processed")

DATABASE_URL = os.environ.get("DATABASE_URL", "")   # set once RDS is up

RENDER_DPI = int(os.environ.get("RENDER_DPI", "150"))
WORKER_VERSION = os.environ.get("WORKER_VERSION", "0.1.0")

# which manifest classifications to run page extraction on.
# Strict: only strong plan-set matches. "review" is a noisy catch-all (it let
# inspection reports / applications through), so it's excluded for now.
PLAN_CLASSES = {"keep"}
