#!/usr/bin/env python3
"""
Bezalel.AI iMessage Sync Agent

Reads iMessage data from the local macOS chat.db, encrypts it,
and syncs it to the Bezalel server. Designed to run as a launchd
agent every 30 minutes.
"""

import argparse
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHAT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"
SYNC_STATE_PATH = Path.home() / ".bezalel_sync_state"
ENV_FILE_PATH = Path.home() / ".bezalel_env"
YEARS_LOOKBACK = 3

# Apple's Core Data epoch: 2001-01-01 00:00:00 UTC
APPLE_EPOCH_OFFSET = 978307200

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("bezalel_sync")

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def load_config():
    """Load configuration from the env file and environment variables."""
    if ENV_FILE_PATH.exists():
        load_dotenv(ENV_FILE_PATH)

    master_key = os.getenv("BEZALEL_MASTER_KEY")
    encryption_key = os.getenv("BEZALEL_ENCRYPTION_KEY")
    server_url = os.getenv("BEZALEL_SERVER_URL", "https://www.danieltaehyunpark.com")

    if not master_key:
        log.error("BEZALEL_MASTER_KEY is not set. Aborting.")
        sys.exit(1)
    if not encryption_key:
        log.error("BEZALEL_ENCRYPTION_KEY is not set. Aborting.")
        sys.exit(1)

    return {
        "master_key": master_key,
        "encryption_key": encryption_key,
        "server_url": server_url.rstrip("/"),
    }


# ---------------------------------------------------------------------------
# Rotating API key management
# ---------------------------------------------------------------------------

_cached_api_key: str | None = None


def fetch_rotating_key(config: dict, force_refresh: bool = False) -> str:
    """
    Retrieve a short-lived rotating API key from the server.
    Caches the key in-memory and refreshes on demand.
    """
    global _cached_api_key

    if _cached_api_key and not force_refresh:
        return _cached_api_key

    url = f"{config['server_url']}/api/imessage/key"
    headers = {"Authorization": f"Bearer {config['master_key']}"}

    log.info("Fetching rotating API key from server...")
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        _cached_api_key = resp.json()["key"]
        log.info("Rotating API key obtained successfully.")
        return _cached_api_key
    except requests.RequestException as exc:
        log.error("Failed to fetch rotating API key: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------


def encrypt_payload(plaintext: bytes, key_hex: str) -> dict:
    """
    Encrypt *plaintext* with AES-256-GCM.

    Parameters
    ----------
    plaintext : bytes
        The data to encrypt.
    key_hex : str
        A 64-character hex string representing the 256-bit key.

    Returns
    -------
    dict with keys ``nonce`` and ``ciphertext``, both hex-encoded strings.
    """
    key = bytes.fromhex(key_hex)
    if len(key) != 32:
        raise ValueError("Encryption key must be 256 bits (64 hex characters).")

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return {
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
    }


# ---------------------------------------------------------------------------
# Sync state persistence
# ---------------------------------------------------------------------------


def read_last_sync_timestamp() -> float | None:
    """Return the Unix timestamp of the last successful sync, or None."""
    if not SYNC_STATE_PATH.exists():
        return None
    try:
        data = json.loads(SYNC_STATE_PATH.read_text())
        return data.get("last_sync_timestamp")
    except (json.JSONDecodeError, OSError):
        return None


def write_last_sync_timestamp(ts: float) -> None:
    """Persist the Unix timestamp of a successful sync."""
    SYNC_STATE_PATH.write_text(json.dumps({"last_sync_timestamp": ts}))


# ---------------------------------------------------------------------------
# macOS Contacts resolution
# ---------------------------------------------------------------------------


def build_contact_map() -> dict[str, str]:
    """
    Build a mapping of phone numbers and emails to display names using
    the macOS Contacts database via AppleScript.

    Returns a dict like {"+15551234567": "Jane Doe", "jane@example.com": "Jane Doe"}.
    """
    contact_map: dict[str, str] = {}

    applescript = """
    use framework "Contacts"
    use scripting additions

    set contactStore to current application's CNContactStore's alloc()'s init()
    set keysToFetch to {current application's CNContactGivenNameKey, ¬
        current application's CNContactFamilyNameKey, ¬
        current application's CNContactPhoneNumbersKey, ¬
        current application's CNContactEmailAddressesKey}
    set fetchRequest to current application's CNContactFetchRequest's alloc()'s initWithKeysToFetch:keysToFetch
    set contactsList to current application's NSMutableArray's alloc()'s init()

    contactStore's enumerateContactsWithFetchRequest:fetchRequest error:(missing value) usingBlock:(void (^)(CNContact *contact, BOOL *stop) {
        contactsList's addObject:contact
    })

    set output to ""
    repeat with c in (contactsList as list)
        set givenName to (c's givenName()) as text
        set familyName to (c's familyName()) as text
        set fullName to givenName & " " & familyName

        set phoneNumbers to c's phoneNumbers() as list
        repeat with pn in phoneNumbers
            set phoneValue to (((pn's value())'s stringValue()) as text)
            set output to output & "PHONE:" & phoneValue & "|" & fullName & linefeed
        end repeat

        set emailAddresses to c's emailAddresses() as list
        repeat with em in emailAddresses
            set emailValue to ((em's value()) as text)
            set output to output & "EMAIL:" & emailValue & "|" & fullName & linefeed
        end repeat
    end repeat

    return output
    """

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.warning(
                "Contacts AppleScript failed (rc=%d): %s",
                result.returncode,
                result.stderr.strip(),
            )
            return contact_map

        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" not in line:
                continue
            identifier, name = line.split("|", 1)
            name = name.strip()
            if identifier.startswith("PHONE:"):
                phone = normalize_phone(identifier[6:])
                if phone:
                    contact_map[phone] = name
            elif identifier.startswith("EMAIL:"):
                email = identifier[6:].strip().lower()
                if email:
                    contact_map[email] = name

    except FileNotFoundError:
        log.warning("osascript not found -- not running on macOS?")
    except subprocess.TimeoutExpired:
        log.warning("Contacts lookup timed out.")
    except Exception as exc:
        log.warning("Contacts lookup failed: %s", exc)

    log.info("Resolved %d contacts.", len(contact_map))
    return contact_map


def normalize_phone(raw: str) -> str | None:
    """Strip a phone string down to digits (with leading +)."""
    digits = "".join(c for c in raw if c.isdigit() or c == "+")
    if not digits:
        return None
    # Ensure US numbers have +1 prefix
    if digits.isdigit() and len(digits) == 10:
        digits = "+1" + digits
    elif digits.isdigit() and len(digits) == 11 and digits.startswith("1"):
        digits = "+" + digits
    return digits


# ---------------------------------------------------------------------------
# chat.db extraction
# ---------------------------------------------------------------------------


def apple_ts_to_unix(apple_ts: int) -> float:
    """
    Convert an Apple Core Data / NSDate timestamp to a Unix timestamp.
    Newer macOS versions store timestamps in nanoseconds; older ones in seconds.
    """
    if apple_ts is None:
        return 0.0
    # If the value is unreasonably large, it is in nanoseconds
    if apple_ts > 1e15:
        apple_ts = apple_ts / 1e9
    return apple_ts + APPLE_EPOCH_OFFSET


def extract_messages(since_timestamp: float | None, full_sync: bool) -> list[dict]:
    """
    Query chat.db for messages, optionally filtering to those sent after
    *since_timestamp* (Unix epoch).

    Returns a list of message dicts.
    """
    if not CHAT_DB_PATH.exists():
        log.error("chat.db not found at %s", CHAT_DB_PATH)
        return []

    # Determine the earliest date we care about (3 years back for full sync)
    if full_sync or since_timestamp is None:
        earliest = datetime.now(timezone.utc) - timedelta(days=365 * YEARS_LOOKBACK)
        since_unix = earliest.timestamp()
        log.info("Full sync: fetching messages since %s", earliest.isoformat())
    else:
        since_unix = since_timestamp
        log.info(
            "Incremental sync: fetching messages since %s",
            datetime.fromtimestamp(since_unix, tz=timezone.utc).isoformat(),
        )

    # Convert Unix timestamp to Apple's epoch for the SQL query
    since_apple = since_unix - APPLE_EPOCH_OFFSET

    query = """
        SELECT
            m.rowid,
            m.guid,
            m.text,
            m.date            AS message_date,
            m.is_from_me,
            m.service,
            h.id              AS handle_id_str,
            c.chat_identifier,
            c.display_name    AS chat_display_name
        FROM message AS m
        LEFT JOIN handle AS h
            ON m.handle_id = h.rowid
        LEFT JOIN chat_message_join AS cmj
            ON m.rowid = cmj.message_id
        LEFT JOIN chat AS c
            ON cmj.chat_id = c.rowid
        WHERE m.date > ?
        ORDER BY m.date ASC
    """

    messages: list[dict] = []

    try:
        # Open the database in read-only mode with a short timeout to handle locks
        conn = sqlite3.connect(
            f"file:{CHAT_DB_PATH}?mode=ro",
            uri=True,
            timeout=10,
        )
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # chat.db may store dates in nanoseconds on newer macOS versions.
        # We need to figure out which scale is used.
        cursor.execute("SELECT date FROM message ORDER BY date DESC LIMIT 1")
        sample_row = cursor.fetchone()
        uses_nanoseconds = False
        if sample_row and sample_row["date"] and sample_row["date"] > 1e15:
            uses_nanoseconds = True

        if uses_nanoseconds:
            since_apple = since_apple * 1e9

        cursor.execute(query, (since_apple,))
        rows = cursor.fetchall()

        for row in rows:
            msg_text = row["text"]
            if msg_text is None:
                continue  # Skip attachment-only messages with no text

            unix_ts = apple_ts_to_unix(row["message_date"])
            messages.append(
                {
                    "guid": row["guid"],
                    "text": msg_text,
                    "timestamp": unix_ts,
                    "iso_date": datetime.fromtimestamp(
                        unix_ts, tz=timezone.utc
                    ).isoformat(),
                    "is_from_me": bool(row["is_from_me"]),
                    "service": row["service"],
                    "handle": row["handle_id_str"],
                    "chat_identifier": row["chat_identifier"],
                    "chat_display_name": row["chat_display_name"],
                }
            )

        conn.close()
        log.info("Extracted %d messages from chat.db.", len(messages))

    except sqlite3.OperationalError as exc:
        if "database is locked" in str(exc).lower():
            log.error(
                "chat.db is locked (Messages app may be writing). "
                "Will retry on next scheduled run."
            )
        else:
            log.error("SQLite error reading chat.db: %s", exc)
    except Exception as exc:
        log.error("Unexpected error reading chat.db: %s", exc)

    return messages


# ---------------------------------------------------------------------------
# Contact enrichment
# ---------------------------------------------------------------------------


def enrich_messages(
    messages: list[dict], contact_map: dict[str, str]
) -> list[dict]:
    """Add a ``contact_name`` field to each message based on the contact map."""
    for msg in messages:
        handle = msg.get("handle") or ""
        normalized = normalize_phone(handle) if handle else None
        name = None

        if normalized:
            name = contact_map.get(normalized)

        # Try the raw handle as an email lookup
        if not name and handle:
            name = contact_map.get(handle.lower())

        msg["contact_name"] = name  # None if unresolved

    return messages


# ---------------------------------------------------------------------------
# Server upload
# ---------------------------------------------------------------------------


def upload_to_server(
    messages: list[dict], config: dict, retry_auth: bool = True
) -> bool:
    """
    Encrypt and upload messages to the Bezalel server.

    Returns True on success, False otherwise.
    """
    if not messages:
        log.info("No new messages to upload.")
        return True

    payload_json = json.dumps(messages, ensure_ascii=False).encode("utf-8")
    encrypted = encrypt_payload(payload_json, config["encryption_key"])

    api_key = fetch_rotating_key(config)
    url = f"{config['server_url']}/api/imessage/sync"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "nonce": encrypted["nonce"],
        "ciphertext": encrypted["ciphertext"],
        "message_count": len(messages),
        "sync_timestamp": time.time(),
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=60)

        # Handle expired rotating key
        if resp.status_code == 403 and retry_auth:
            log.warning("Server returned 403. Refreshing rotating API key...")
            _new_key = fetch_rotating_key(config, force_refresh=True)
            return upload_to_server(messages, config, retry_auth=False)

        resp.raise_for_status()
        log.info(
            "Successfully uploaded %d messages to server.", len(messages)
        )
        return True

    except requests.RequestException as exc:
        log.error("Upload failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bezalel.AI iMessage Sync Agent"
    )
    parser.add_argument(
        "--full-sync",
        action="store_true",
        help="Ignore last sync timestamp and sync all messages from the past 3 years.",
    )
    args = parser.parse_args()

    log.info("=== Bezalel iMessage Sync starting ===")

    config = load_config()

    # Resolve contacts
    contact_map = build_contact_map()

    # Determine sync window
    last_sync = read_last_sync_timestamp()
    if args.full_sync:
        log.info("--full-sync flag set. Performing full sync.")

    # Extract messages
    messages = extract_messages(last_sync, full_sync=args.full_sync)
    if not messages:
        log.info("No new messages found. Exiting.")
        return

    # Enrich with contact names
    messages = enrich_messages(messages, contact_map)

    # Upload
    sync_start = time.time()
    success = upload_to_server(messages, config)

    if success:
        # Use the timestamp of the newest message as the watermark
        newest_ts = max(m["timestamp"] for m in messages)
        write_last_sync_timestamp(newest_ts)
        log.info(
            "Sync completed successfully in %.1f seconds. %d messages synced.",
            time.time() - sync_start,
            len(messages),
        )
    else:
        log.error("Sync failed. Will retry on next scheduled run.")

    log.info("=== Bezalel iMessage Sync finished ===")


if __name__ == "__main__":
    main()
