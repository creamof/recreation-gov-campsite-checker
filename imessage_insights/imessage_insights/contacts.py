"""Best-effort mapping of phone/email handles to contact names.

Reads the local AddressBook SQLite databases. This is entirely optional — if the
databases can't be read, handles are shown as-is (phone number / email).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from . import config


def _normalize_phone(value: str) -> str:
    """Reduce a phone number to its trailing 10 digits for loose matching."""
    digits = re.sub(r"\D", "", value)
    return digits[-10:] if len(digits) >= 10 else digits


def load_contacts() -> dict[str, str]:
    """Return a mapping of handle (phone/email) -> display name.

    Phone numbers are also indexed by their last-10-digits form so that
    differently formatted numbers still resolve.
    """
    mapping: dict[str, str] = {}
    root = config.ADDRESSBOOK_GLOB
    if not root.exists():
        return mapping

    for db_path in root.glob("*/AddressBook-v22.abcddb"):
        try:
            uri = f"file:{db_path}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True)
        except sqlite3.Error:
            continue
        try:
            _load_from(conn, mapping)
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    return mapping


def _full_name(first: str | None, last: str | None, org: str | None) -> str | None:
    name = " ".join(p for p in (first, last) if p).strip()
    return name or (org or None)


def _load_from(conn: sqlite3.Connection, mapping: dict[str, str]) -> None:
    cur = conn.cursor()
    # Phone numbers
    cur.execute(
        """
        SELECT r.ZFIRSTNAME, r.ZLASTNAME, r.ZORGANIZATION, p.ZFULLNUMBER
        FROM ZABCDPHONENUMBER p
        JOIN ZABCDRECORD r ON p.ZOWNER = r.Z_PK
        WHERE p.ZFULLNUMBER IS NOT NULL
        """
    )
    for first, last, org, number in cur.fetchall():
        name = _full_name(first, last, org)
        if not name:
            continue
        mapping.setdefault(number, name)
        mapping.setdefault(_normalize_phone(number), name)

    # Email addresses
    cur.execute(
        """
        SELECT r.ZFIRSTNAME, r.ZLASTNAME, r.ZORGANIZATION, e.ZADDRESS
        FROM ZABCDEMAILADDRESS e
        JOIN ZABCDRECORD r ON e.ZOWNER = r.Z_PK
        WHERE e.ZADDRESS IS NOT NULL
        """
    )
    for first, last, org, address in cur.fetchall():
        name = _full_name(first, last, org)
        if name:
            mapping.setdefault(address.lower(), name)


def resolve(handle: str, contacts: dict[str, str]) -> str:
    """Resolve a handle to a name, falling back to the handle itself."""
    if not handle:
        return "Unknown"
    if handle in contacts:
        return contacts[handle]
    if "@" in handle:
        return contacts.get(handle.lower(), handle)
    key = _normalize_phone(handle)
    return contacts.get(key, handle)
