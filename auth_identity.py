"""Local private identity and Dell's normal public-key registration format."""

import base64
import hashlib
import json
import os
from pathlib import Path
import paramiko


def identity_key(state):
    path = Path(state) / "identity-rsa"
    if path.exists():
        return paramiko.RSAKey.from_private_key_file(str(path))
    key = paramiko.RSAKey.generate(3072)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        key.write_private_key(f)
    return key


def public_identity(key, client_id):
    return f"{key.get_name()} {key.get_base64()} {{{client_id}}}"


def fingerprint(key):
    return "SHA256:" + base64.b64encode(
        hashlib.sha256(key.asbytes()).digest()
    ).decode().rstrip("=")


def registered_key(state, host, client_id):
    path = Path(state) / "key-registration.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    if (
        record.get("host") != host
        or record.get("client_id") != client_id
        or not record.get("confirmed")
    ):
        return None
    key = paramiko.RSAKey.from_private_key_file(str(Path(state) / "identity-rsa"))
    if record.get("key_fingerprint") != fingerprint(key):
        raise ValueError("registered private-key identity mismatch")
    return key
