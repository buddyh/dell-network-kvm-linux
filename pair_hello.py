"""Normal PIN authentication and Hello only. No Join, input, or monitor commands.
Run in a local terminal; PIN is entered without echo and is never persisted.
"""

import argparse
import base64
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import time
import uuid
import paramiko
from discovery import field, fields

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"


def pin_password(pin):
    if len(pin) != 6 or not pin.isascii() or not pin.isdecimal():
        raise ValueError("PIN must be exactly six ASCII digits")
    return hashlib.sha256(
        "".join(format(int(d) + 5, "X") for d in pin).encode()
    ).hexdigest()


def save_private(path, data):
    raw = (json.dumps(data, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)


def status(stage, **kw):
    record = {"stage": stage, "time": time.time(), **kw}
    save_private(STATE / "pairing-status.json", record)
    print(stage, flush=True)


def connection(host, port, keys):
    sock = socket.create_connection((host, port), timeout=5)
    t = paramiko.Transport(sock)
    try:
        t.start_client(timeout=5)
        key = t.get_remote_server_key()
        entry = {
            "type": key.get_name(),
            "key": key.get_base64(),
            "fingerprint": "SHA256:"
            + base64.b64encode(hashlib.sha256(key.asbytes()).digest())
            .decode()
            .rstrip("="),
        }
        label = f"{host}:{port}"
        if label in keys and keys[label] != entry:
            raise ValueError(f"Host key changed for {label}")
        if label not in keys:
            keys[label] = entry
            save_private(STATE / "host-keys.json", keys)
            print(f'{label} first-contact host key: {entry["fingerprint"]}', flush=True)
        return t
    except BaseException:
        t.close()
        raise


def recv_exact(channel, n):
    out = bytearray()
    while len(out) < n:
        chunk = channel.recv(n - len(out))
        if not chunk:
            raise EOFError("SSH channel closed mid-frame")
        out.extend(chunk)
    return bytes(out)


def read_frame(channel):
    n = struct.unpack("<I", recv_exact(channel, 4))[0]
    if n > 1024 * 1024:
        raise ValueError("Oversized or unexpected stream frame")
    return recv_exact(channel, n)


def hello(client_id):
    body = field(1, client_id) + field(2, 6)
    payload = field(1, 1) + field(3, 4) + field(6, body)
    return struct.pack("<I", len(payload)) + payload


def decode_reply(body):
    base = fields(body)
    result = {
        "type": base.get(3, [0])[-1],
        "id": base.get(1, [0])[-1],
        "correlation_id": base.get(2, [0])[-1],
    }
    if 7 in base:
        msg = fields(base[7][-1])
        names = {
            1: "cluster_id",
            2: "client_id",
            3: "protocol_major",
            4: "protocol_minor",
            5: "is_active",
            6: "active_ip",
            7: "is_online",
        }
        result["hello_response"] = {
            names[n]: (v[-1].decode() if n in (1, 2, 6) else v[-1])
            for n, v in msg.items()
            if n in names
        }
    if 5 in base:
        err = fields(base[5][-1])
        result["error"] = {
            "code": err.get(1, [0])[-1],
            "message": err.get(2, [b""])[-1].decode(errors="replace"),
        }
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", type=ipaddress.IPv4Address, help="Mac LAN IPv4 address")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--receive", action="store_true", help="join and receive keyboard/mouse input"
    )
    mode.add_argument(
        "--join-probe",
        action="store_true",
        help="join for 15 seconds without injecting input",
    )
    parser.add_argument(
        "--existing-pin",
        action="store_true",
        help="skip the PIN request; use a PIN the Mac is already showing",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    host = str(args.host)
    STATE.mkdir(mode=0o700, exist_ok=True)
    keys = (
        json.loads((STATE / "host-keys.json").read_text())
        if (STATE / "host-keys.json").exists()
        else {}
    )
    identity_path = STATE / "identity.json"
    if identity_path.exists():
        identity = json.loads(identity_path.read_text())
    else:
        identity = {"client_id": hashlib.sha256(uuid.uuid4().bytes).hexdigest()}
        save_private(identity_path, identity)
    transports = []
    try:
        from auth_identity import registered_key

        auth_key = registered_key(STATE, host, identity["client_id"])
        if auth_key is None:
            status(
                ("using_existing_pin" if args.existing_pin else "requesting_mac_pin"),
                target=host,
            )
            t = None if args.existing_pin else connection(host, 5566, keys)
            try:
                try:
                    if t is None:
                        raise paramiko.AuthenticationException("Existing PIN selected")
                    t.auth_password("SKvm_Multiple", "", fallback=False)
                    raise RuntimeError(
                        "Unexpected empty-password authentication success; stopped"
                    )
                except paramiko.AuthenticationException:
                    pass
            finally:
                if t is not None:
                    t.close()
            print(
                "\nEnter the PIN displayed by Dell Network KVM on the Mac.\nMode: "
                + (
                    "receiving client"
                    if args.receive
                    else (
                        "15-second membership probe"
                        if args.join_probe
                        else "Hello only"
                    )
                )
                + "\n",
                flush=True,
            )
            status("waiting_for_pin", target=host)
            while True:
                pin = getpass.getpass(
                    "Mac Dell PIN (six digits, hidden; Enter cancels): "
                )
                if not pin:
                    status("cancelled_before_pin_authentication", target=host)
                    return 0
                try:
                    password = pin_password(pin)
                    break
                except ValueError:
                    print(
                        "Enter the six digits from the Mac. Nothing was sent.",
                        flush=True,
                    )
                finally:
                    del pin
        else:
            status("authenticating_registered_key", target=host)
        channels = {}
        for port in (5566, 5567):
            t = connection(host, port, keys)
            transports.append(t)
            # Exactly one attempt per stream. Stop on failure; do not guess or retry.
            if auth_key is None:
                t.auth_password("SKvm_Multiple", password, fallback=False)
            else:
                t.auth_publickey("SKvm_Multiple", auth_key)
            c = t.open_session(timeout=8)
            c.settimeout(8)
            c.get_pty(term="xterm", width=80, height=24)
            c.invoke_shell()
            channels[port] = c
        if auth_key is None:
            del password
        status("authenticated_both_streams", target=host)
        channels[5566].sendall(hello(identity["client_id"]))
        reply = decode_reply(read_frame(channels[5567]))
        if reply["type"] != 5 or "hello_response" not in reply:
            status("hello_rejected", reply=reply)
            return 1
        status("hello_success", target=host, reply=reply)
        print(json.dumps(reply, indent=2), flush=True)
        if args.join_probe or args.receive:
            if not reply["hello_response"].get("is_active"):
                status("join_skipped_mac_not_active", target=host)
                return 1
            from join_probe import run

            return run(channels, identity, host, receiver_mode=args.receive)
        return 0
    except BaseException as e:
        status("stopped", error_type=type(e).__name__, error=str(e))
        print("Stopped after one attempt; no automatic retries.", flush=True)
        return 1
    finally:
        for t in transports:
            t.close()


if __name__ == "__main__":
    raise SystemExit(main())
