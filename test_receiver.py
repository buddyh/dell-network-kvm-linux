import contextlib
import io
import json
import subprocess
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from evdev import ecodes as E
import receiver as r
import protocol as p
from input_sink import InputSink
from test_input_sink import FakeDevice
from test_stream_frames import compact


class Sink(InputSink):
    def __init__(self):
        super().__init__(FakeDevice())
        self.original_device = self.device

    def open(self):
        return self


class Send:
    def __init__(self):
        self.sent = []

    def sendall(self, data):
        self.sent.append(p.decode("BaseClusterCommand", data[4:]))


class Receive:
    def __init__(self, data):
        self.data = data

    def settimeout(self, n):
        pass

    def recv(self, n):
        data, self.data = self.data, b""
        return data


class CursorTests(unittest.TestCase):
    def test_move_cursor_falls_back_to_dispatch(self):
        calls = []

        def hypr(*args):
            calls.append(args)
            if args[0] == "eval":
                raise subprocess.CalledProcessError(1, "hyprctl")
            return "ok"

        with patch.object(r, "hypr", side_effect=hypr):
            r.move_cursor(10, 20)
        self.assertEqual(calls[-1], ("dispatch", "movecursor", "10", "20"))

    def test_cursor_pos_failure_is_none(self):
        with patch.object(
            r, "hypr", side_effect=subprocess.TimeoutExpired("hyprctl", 2)
        ):
            self.assertIsNone(r.cursor_pos())


class ReceiverTests(unittest.TestCase):
    def test_active_input_release_keepalive_and_leave(self):
        identity = {"client_id": "linux"}
        response = {
            "clientId": "mac",
            "clusterId": "cluster",
            "clusterState": {"activeClientId": "mac", "activeTerm": 1},
            "clusterData": {"clientArrangementArray": ["mac", "linux"]},
        }

        def active(term, target):
            return p.command(
                10,
                13,
                setActive={
                    "clusterId": "cluster",
                    "term": term,
                    "toClientId": target,
                    "startPercentX": 0.0,
                    "startPercentY": 0.5,
                },
            )

        data = b"".join(
            p.frame(x)
            for x in [
                active(1, "linux"),
                p.command(
                    11, 21, keyboard={"clusterId": "cluster", "type": 1, "vkCode": 1}
                ),
                active(2, "mac"),
                p.command(12, 17, alive={}),
            ]
        )
        # Regression: native compact movement immediately follows handoff.
        first = p.frame(active(1, "linux"))
        data = p.frame(
            p.encode(
                "BaseClusterCommand",
                {"id_p": 50, "correlationId": 100, "type": 28, "sshCopyIdResponse": {}},
            )
        ) + data.replace(first, first + compact(b"-3,5"), 1)
        send = Send()
        receive = Receive(data)
        sink = Sink()
        statuses = []
        monitor = {"width": 1920, "height": 1080, "scale": 1, "x": 0, "y": 0}

        def hypr(*args):
            return json.dumps([monitor]) if args[0] == "monitors" else "{}"

        with tempfile.TemporaryDirectory() as state_dir, patch.object(
            r, "STATE", Path(state_dir)
        ), patch.object(r, "InputSink", return_value=sink), patch.object(
            r, "hypr", side_effect=hypr
        ), patch.object(
            r, "status", side_effect=lambda *a, **k: statuses.append((a, k))
        ), contextlib.redirect_stdout(
            io.StringIO()
        ):
            self.assertEqual(
                r.run(
                    {5566: receive, 5567: send},
                    identity,
                    "127.0.0.1",
                    response,
                    duration=1,
                ),
                0,
            )
            registration = json.loads(
                (Path(state_dir) / "key-registration.json").read_text()
            )
            self.assertTrue(registration["confirmed"])
            self.assertEqual(registration["client_id"], "linux")
        self.assertIn((E.EV_REL, E.REL_X, -3), sink.original_device.events)
        self.assertIn((E.EV_KEY, E.KEY_A, 1), sink.original_device.events)
        self.assertIn((E.EV_KEY, E.KEY_A, 0), sink.original_device.events)
        self.assertFalse(sink.active)
        self.assertTrue(
            any(x.get("correlationId") == 12 and x["type"] == 2 for x in send.sent)
        )
        self.assertEqual(
            send.sent[-1]["leave"], {"clusterId": "cluster", "leaveClientId": "linux"}
        )
        # No keystroke contents in persisted status callbacks.
        self.assertNotIn("vkCode", str(statuses))

    def test_registered_key_skips_copy_id(self):
        response = {
            "clientId": "mac",
            "clusterId": "cluster",
            "clusterState": {"activeClientId": "mac", "activeTerm": 1},
        }
        send = Send()
        monitor = {"width": 1920, "height": 1080, "scale": 1, "x": 0, "y": 0}
        with tempfile.TemporaryDirectory() as state_dir, patch.object(
            r, "STATE", Path(state_dir)
        ), patch.object(r, "InputSink", return_value=Sink()), patch.object(
            r, "hypr", return_value=json.dumps([monitor])
        ), patch.object(
            r, "registered_key", return_value=object()
        ), patch.object(
            r, "status"
        ), contextlib.redirect_stdout(
            io.StringIO()
        ):
            r.run(
                {5566: Receive(b""), 5567: send},
                {"client_id": "linux"},
                "127.0.0.1",
                response,
                duration=1,
            )
        self.assertFalse(any(x["type"] == 27 for x in send.sent))


if __name__ == "__main__":
    unittest.main()
