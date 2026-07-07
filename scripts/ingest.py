"""Free job-tracker ingest. Runs in GitHub Actions on a schedule.

Flow (no AWS, no billing):
  1. Build Gmail creds from GitHub Secrets (refresh token).
  2. Pull messages matching GMAIL_QUERY that are NOT yet labelled Tracker-Processed.
  3. Classify each with regex rules (classify.py).
  4. Decrypt the existing dataset, upsert each application. Status only ever moves
     UP the priority ladder, so a stray later email can't bury an Interview.
  5. Label each message Tracker-Processed so it's never counted twice.
  6. Re-encrypt the dataset and write data/applications.enc.json.

Required env (set as GitHub Secrets or in local .env file):
  GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, TRACKER_PASSPHRASE
Optional env:
  GMAIL_QUERY, PROCESSED_LABEL, DATA_PATH
"""
import datetime as dt
import json
import os
import re

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import classify as C
import crypto_util as crypto

# Load from .env file if it exists (for local testing)
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                if key and not os.environ.get(key):
                    os.environ[key] = value

# Use timezone-aware UTC for timestamp generation
UTC = dt.timezone.utc

# Spam/ad patterns to skip - marketing, recruiting spam, salary surveys, etc.
SPAM_PATTERNS = [
    r"recruit.*for.*fee|recruitment fee|commission|contingency",
    r"salary survey|market report|compensation report",
    r"job posting.*service|recruiting service|job board",
    r"sponsored|promote your (jobs|company|products)",
    r"hire talent|hiring platform|recruitment platform",
    r"we are hiring.*contact us|reach out.*hiring",
    r"bulk recruiting|mass application",
    r"automated job posting",
]

GMAIL_QUERY = os.environ.get(
    "GMAIL_QUERY",
    'newer_than:6m ('
    'subject:application OR subject:applied OR subject:apply OR '
    'subject:interview OR subject:"thank you" OR '
    '"thank you for applying" OR "thanks for applying" OR '
    '"received your application" OR "your application was" OR '
    '"application was sent" OR "application submission" OR '
    'interview OR "regret to inform" OR "offer of employment" OR '
    '"job application" OR "position of" OR '
    'from:linkedin.com OR from:indeed.com OR from:seek.com OR '
    'from:glassdoor.com OR from:ziprecruiter.com OR from:angellist.com OR '
    'from:workable.com OR from:lever.co OR from:greenhouse.io OR '
    '"linkedin careers" OR "indeed jobs" OR "glassdoor" OR "ziprecruiter" OR '
    '"welcome to apply" OR "apply now" OR "job details" OR '
    '"application status" OR "career opportunity"'
    ') -in:spam -label:promotions'
)
PROCESSED_LABEL = os.environ.get("PROCESSED_LABEL", "Tracker-Processed")
DATA_PATH = os.environ.get("DATA_PATH", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "applications.enc.json"))

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "unknown"


def _creds():
    return Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def _ensure_label(svc):
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    for l in labels:
        if l["name"] == PROCESSED_LABEL:
            return l["id"]
    created = svc.users().labels().create(
        userId="me", body={"name": PROCESSED_LABEL,
                            "labelListVisibility": "labelShow",
                            "messageListVisibility": "show"}).execute()
    return created["id"]


def _header(payload, name):
    for h in payload.get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _index(items):
    """Map (account, normalized company#role) -> item for fast upsert."""
    return {(it.get("account"), it.get("key")): it for it in items}


def _is_spam(sender, subject, snippet):
    """Check if email looks like spam/ads/recruiting marketing."""
    text = f"{sender} {subject} {snippet}".lower()
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, text, re.I):
            return True
    return False


def _upsert(idx, items, account, info, msg_date, thread_id):
    key = f"{_norm(info['company'])}#{_norm(info['role'])}"
    now = dt.datetime.now(UTC).isoformat().replace('+00:00', 'Z')
    existing = idx.get((account, key))

    if existing:
        cur = existing.get("status", "Unknown")
        new_status = info["status"]
        if C.STATUS_PRIORITY.get(new_status, 0) > C.STATUS_PRIORITY.get(cur, 0):
            cur = new_status
        threads = set(existing.get("threadIds", []))
        threads.add(thread_id)
        existing.update({
            "status": cur,
            "lastUpdated": now,
            "lastEmailDate": max(existing.get("lastEmailDate", ""), msg_date),
            "threadIds": sorted(threads),
            "replied": "Yes" if cur in ("Interview", "Rejected", "Offer") else existing.get("replied", "No"),
        })
    else:
        item = {
            "account": account, "key": key,
            "company": info["company"], "role": info["role"],
            "source": info["source"], "status": info["status"],
            "replied": "Yes" if info["status"] in ("Interview", "Rejected", "Offer") else "No",
            "firstSeen": now, "lastUpdated": now, "lastEmailDate": msg_date,
            "threadIds": [thread_id],
        }
        items.append(item)
        idx[(account, key)] = item


def main():
    passphrase = os.environ["TRACKER_PASSPHRASE"]
    dataset = crypto.load_existing(DATA_PATH, passphrase)
    items = dataset.get("items", [])
    idx = _index(items)

    svc = build("gmail", "v1", credentials=_creds(), cache_discovery=False)
    account = svc.users().getProfile(userId="me").execute()["emailAddress"]
    label_id = _ensure_label(svc)

    q = f"{GMAIL_QUERY} -label:{PROCESSED_LABEL}"
    processed, upserted = 0, 0
    page = None
    while True:
        resp = svc.users().messages().list(
            userId="me", q=q, maxResults=100, pageToken=page).execute()
        for m in resp.get("messages", []):
            full = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]).execute()
            payload = full.get("payload", {})
            sender = _header(payload, "From")
            subject = _header(payload, "Subject")
            snippet = full.get("snippet", "")
            ts = int(full.get("internalDate", "0")) / 1000
            msg_date = dt.datetime.fromtimestamp(ts, tz=UTC).date().isoformat() if ts else ""

            # skip non-application emails first (LinkedIn alerts, personal messages, flights, etc.)
            if C.is_junk_email(sender, subject, snippet):
                svc.users().messages().modify(
                    userId="me", id=m["id"], body={"addLabelIds": [label_id]}).execute()
                continue

            info = C.classify_with_rules(sender, subject, snippet)

            # skip spam/ads/recruiting marketing, but still mark it
            if _is_spam(sender, subject, snippet):
                svc.users().messages().modify(
                    userId="me", id=m["id"], body={"addLabelIds": [label_id]}).execute()
                continue

            # skip noise that isn't really an application touch, but still mark it
            if info["status"] == "Unknown" and info["company"] == "Unknown":
                svc.users().messages().modify(
                    userId="me", id=m["id"], body={"addLabelIds": [label_id]}).execute()
                continue

            _upsert(idx, items, account, info, msg_date, full.get("threadId", m["id"]))
            upserted += 1
            svc.users().messages().modify(
                userId="me", id=m["id"], body={"addLabelIds": [label_id]}).execute()
            processed += 1

        page = resp.get("nextPageToken")
        if not page:
            break

    dataset = {"updatedAt": dt.datetime.now(UTC).isoformat().replace('+00:00', 'Z'), "items": items}
    env = crypto.encrypt(passphrase, json.dumps(dataset, ensure_ascii=False))
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(env, f)

    print(json.dumps({"account": account, "processed": processed,
                      "upserted": upserted, "total": len(items)}))


if __name__ == "__main__":
    main()
