from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import build_config
from database import DatabaseManager
from services import LogService


def main() -> int:
    config = build_config()
    logger = LogService(config.paths.log_file, enable_console=True)
    database = DatabaseManager(config.paths.database_file, config.default_settings, logger=logger)
    try:
        counts = database.reset_runtime_state(preserve_settings=True)
        logger.clear()
    finally:
        database.close()
    print(
        "Runtime data cleared:",
        f"recruiters={counts['recruiters']}",
        f"email_logs={counts['email_logs']}",
        f"followups={counts['followups']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
