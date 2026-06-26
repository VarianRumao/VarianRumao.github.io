"""AES-256-GCM + PBKDF2 envelope, byte-compatible with the browser's Web Crypto.

Envelope JSON (what gets committed as data/applications.enc.json):
  { "v":1, "kdf":"PBKDF2-SHA256", "iter":210000,
    "salt": <b64>, "iv": <b64>, "ct": <b64 ciphertext+16-byte GCM tag> }

The tag is appended to the ciphertext, which is what SubtleCrypto.decrypt expects.
"""
import base64
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 210000


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _ub64(s: str) -> bytes:
    return base64.b64decode(s)


def derive_key(passphrase: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)


def encrypt(passphrase: str, plaintext: str) -> dict:
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = derive_key(passphrase, salt)
    ct = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)  # tag appended
    return {
        "v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS,
        "salt": _b64(salt), "iv": _b64(iv), "ct": _b64(ct),
    }


def decrypt(passphrase: str, env: dict) -> str:
    key = derive_key(passphrase, _ub64(env["salt"]), env.get("iter", ITERATIONS))
    pt = AESGCM(key).decrypt(_ub64(env["iv"]), _ub64(env["ct"]), None)
    return pt.decode("utf-8")


def load_existing(path: str, passphrase: str) -> dict:
    """Return the decrypted dataset dict, or an empty one if the file is missing/unreadable."""
    if not os.path.exists(path):
        return {"updatedAt": None, "items": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            env = json.load(f)
        return json.loads(decrypt(passphrase, env))
    except Exception:
        # wrong passphrase or corrupt -> start fresh rather than crash the run
        return {"updatedAt": None, "items": []}
