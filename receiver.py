"""Experimental receiving-only Dell KVM session for one Hyprland display.
Physical keyboard/mouse stay on the Mac. No clipboard, files or display switching.
"""

import json
import socket
import subprocess
import time
from evdev import ecodes as E
import protocol
from stream_frames import SessionFrames
from auth_identity import identity_key, public_identity, fingerprint, registered_key
from input_sink import InputSink, KEYMAP
from pair_hello import STATE, save_private, status


def hypr(*args):
    return subprocess.run(
        ["hyprctl", *args], capture_output=True, text=True, timeout=2, check=True
    ).stdout


def cursor_pos():
    """Current cursor position, or None if the compositor query fails."""
    try:
        return json.loads(hypr("cursorpos", "-j"))
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def move_cursor(x, y):
    # Lua-configured Hyprland only accepts the eval form; hyprlang configs
    # still use the classic dispatcher.
    try:
        hypr("eval", f"hl.dispatch(hl.dsp.cursor.move({{ x = {x}, y = {y} }}))")
    except subprocess.CalledProcessError:
        hypr("dispatch", "movecursor", str(x), str(y))


def run(channels, identity, host, response, duration=600):
    # Dell swaps channel roles after JoinResponse: read5566, write5567.
    send, receive = channels[5567], channels[5566]
    local_id = identity["client_id"]
    mac_id = response["clientId"]
    cluster_id = response["clusterId"]
    state = response["clusterState"]
    data = response.get("clusterData", {})
    active_id = state.get("activeClientId")
    term = state.get("activeTerm", 0)
    monitors = [m for m in json.loads(hypr("monitors", "-j")) if not m.get("disabled")]
    if len(monitors) != 1:
        raise ValueError("receiver currently requires one active Linux monitor")
    monitor = monitors[0]
    width = monitor["width"] / monitor["scale"]
    height = monitor["height"] / monitor["scale"]
    ox, oy = monitor["x"], monitor["y"]
    stats = {
        "keyboard_events": 0,
        "mouse_events": 0,
        "handoffs_to_linux": 0,
        "returns_to_mac": 0,
        "unmapped_keys": 0,
    }
    next_id = 100
    decoder = SessionFrames(cluster_id)
    last_handoff = 0
    last_position_check = 0
    last_report = 0
    last_alive = 0
    stop = False
    sink = InputSink().open()

    def send_command(kind, **body):
        nonlocal next_id
        send.sendall(protocol.frame(protocol.command(next_id, kind, **body)))
        next_id += 1

    def return_to_mac(reason=3):
        nonlocal term, active_id, last_handoff
        arrangement = data.get("clientArrangementArray", [mac_id, local_id])
        # Infer the neighboring Mac side from DDPM's current arrangement.
        mac_left = (
            arrangement.index(mac_id) < arrangement.index(local_id)
            if mac_id in arrangement and local_id in arrangement
            else True
        )
        pos = cursor_pos()
        y = max(0, min(1, (pos["y"] - oy) / height)) if pos else 0.5
        send_command(
            13,
            setActive={
                "clusterId": cluster_id,
                "fromClientId": local_id,
                "toClientId": mac_id,
                "reason": reason,
                "startPercentX": 1.0 if mac_left else 0.0,
                "startPercentY": y,
                "term": term,
                "isSmoothMouse": False,
            },
        )
        term += 1
        active_id = mac_id
        sink.set_active(False)
        last_handoff = time.monotonic()
        stats["returns_to_mac"] += 1

    def report(stage):
        stats["unmapped_keys"] = sink.unmapped_count
        status(
            stage,
            target=host,
            active="linux" if active_id == local_id else "mac",
            counts=stats.copy(),
        )

    # Register only our public identity through the authenticated KVM stream.
    # This is Dell's SshCopyId operation, with no peer-wide key scan or relay.
    # Skip it once registration is confirmed so the Mac does not collect duplicates.
    local_key = identity_key(STATE)
    registration_id = None
    if registered_key(STATE, host, local_id) is None:
        registration_id = next_id
        send_command(
            27,
            sshCopyId={
                "sourceIdentities": public_identity(local_key, local_id),
                "sourceClientId": local_id,
                "requestRelay": False,
            },
        )
    receive.settimeout(0.1)
    end = time.monotonic() + duration
    report("receiver_ready")
    print(
        "Receiver ready: use DDPM to arrange this Linux client beside the Mac, then cross the pointer.\nCtrl+Alt+Escape returns control to the Mac. Session ends automatically in 10 minutes.\nNo keystrokes, mouse coordinates, clipboard contents or files are logged.",
        flush=True,
    )
    try:
        while time.monotonic() < end and not stop:
            try:
                chunk = receive.recv(65536)
                if not chunk:
                    break
                commands = decoder.feed(chunk)
            except socket.timeout:
                commands = []
            for cmd in commands:
                kind = cmd.get("type", 0)
                if (
                    kind == 28
                    and registration_id is not None
                    and cmd.get("correlationId") == registration_id
                ):
                    save_private(
                        STATE / "key-registration.json",
                        {
                            "host": host,
                            "client_id": local_id,
                            "key_fingerprint": fingerprint(local_key),
                            "confirmed": True,
                        },
                    )
                    report("persistent_pairing_registered")
                elif kind == 17:
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
                elif kind in (9, 36, 35):
                    update = cmd.get(
                        {9: "syncFull", 36: "syncState", 35: "syncData"}[kind], {}
                    )
                    if update.get("clusterId") != cluster_id:
                        continue
                    if "clusterData" in update:
                        data = update["clusterData"]
                    if "clusterState" in update:
                        state = update["clusterState"]
                        term = max(term, state.get("activeTerm", 0))
                        active_id = state.get("activeClientId", active_id)
                        sink.set_active(active_id == local_id)
                elif kind == 13:
                    event = cmd.get("setActive", {})
                    if (
                        event.get("clusterId") != cluster_id
                        or event.get("term", 0) < term
                    ):
                        continue
                    term = max(term, event.get("term", 0)) + 1
                    active_id = event.get("toClientId")
                    sink.set_active(active_id == local_id)
                    last_handoff = time.monotonic()
                    if active_id == local_id:
                        x = ox + (
                            max(8, width * 0.02)
                            if event.get("startPercentX", 0) <= 0
                            else width - max(8, width * 0.02)
                        )
                        y = oy + max(
                            2, min(height - 2, event.get("startPercentY", 0.5) * height)
                        )
                        move_cursor(int(x), int(y))
                        stats["handoffs_to_linux"] += 1
                    report("control_changed")
                elif kind == 21:
                    event = cmd.get("keyboard", {})
                    if event.get("clusterId") != cluster_id:
                        continue
                    code = KEYMAP.get(event.get("vkCode"))
                    ctrl = bool(sink.pressed & {E.KEY_LEFTCTRL, E.KEY_RIGHTCTRL})
                    alt = bool(sink.pressed & {E.KEY_LEFTALT, E.KEY_RIGHTALT})
                    if (
                        sink.active
                        and event.get("type") == 1
                        and code == E.KEY_ESC
                        and ctrl
                        and alt
                    ):
                        return_to_mac(reason=1)
                        report("emergency_return")
                        continue
                    sink.keyboard(event)
                    stats["keyboard_events"] = sink.event_count - stats["mouse_events"]
                elif kind == 22:
                    event = cmd.get("mouse", {})
                    if event.get("clusterId") != cluster_id:
                        continue
                    before = sink.event_count
                    sink.mouse(event)
                    stats["mouse_events"] += sink.event_count - before
                elif kind == 19:
                    event = cmd.get("disconnect", {})
                    if event.get("disconnectClientId") in (local_id, mac_id):
                        stop = True
                        break
            now = time.monotonic()
            if now - last_alive > 3:
                last_alive = now
                send_command(17, alive={})
            if (
                sink.active
                and now - last_handoff > 0.7
                and now - last_position_check > 0.1
            ):
                last_position_check = now
                pos = cursor_pos()
                arrangement = data.get("clientArrangementArray", [mac_id, local_id])
                mac_left = (
                    arrangement.index(mac_id) < arrangement.index(local_id)
                    if mac_id in arrangement and local_id in arrangement
                    else True
                )
                if pos and (
                    (mac_left and pos["x"] <= ox + 1)
                    or (not mac_left and pos["x"] >= ox + width - 2)
                ):
                    return_to_mac()
                    report("returned_at_boundary")
            if now - last_report > 5:
                last_report = now
                report("receiver_running")
    finally:
        if active_id == local_id:
            try:
                return_to_mac(reason=2)
            except Exception:
                pass
        sink.close()
        try:
            send_command(20, leave={"clusterId": cluster_id, "leaveClientId": local_id})
        except (OSError, EOFError):
            pass
        finally:
            report("receiver_stopped")
    return 0
