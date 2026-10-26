"""Bounded cluster membership test. No input, clipboard or display commands."""

import json
from pathlib import Path
import socket
import time
import protocol
from pair_hello import read_frame, status, save_private, STATE


def run(channels, identity, host, duration=15, receiver_mode=False):
    local_ip = channels[5566].get_transport().sock.getsockname()[0]
    client = {
        "clientId": identity["client_id"],
        "systemClientId": identity["client_id"],
        "clientName": socket.gethostname(),
        "ipAddress": local_ip,
        "os": "Linux",
        "protocolMajorVersion": 6,
        "protocolMinorVersion": 0,
        "monitorAmount": 1,
        "isOnline": True,
        "supportedMonitorCount": 0,
        "isDdcciConnected": False,
        "autoConnectFeature": False,
        "contentTransferFeature": False,
        "isSmoothMouseEnabled": False,
        "clientFlag": {"isSystemMode": False, "isLockScreen": False},
    }
    send, receive = channels[5566], channels[5567]
    request = protocol.command(
        2, 6, join={"setup": 4, "client": client, "requestActive": False}
    )
    send.sendall(protocol.frame(request))
    message = protocol.decode("BaseClusterCommand", read_frame(receive))
    if message.get("type") != 7:
        status("join_rejected", reply=message)
        return 1
    response = message.get("joinResponse", {})
    cluster_id = response.get("clusterId", "")
    state = response.get("clusterState", {})
    # Persist topology, not key or mouse events.
    save_private(STATE / "join-response.json", message)
    status(
        "join_success",
        target=host,
        cluster_id=cluster_id,
        active_client_id=state.get("activeClientId"),
        duration_seconds=duration,
    )
    if receiver_mode:
        from receiver import run as receive_session

        return receive_session(channels, identity, host, response)
    # Established RemoteConnection roles are the reverse of the handshake roles.
    send, receive = channels[5567], channels[5566]
    print(
        "Membership test runs for 15 seconds. Keep Mac pointer near the center. No input events are delivered.",
        flush=True,
    )
    end = time.monotonic() + duration
    receive.settimeout(0.5)
    buffer = bytearray()
    counts = {}
    next_id = 3
    try:
        while time.monotonic() < end:
            try:
                chunk = receive.recv(65536)
                if not chunk:
                    break
                buffer.extend(chunk)
            except socket.timeout:
                continue
            while len(buffer) >= 4:
                n = int.from_bytes(buffer[:4], "little")
                if n > 1024 * 1024:
                    raise ValueError("unexpected stream header")
                if len(buffer) < n + 4:
                    break
                body = bytes(buffer[4 : n + 4])
                del buffer[: n + 4]
                cmd = protocol.decode("BaseClusterCommand", body)
                kind = cmd.get("type", 0)
                counts[str(kind)] = counts.get(str(kind), 0) + 1
                # Alive requests receive explicit Success in the inspected native handler.
                # Sync and active-control messages are notifications; do not emit extra acknowledgements.
                if kind == 17:
                    reply = protocol.encode(
                        "BaseClusterCommand",
                        {
                            "id_p": next_id,
                            "correlationId": cmd.get("id_p", 0),
                            "type": 2,
                            "success": {},
                        },
                    )
                    next_id += 1
                    send.sendall(protocol.frame(reply))
    finally:
        if cluster_id:
            leave = protocol.command(
                next_id,
                20,
                leave={"clusterId": cluster_id, "leaveClientId": identity["client_id"]},
            )
            send.sendall(protocol.frame(leave))
        status("join_probe_finished", target=host, message_type_counts=counts)
    return 0
