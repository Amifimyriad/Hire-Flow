from __future__ import annotations

import csv
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from database.schema import SCHEMA_SQL


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class DatabaseManager:
    def __init__(self, database_file: Path, default_settings: dict[str, str], logger=None):
        self.database_file = database_file
        self.default_settings = default_settings
        self.logger = logger
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            database_file,
            check_same_thread=False,
            timeout=30,
        )
        self._connection.row_factory = sqlite3.Row
        self.initialize()

    @contextmanager
    def _cursor(self) -> Iterable[sqlite3.Cursor]:
        with self._lock:
            cursor = self._connection.cursor()
            try:
                yield cursor
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            finally:
                cursor.close()

    def initialize(self) -> None:
        with self._cursor() as cursor:
            cursor.executescript(SCHEMA_SQL)
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.execute("PRAGMA synchronous = NORMAL")
            now = utc_now()
            cursor.executemany(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                [(key, value, now) for key, value in self.default_settings.items()],
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def save_settings(self, values: dict[str, str]) -> None:
        now = utc_now()
        with self._cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                [(key, value, now) for key, value in values.items()],
            )

    def get_settings(self) -> dict[str, str]:
        with self._cursor() as cursor:
            rows = cursor.execute("SELECT key, value FROM settings").fetchall()
        values = {row["key"]: row["value"] for row in rows}
        merged = self.default_settings.copy()
        merged.update(values)
        return merged

    def _log_event(self, event: str, **fields: object) -> None:
        if self.logger and hasattr(self.logger, "event"):
            self.logger.event(event, component="database", **fields)

    def import_recruiters(self, recruiters: list[dict[str, str]], source_file: str) -> tuple[int, int]:
        inserted = 0
        updated = 0
        now = utc_now()
        with self._cursor() as cursor:
            for recruiter in recruiters:
                existing = cursor.execute(
                    "SELECT id FROM recruiters WHERE email = ?",
                    (recruiter["email"],),
                ).fetchone()
                if existing:
                    cursor.execute(
                        """
                        UPDATE recruiters
                        SET name = ?,
                            company = ?,
                            source_file = ?,
                            active = 1,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            recruiter["name"],
                            recruiter["company"],
                            source_file,
                            now,
                            existing["id"],
                        ),
                    )
                    updated += 1
                else:
                    cursor.execute(
                        """
                        INSERT INTO recruiters(
                            name, company, email, source_file,
                            created_at, updated_at
                        ) VALUES(?, ?, ?, ?, ?, ?)
                        """,
                        (
                            recruiter["name"],
                            recruiter["company"],
                            recruiter["email"],
                            source_file,
                            now,
                            now,
                        ),
                    )
                    inserted += 1
        self._log_event(
            "db_recruiters_imported",
            source_file=source_file,
            inserted=inserted,
            updated=updated,
            total_rows=len(recruiters),
        )
        return inserted, updated

    def get_recruiters(self) -> list[dict]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                """
                SELECT
                    r.*,
                    EXISTS(
                        SELECT 1
                        FROM email_logs e
                        WHERE e.recruiter_id = r.id
                          AND e.email_type = 'initial'
                          AND e.status = 'sent'
                    ) AS initial_sent
                FROM recruiters r
                ORDER BY datetime(r.updated_at) DESC, r.name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_initial_send_candidates(self) -> list[dict]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                """
                SELECT r.*
                FROM recruiters r
                WHERE r.active = 1
                  AND r.reply_status = 0
                  AND NOT EXISTS (
                      SELECT 1
                      FROM email_logs e
                      WHERE e.recruiter_id = r.id
                        AND e.email_type = 'initial'
                        AND e.status = 'sent'
                  )
                ORDER BY r.created_at ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_daily_sent_count(self) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        with self._cursor() as cursor:
            row = cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM email_logs
                WHERE status = 'sent'
                  AND sent_at IS NOT NULL
                  AND substr(sent_at, 1, 10) = ?
                """,
                (today,),
            ).fetchone()
        return int(row["total"])

    def create_email_log(
        self,
        recruiter_id: int | None,
        recruiter_email: str,
        email_type: str,
        subject: str,
        body_html: str,
        status: str,
        attempt_count: int,
        error_message: str | None = None,
        message_id: str | None = None,
        sent_at: str | None = None,
    ) -> int:
        created_at = utc_now()
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO email_logs(
                    recruiter_id, recruiter_email, email_type, subject,
                    body_html, status, error_message, message_id,
                    attempt_count, sent_at, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recruiter_id,
                    recruiter_email,
                    email_type,
                    subject,
                    body_html,
                    status,
                    error_message,
                    message_id,
                    attempt_count,
                    sent_at,
                    created_at,
                ),
            )
            log_id = int(cursor.lastrowid)
        self._log_event(
            "db_email_log_created",
            recruiter_id=recruiter_id,
            recruiter_email=recruiter_email,
            email_type=email_type,
            status=status,
            attempt_count=attempt_count,
            log_id=log_id,
        )
        return log_id

    def mark_initial_sent(self, recruiter_id: int, subject: str, sent_at: str, followup_days: int) -> None:
        due_at = (parse_iso(sent_at) or datetime.now(timezone.utc)) + timedelta(days=followup_days)
        due_at_iso = due_at.replace(microsecond=0).isoformat()
        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE recruiters
                SET first_sent_at = COALESCE(first_sent_at, ?),
                    last_sent_at = ?,
                    last_email_subject = ?,
                    followup_status = 'waiting',
                    updated_at = ?
                WHERE id = ?
                """,
                (sent_at, sent_at, subject, utc_now(), recruiter_id),
            )
            cursor.execute(
                """
                INSERT INTO followups(
                    recruiter_id, due_at, status, attempt_number,
                    created_at, updated_at
                ) VALUES(?, ?, 'pending', 1, ?, ?)
                ON CONFLICT(recruiter_id, attempt_number) DO UPDATE SET
                    due_at = excluded.due_at,
                    status = 'pending',
                    updated_at = excluded.updated_at
                """,
                (recruiter_id, due_at_iso, sent_at, sent_at),
            )
        self.save_conversation_message(
            recruiter_id=recruiter_id,
            direction="outbound",
            message_type="initial",
            subject=subject,
            body_text="",
            body_html="",
            preview_text=subject,
            external_message_id=self._latest_sent_message_id_for_recruiter(recruiter_id, "initial"),
            sent_at=sent_at,
            status="sent",
        )
        self._log_event(
            "db_initial_sent_marked",
            recruiter_id=recruiter_id,
            due_at=due_at_iso,
            sent_at=sent_at,
        )

    def mark_reply_received(self, recruiter_id: int, reply_received_at: str) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE recruiters
                SET reply_status = 1,
                    reply_received_at = ?,
                    followup_status = 'replied',
                    updated_at = ?
                WHERE id = ?
                """,
                (reply_received_at, utc_now(), recruiter_id),
            )
            cursor.execute(
                """
                UPDATE followups
                SET status = 'cancelled',
                    updated_at = ?
                WHERE recruiter_id = ?
                  AND status = 'pending'
                """,
                (utc_now(), recruiter_id),
            )
        self._log_event(
            "db_reply_marked",
            recruiter_id=recruiter_id,
            reply_received_at=reply_received_at,
        )

    def get_unreplied_recruiters(self) -> list[dict]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                """
                SELECT id, name, company, email, first_sent_at
                FROM recruiters
                WHERE first_sent_at IS NOT NULL
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_due_followups(self) -> list[dict]:
        now = utc_now()
        with self._cursor() as cursor:
            rows = cursor.execute(
                """
                SELECT
                    f.id AS followup_id,
                    f.recruiter_id,
                    f.due_at,
                    f.attempt_number,
                    r.name,
                    r.company,
                    r.email,
                    r.followup_count,
                    r.reply_status
                FROM followups f
                JOIN recruiters r ON r.id = f.recruiter_id
                WHERE f.status = 'pending'
                  AND f.due_at <= ?
                  AND r.reply_status = 0
                  AND r.followup_count < 2
                ORDER BY datetime(f.due_at) ASC
                """,
                (now,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_followup_sent(
        self,
        followup_id: int,
        recruiter_id: int,
        sent_log_id: int,
        sent_at: str,
        subject: str,
        body_html: str,
        followup_days: int,
    ) -> None:
        with self._cursor() as cursor:
            recruiter = cursor.execute(
                "SELECT followup_count, reply_status FROM recruiters WHERE id = ?",
                (recruiter_id,),
            ).fetchone()
            if recruiter is None:
                return

            next_count = int(recruiter["followup_count"]) + 1
            cursor.execute(
                """
                UPDATE followups
                SET status = 'sent',
                    subject = ?,
                    body_html = ?,
                    sent_log_id = ?,
                    sent_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (subject, body_html, sent_log_id, sent_at, utc_now(), followup_id),
            )
            followup_status = "maxed_out" if next_count >= 2 else "waiting"
            cursor.execute(
                """
                UPDATE recruiters
                SET followup_count = ?,
                    last_followup_at = ?,
                    followup_status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (next_count, sent_at, followup_status, utc_now(), recruiter_id),
            )
            if next_count < 2 and int(recruiter["reply_status"]) == 0:
                due_at = (parse_iso(sent_at) or datetime.now(timezone.utc)) + timedelta(days=followup_days)
                due_at_iso = due_at.replace(microsecond=0).isoformat()
                cursor.execute(
                    """
                    INSERT INTO followups(
                        recruiter_id, due_at, status, attempt_number,
                        created_at, updated_at
                    ) VALUES(?, ?, 'pending', ?, ?, ?)
                    ON CONFLICT(recruiter_id, attempt_number) DO NOTHING
                    """,
                    (
                        recruiter_id,
                        due_at_iso,
                        next_count + 1,
                        sent_at,
                        sent_at,
                    ),
                )
        self._log_event(
            "db_followup_sent_marked",
            recruiter_id=recruiter_id,
            followup_id=followup_id,
            sent_log_id=sent_log_id,
            sent_at=sent_at,
        )
        self.save_conversation_message(
            recruiter_id=recruiter_id,
            direction="outbound",
            message_type="followup",
            subject=subject,
            body_text="",
            body_html=body_html,
            preview_text=subject,
            external_message_id=self._latest_sent_message_id_for_recruiter(recruiter_id, "followup", sent_log_id),
            sent_at=sent_at,
            status="sent",
        )

    def get_stats(self) -> dict[str, int]:
        with self._cursor() as cursor:
            sent_total = cursor.execute(
                "SELECT COUNT(*) AS total FROM email_logs WHERE status = 'sent'"
            ).fetchone()["total"]
            replies = cursor.execute(
                "SELECT COUNT(*) AS total FROM recruiters WHERE reply_status = 1"
            ).fetchone()["total"]
            pending_followups = cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM followups f
                JOIN recruiters r ON r.id = f.recruiter_id
                WHERE f.status = 'pending'
                  AND f.due_at <= ?
                  AND r.reply_status = 0
                """,
                (utc_now(),),
            ).fetchone()["total"]
            failed = cursor.execute(
                "SELECT COUNT(*) AS total FROM email_logs WHERE status = 'failed'"
            ).fetchone()["total"]
            followup_sent = cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM email_logs
                WHERE status = 'sent' AND email_type = 'followup'
                """
            ).fetchone()["total"]

        return {
            "sent_total": int(sent_total),
            "replies_received": int(replies),
            "pending_followups": int(pending_followups),
            "failed_emails": int(failed),
            "followups_sent": int(followup_sent),
        }

    def list_logs(
        self,
        status: str | None = None,
        email_type: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        query = """
            SELECT
                e.id,
                e.recruiter_email,
                COALESCE(r.name, '') AS recruiter_name,
                COALESCE(r.company, '') AS company,
                e.email_type,
                e.subject,
                e.status,
                e.error_message,
                e.attempt_count,
                e.sent_at,
                e.created_at
            FROM email_logs e
            LEFT JOIN recruiters r ON r.id = e.recruiter_id
            WHERE 1 = 1
        """
        params: list[object] = []
        if status and status != "all":
            query += " AND e.status = ?"
            params.append(status)
        if email_type and email_type != "all":
            query += " AND e.email_type = ?"
            params.append(email_type)
        query += " ORDER BY COALESCE(e.sent_at, e.created_at) DESC LIMIT ?"
        params.append(limit)
        with self._cursor() as cursor:
            rows = cursor.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def recent_activity(self, limit: int = 10) -> list[dict]:
        return self.list_logs(limit=limit)

    def export_logs(self, destination: Path, status: str | None = None, email_type: str | None = None) -> None:
        rows = self.list_logs(status=status, email_type=email_type, limit=10_000)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "id",
                    "recruiter_email",
                    "recruiter_name",
                    "company",
                    "email_type",
                    "subject",
                    "status",
                    "error_message",
                    "attempt_count",
                    "sent_at",
                    "created_at",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

    def refresh_followup_statuses(self) -> int:
        due_count = len(self.get_due_followups())
        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE recruiters
                SET followup_status = 'due',
                    updated_at = ?
                WHERE id IN (
                    SELECT recruiter_id
                    FROM followups
                    WHERE status = 'pending'
                      AND due_at <= ?
                )
                """,
                (utc_now(), utc_now()),
            )
        return due_count

    def get_sent_message_ids_by_recruiter(self, recruiter_ids: list[int]) -> dict[int, set[str]]:
        if not recruiter_ids:
            return {}
        placeholders = ", ".join("?" for _ in recruiter_ids)
        with self._cursor() as cursor:
            rows = cursor.execute(
                f"""
                SELECT recruiter_id, message_id
                FROM email_logs
                WHERE status = 'sent'
                  AND recruiter_id IN ({placeholders})
                  AND message_id IS NOT NULL
                """,
                recruiter_ids,
            ).fetchall()
        grouped: dict[int, set[str]] = {}
        for row in rows:
            recruiter_id = int(row["recruiter_id"])
            grouped.setdefault(recruiter_id, set()).add(str(row["message_id"]).strip().lower())
        return grouped

    def _latest_sent_message_id_for_recruiter(
        self,
        recruiter_id: int,
        email_type: str,
        log_id: int | None = None,
    ) -> str | None:
        query = """
            SELECT message_id
            FROM email_logs
            WHERE recruiter_id = ?
              AND email_type = ?
              AND status = 'sent'
        """
        params: list[object] = [recruiter_id, email_type]
        if log_id is not None:
            query += " AND id = ?"
            params.append(log_id)
        query += " ORDER BY id DESC LIMIT 1"
        with self._cursor() as cursor:
            row = cursor.execute(query, params).fetchone()
        return str(row["message_id"]).strip() if row and row["message_id"] else None

    def save_conversation_message(
        self,
        recruiter_id: int,
        direction: str,
        message_type: str,
        subject: str,
        body_text: str,
        body_html: str,
        preview_text: str,
        external_message_id: str | None = None,
        in_reply_to: str = "",
        references_header: str = "",
        mailbox: str = "",
        status: str = "",
        sent_at: str | None = None,
        received_at: str | None = None,
    ) -> bool:
        now = utc_now()
        external_message_id = (external_message_id or "").strip() or None
        with self._cursor() as cursor:
            if external_message_id:
                existing = cursor.execute(
                    "SELECT id FROM conversation_messages WHERE external_message_id = ?",
                    (external_message_id,),
                ).fetchone()
                if existing:
                    cursor.execute(
                        """
                        UPDATE conversation_messages
                        SET recruiter_id = ?,
                            direction = ?,
                            message_type = ?,
                            subject = ?,
                            body_text = ?,
                            body_html = ?,
                            preview_text = ?,
                            in_reply_to = ?,
                            references_header = ?,
                            mailbox = ?,
                            status = ?,
                            sent_at = COALESCE(?, sent_at),
                            received_at = COALESCE(?, received_at),
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            recruiter_id,
                            direction,
                            message_type,
                            subject,
                            body_text,
                            body_html,
                            preview_text,
                            in_reply_to,
                            references_header,
                            mailbox,
                            status,
                            sent_at,
                            received_at,
                            now,
                            existing["id"],
                        ),
                    )
                    return False
            cursor.execute(
                """
                INSERT INTO conversation_messages(
                    recruiter_id, direction, message_type, subject, body_text, body_html,
                    preview_text, external_message_id, in_reply_to, references_header,
                    mailbox, status, sent_at, received_at, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recruiter_id,
                    direction,
                    message_type,
                    subject,
                    body_text,
                    body_html,
                    preview_text,
                    external_message_id,
                    in_reply_to,
                    references_header,
                    mailbox,
                    status,
                    sent_at,
                    received_at,
                    now,
                    now,
                ),
            )
        return True

    def upsert_inbox_reply(
        self,
        recruiter_id: int,
        subject: str,
        preview: str,
        external_message_id: str | None,
        received_at: str,
    ) -> None:
        now = utc_now()
        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO inbox_replies(
                    recruiter_id, status, latest_subject, latest_preview,
                    latest_message_id, last_received_at, created_at, updated_at
                ) VALUES(?, 'new', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(recruiter_id) DO UPDATE SET
                    latest_subject = excluded.latest_subject,
                    latest_preview = excluded.latest_preview,
                    latest_message_id = excluded.latest_message_id,
                    last_received_at = excluded.last_received_at,
                    archived = 0,
                    updated_at = excluded.updated_at
                """,
                (
                    recruiter_id,
                    subject,
                    preview,
                    external_message_id,
                    received_at,
                    now,
                    now,
                ),
            )

    def list_inbox_replies(self, include_archived: bool = False) -> list[dict]:
        query = """
            SELECT
                r.id AS recruiter_id,
                r.name,
                r.company,
                r.email,
                ir.status,
                ir.interest_status,
                ir.notes,
                ir.archived,
                ir.latest_subject,
                ir.latest_preview,
                ir.latest_message_id,
                ir.last_received_at,
                (
                    SELECT GROUP_CONCAT(cm.subject || '|' || COALESCE(cm.preview_text, ''), '\n---\n')
                    FROM conversation_messages cm
                    WHERE cm.recruiter_id = r.id
                    ORDER BY COALESCE(cm.received_at, cm.sent_at, cm.created_at) ASC
                ) AS full_thread
            FROM inbox_replies ir
            JOIN recruiters r ON r.id = ir.recruiter_id
        """
        params: list[object] = []
        if not include_archived:
            query += " WHERE ir.archived = 0"
        query += " ORDER BY datetime(ir.last_received_at) DESC, r.name COLLATE NOCASE"
        with self._cursor() as cursor:
            rows = cursor.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_conversation_messages(self, recruiter_id: int) -> list[dict]:
        with self._cursor() as cursor:
            rows = cursor.execute(
                """
                SELECT *
                FROM conversation_messages
                WHERE recruiter_id = ?
                ORDER BY datetime(COALESCE(received_at, sent_at, created_at)) ASC, id ASC
                """,
                (recruiter_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_reply_thread_state(self, recruiter_id: int) -> dict | None:
        with self._cursor() as cursor:
            row = cursor.execute(
                """
                SELECT *
                FROM inbox_replies
                WHERE recruiter_id = ?
                """,
                (recruiter_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_inbox_reply_state(
        self,
        recruiter_id: int,
        *,
        status: str | None = None,
        interest_status: str | None = None,
        notes: str | None = None,
        archived: int | None = None,
    ) -> None:
        updates: list[str] = []
        params: list[object] = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if interest_status is not None:
            updates.append("interest_status = ?")
            params.append(interest_status)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if archived is not None:
            updates.append("archived = ?")
            params.append(archived)
        if not updates:
            return
        updates.append("updated_at = ?")
        params.append(utc_now())
        params.append(recruiter_id)
        with self._cursor() as cursor:
            cursor.execute(
                f"UPDATE inbox_replies SET {', '.join(updates)} WHERE recruiter_id = ?",
                params,
            )

    def get_latest_conversation_message(self, recruiter_id: int) -> dict | None:
        with self._cursor() as cursor:
            row = cursor.execute(
                """
                SELECT *
                FROM conversation_messages
                WHERE recruiter_id = ?
                ORDER BY datetime(COALESCE(received_at, sent_at, created_at)) DESC, id DESC
                LIMIT 1
                """,
                (recruiter_id,),
            ).fetchone()
        return dict(row) if row else None

    def reset_runtime_state(self, preserve_settings: bool = True) -> dict[str, int]:
        with self._cursor() as cursor:
            counts_row = cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM recruiters) AS recruiters,
                    (SELECT COUNT(*) FROM email_logs) AS email_logs,
                    (SELECT COUNT(*) FROM followups) AS followups,
                    (SELECT COUNT(*) FROM inbox_replies) AS inbox_replies,
                    (SELECT COUNT(*) FROM conversation_messages) AS conversation_messages,
                    (SELECT COUNT(*) FROM settings) AS settings
                """
            ).fetchone()
        counts = {key: int(counts_row[key]) for key in counts_row.keys()}
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM conversation_messages")
            cursor.execute("DELETE FROM inbox_replies")
            cursor.execute("DELETE FROM followups")
            cursor.execute("DELETE FROM email_logs")
            cursor.execute("DELETE FROM recruiters")
            if not preserve_settings:
                cursor.execute("DELETE FROM settings")
            tables = ["conversation_messages", "inbox_replies", "followups", "email_logs", "recruiters"]
            if not preserve_settings:
                tables.append("settings")
            placeholders = ", ".join("?" for _ in tables)
            cursor.execute(
                f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
                tables,
            )
        with self._lock:
            self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._connection.commit()
            self._connection.execute("VACUUM")
            self._connection.commit()
        self._log_event(
            "db_runtime_state_reset",
            preserve_settings=preserve_settings,
            recruiters_deleted=counts["recruiters"],
            email_logs_deleted=counts["email_logs"],
            followups_deleted=counts["followups"],
            inbox_replies_deleted=counts["inbox_replies"],
            conversation_messages_deleted=counts["conversation_messages"],
            settings_deleted=0 if preserve_settings else counts["settings"],
        )
        return counts
