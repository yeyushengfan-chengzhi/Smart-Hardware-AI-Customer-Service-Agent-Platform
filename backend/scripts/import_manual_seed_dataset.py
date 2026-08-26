"""Import the local official-manual seed manifest into Knowledge Center."""

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_database  # noqa: E402
from app.services.manual_seed_import_service import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    ManifestUpdatingError,
    import_manual_seed_dataset,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Import downloaded official manual seed PDFs."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to download_manifest.json",
    )
    args = parser.parse_args()

    init_database()
    try:
        with SessionLocal() as db:
            result = import_manual_seed_dataset(db, manifest_path=args.manifest)
    except ManifestUpdatingError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
