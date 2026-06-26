"""Run ONCE locally to mint a Gmail refresh token for the ingest job.

Prereqs:
  1. Google Cloud Console -> create a project -> enable "Gmail API".
  2. OAuth consent screen: External, add yourself under "Test users".
  3. Credentials -> Create OAuth client ID -> "Desktop app" -> download the JSON
     and save it next to this script as  client_secret.json
  4. pip install google-auth-oauthlib
  5. python get_gmail_token.py

It prints client_id, client_secret and refresh_token. Put those three into your
GitHub repo secrets (Settings -> Secrets and variables -> Actions) as
GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN.

Scope is gmail.modify (read + apply the Tracker-Processed label). It cannot send
or delete mail.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

print("\n--- put these into GitHub repo secrets ---")
print("GMAIL_CLIENT_ID     =", creds.client_id)
print("GMAIL_CLIENT_SECRET =", creds.client_secret)
print("GMAIL_REFRESH_TOKEN =", creds.refresh_token)
