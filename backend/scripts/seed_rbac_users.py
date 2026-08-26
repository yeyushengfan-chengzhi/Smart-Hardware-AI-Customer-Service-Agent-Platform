"""Create or normalize the three local RBAC acceptance accounts."""

import os
import sys
from pathlib import Path

from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_database  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402


DEMO_ACCOUNTS = {
    "user_demo": "user",
    "agent_demo": "agent",
    "admin_demo": "admin",
}


def main() -> int:
    password = os.getenv("RBAC_DEMO_PASSWORD", "123456")
    init_database()
    with SessionLocal() as db:
        for username, role in DEMO_ACCOUNTS.items():
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(username=username, password_hash=hash_password(password), role=role)
                db.add(user)
                action = "created"
            else:
                user.password_hash = hash_password(password)
                user.role = role
                action = "updated"
            print(f"{username}: role={role} ({action})")
        db.commit()
    print("RBAC demo accounts are ready. Password comes from RBAC_DEMO_PASSWORD or the documented development default.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
