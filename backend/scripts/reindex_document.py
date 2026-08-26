"""Rebuild parsed chunks and Chroma vectors for one knowledge document."""

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_database  # noqa: E402
from app.services.reindex_service import reindex_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", type=int, required=True)
    args = parser.parse_args()
    if args.document_id < 1:
        parser.error("--document-id must be a positive integer")

    init_database()
    with SessionLocal() as db:
        stats = reindex_document(db, args.document_id)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
