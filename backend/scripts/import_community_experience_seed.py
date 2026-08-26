"""Import the local community-experience seed into Knowledge Center."""

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_database  # noqa: E402
from app.services.community_experience_import_service import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    DEFAULT_SEED_PATH,
    import_community_experience_seed,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Import the local community experience seed dataset."
    )
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()

    init_database()
    with SessionLocal() as db:
        result = import_community_experience_seed(
            db,
            seed_path=args.seed,
            manifest_path=args.manifest,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
