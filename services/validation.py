from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

EMAIL_COLUMNS = {"email", "email address", "recruiter email", "mail"}
NAME_COLUMNS = {"name", "recruiter", "recruiter name", "full name", "contact"}
COMPANY_COLUMNS = {"company", "organization", "organisation", "employer"}
GENERIC_COMPANY_DOMAINS = {
    "gmail",
    "yahoo",
    "outlook",
    "hotmail",
    "live",
    "icloud",
    "aol",
    "msn",
    "protonmail",
    "gmx",
    "zoho",
}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(normalize_email(email)))


def _titleize(value: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"\s+", value.strip()) if part)


def parse_recruiter_identity(email: str) -> dict[str, str]:
    normalized = normalize_email(email)
    local, _, domain = normalized.partition("@")
    company_root = domain.split(".", 1)[0] if domain else ""
    recruiter_name = _titleize(re.sub(r"[^a-z0-9]+", " ", local, flags=re.I)) or "Unknown"
    company_name = ""
    if company_root and company_root not in GENERIC_COMPANY_DOMAINS:
        company_name = _titleize(re.sub(r"[^a-z0-9]+", " ", company_root, flags=re.I))
    return {
        "name": recruiter_name,
        "company": company_name,
        "email": normalized,
    }


@dataclass(slots=True)
class RecruiterImportPreview:
    valid_rows: list[dict[str, str]]
    invalid_rows: list[dict[str, str]]
    preview_rows: list[dict[str, str]]
    source_file: str


class RecruiterFileService:
    def _read_file(self, file_path: Path) -> pd.DataFrame:
        if file_path.suffix.lower() == ".csv":
            return pd.read_csv(file_path)
        if file_path.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(file_path)
        raise ValueError("Unsupported file type. Please select a CSV or Excel file.")

    @staticmethod
    def _resolve_column(columns: list[str], candidates: set[str]) -> str | None:
        normalized = {column.strip().lower(): column for column in columns}
        for candidate in candidates:
            if candidate in normalized:
                return normalized[candidate]
        return None

    def load_preview(self, file_path: str) -> RecruiterImportPreview:
        path = Path(file_path)
        frame = self._read_file(path).fillna("")
        frame.columns = [str(column).strip() for column in frame.columns]
        email_column = self._resolve_column(frame.columns.tolist(), EMAIL_COLUMNS)
        if not email_column:
            raise ValueError("No email column found. Accepted headers include 'email' and 'email address'.")

        name_column = self._resolve_column(frame.columns.tolist(), NAME_COLUMNS)
        company_column = self._resolve_column(frame.columns.tolist(), COMPANY_COLUMNS)

        valid_rows: list[dict[str, str]] = []
        invalid_rows: list[dict[str, str]] = []
        preview_rows: list[dict[str, str]] = []

        for index, row in frame.iterrows():
            email = normalize_email(str(row.get(email_column, "")))
            name = str(row.get(name_column, "")).strip() if name_column else ""
            company = str(row.get(company_column, "")).strip() if company_column else ""
            resolved_name = name or email.split("@")[0].replace(".", " ").title()
            record = {
                "name": resolved_name,
                "company": company,
                "email": email,
                "row_number": str(index + 2),
            }
            if not email:
                record["validation_error"] = "Missing email address"
                invalid_rows.append(record)
            elif not is_valid_email(email):
                record["validation_error"] = "Invalid email format"
                invalid_rows.append(record)
            else:
                record["validation_error"] = ""
                valid_rows.append(record)
            preview_rows.append(record)

        return RecruiterImportPreview(
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            preview_rows=preview_rows,
            source_file=path.name,
        )

    def build_preview_from_emails(self, raw_text: str) -> RecruiterImportPreview:
        emails = []
        seen: set[str] = set()
        for token in re.split(r"[\s,;]+", raw_text):
            email = normalize_email(token)
            if not email or email in seen:
                continue
            seen.add(email)
            parsed = parse_recruiter_identity(email)
            parsed["row_number"] = str(len(emails) + 2)
            if not is_valid_email(email):
                parsed["validation_error"] = "Invalid email format"
            else:
                parsed["validation_error"] = ""
            emails.append(parsed)
        valid_rows = [row for row in emails if not row["validation_error"]]
        invalid_rows = [row for row in emails if row["validation_error"]]
        return RecruiterImportPreview(
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            preview_rows=emails,
            source_file="sample_recruiters.csv",
        )

    def save_parsed_csv(self, destination: Path, recruiter_rows: list[dict[str, str]], source: str = "auto_parser") -> None:
        frame = pd.DataFrame(
            [
                {
                    "recruiter_name": row["name"],
                    "company_name": row["company"],
                    "email": row["email"],
                    "source": source,
                    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                }
                for row in recruiter_rows
            ]
        )
        frame.to_csv(destination, index=False)
