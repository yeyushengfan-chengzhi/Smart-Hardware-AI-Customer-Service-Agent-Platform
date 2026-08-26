"""Scan uploads/knowledge and incrementally process all supported documents."""

import json
import logging
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_database  # noqa: E402
from app.services.knowledge_pipeline_service import process_directory  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    init_database()
    results = process_directory(SessionLocal)
    for result in results:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    failed = sum(result.status == "failed" for result in results)
    print(f"processed={len(results)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
