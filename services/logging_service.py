from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LogService:
    def __init__(self, log_file: Path, enable_console: bool = True):
        self.log_file = log_file
        self.enable_console = enable_console
        self.logger = logging.getLogger("hireflow")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self._configure()

    def _configure(self) -> None:
        if self.logger.handlers:
            return
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = RotatingFileHandler(
            self.log_file,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        if self.enable_console:
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            self.logger.addHandler(console)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def exception(self, message: str) -> None:
        self.logger.exception(message)

    @staticmethod
    def _serialize_field(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(str(value), ensure_ascii=True)

    def event(self, event: str, level: str = "info", **fields: object) -> None:
        parts = [f"event={event}"]
        for key in sorted(fields):
            parts.append(f"{key}={self._serialize_field(fields[key])}")
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, " ".join(parts))

    def tail(self, limit: int = 300) -> str:
        if not self.log_file.exists():
            return ""
        lines = self.log_file.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[-limit:])

    def clear(self) -> None:
        if not self.log_file.exists():
            return
        self.log_file.write_text("", encoding="utf-8")
