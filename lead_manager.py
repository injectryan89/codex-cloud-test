"""A small SQLite-backed application for managing sales leads."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


LEAD_STATUSES = ("new", "contacted", "booked", "closed")


class LeadError(ValueError):
    """Base exception for invalid lead operations."""


class DuplicateLeadError(LeadError):
    """Raised when a lead already exists for a normalized phone number."""


class LeadNotFoundError(LeadError):
    """Raised when a requested lead does not exist."""


@dataclass(frozen=True)
class Lead:
    """A stored lead."""

    id: int
    name: str
    phone_number: str
    source: str
    status: str


def normalize_phone_number(phone_number: str) -> str:
    """Return the digits in a phone number for consistent comparisons."""
    normalized = re.sub(r"\D", "", phone_number)
    if not normalized:
        raise LeadError("Phone number must contain at least one digit")
    return normalized


class LeadManager:
    """Create, find, and update leads in a SQLite database."""

    def __init__(self, database: str | Path = "leads.db") -> None:
        self._connection = sqlite3.connect(str(database))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                normalized_phone TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('new', 'contacted', 'booked', 'closed')
                )
            )
            """
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> LeadManager:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def create_lead(
        self,
        name: str,
        phone_number: str,
        source: str,
        status: str = "new",
    ) -> Lead:
        """Create and return a lead, rejecting duplicate phone numbers."""
        name = self._require_text(name, "Name")
        phone_number = self._require_text(phone_number, "Phone number")
        source = self._require_text(source, "Source")
        normalized_phone = normalize_phone_number(phone_number)
        self._validate_status(status)

        try:
            cursor = self._connection.execute(
                """
                INSERT INTO leads
                    (name, phone_number, normalized_phone, source, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, phone_number, normalized_phone, source, status),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            self._connection.rollback()
            if "normalized_phone" in str(error):
                raise DuplicateLeadError(
                    f"A lead with phone number {phone_number!r} already exists"
                ) from error
            raise

        return self.get_lead(cursor.lastrowid)

    def get_lead(self, lead_id: int) -> Lead:
        """Return one lead by ID."""
        row = self._connection.execute(
            """
            SELECT id, name, phone_number, source, status
            FROM leads
            WHERE id = ?
            """,
            (lead_id,),
        ).fetchone()
        if row is None:
            raise LeadNotFoundError(f"Lead {lead_id} does not exist")
        return self._to_lead(row)

    def list_leads(self) -> list[Lead]:
        """Return all leads in creation order."""
        rows = self._connection.execute(
            """
            SELECT id, name, phone_number, source, status
            FROM leads
            ORDER BY id
            """
        ).fetchall()
        return [self._to_lead(row) for row in rows]

    def change_status(self, lead_id: int, status: str) -> Lead:
        """Change a lead to one of the supported statuses and return it."""
        self._validate_status(status)
        cursor = self._connection.execute(
            "UPDATE leads SET status = ? WHERE id = ?",
            (status, lead_id),
        )
        if cursor.rowcount == 0:
            raise LeadNotFoundError(f"Lead {lead_id} does not exist")
        self._connection.commit()
        return self.get_lead(lead_id)

    @staticmethod
    def _require_text(value: str, field_name: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise LeadError(f"{field_name} is required")
        return cleaned

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in LEAD_STATUSES:
            choices = ", ".join(LEAD_STATUSES)
            raise LeadError(f"Status must be one of: {choices}")

    @staticmethod
    def _to_lead(row: sqlite3.Row) -> Lead:
        return Lead(
            id=row["id"],
            name=row["name"],
            phone_number=row["phone_number"],
            source=row["source"],
            status=row["status"],
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="leads.db", help="SQLite database file")
    commands = parser.add_subparsers(dest="command", required=True)

    add_parser = commands.add_parser("add", help="Create a lead")
    add_parser.add_argument("name")
    add_parser.add_argument("phone_number")
    add_parser.add_argument("source")
    add_parser.add_argument("--status", choices=LEAD_STATUSES, default="new")

    commands.add_parser("list", help="List leads")

    status_parser = commands.add_parser("status", help="Change a lead status")
    status_parser.add_argument("lead_id", type=int)
    status_parser.add_argument("status", choices=LEAD_STATUSES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line lead manager."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        with LeadManager(args.database) as manager:
            if args.command == "add":
                result: Lead | list[Lead] = manager.create_lead(
                    args.name,
                    args.phone_number,
                    args.source,
                    args.status,
                )
            elif args.command == "status":
                result = manager.change_status(args.lead_id, args.status)
            else:
                result = manager.list_leads()
    except LeadError as error:
        parser.error(str(error))

    if isinstance(result, list):
        print(json.dumps([asdict(lead) for lead in result], indent=2))
    else:
        print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
