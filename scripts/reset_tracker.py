"""Reset the tracker: remove Tracker-Processed labels from Gmail + wipe data file.

Run this once via the reset.yml workflow whenever you want to re-classify
everything from scratch with improved extraction logic.
"""
import datetime as dt
import json
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import crypto_util as crypto

if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                if key and not os.environ.get(key):
                    os.environ[key] = value

UTC = dt.timezone.utc
PROCESSED_LABEL = os.environ.get("PROCESSED_LABEL", "Tracker-Processed")
DATA_PATH = os.environ.get("DATA_PATH", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "applications.enc.json"))
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _creds():
    return Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def main():
    passphrase = os.environ["TRACKER_PASSPHRASE"]
    svc = build("gmail", "v1", credentials=_creds(), cache_discovery=False)

    # Find the Tracker-Processed label
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    label_id = next((l["id"] for l in labels if l["name"] == PROCESSED_LABEL), None)

    if not label_id:
        print(f"Label '{PROCESSED_LABEL}' not found — nothing to remove.")
    else:
        removed = 0
        page = None
        while True:
            resp = svc.users().messages().list(
                userId="me", q=f"label:{PROCESSED_LABEL}",
                maxResults=500, pageToken=page).execute()
            msgs = resp.get("messages", [])
            if not msgs:
                break
            for m in msgs:
                svc.users().messages().modify(
                    userId="me", id=m["id"],
                    body={"removeLabelIds": [label_id]}).execute()
                removed += 1
            page = resp.get("nextPageToken")
            if not page:
                break
        print(f"Removed '{PROCESSED_LABEL}' from {removed} messages.")

    # Write an empty encrypted data file
    empty = {"updatedAt": dt.datetime.now(UTC).isoformat().replace('+00:00', 'Z'), "items": []}
    enc = crypto.encrypt(passphrase, json.dumps(empty, ensure_ascii=False))
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(enc, f)
    print(f"Data file cleared: {DATA_PATH}")
    print("Done. Run the ingest workflow next to reprocess everything with clean extraction.")


if __name__ == "__main__":
    main()
