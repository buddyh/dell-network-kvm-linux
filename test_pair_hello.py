import contextlib
import hashlib
import io
import unittest
import pair_hello as p


class FakeChannel:
    def __init__(self, data):
        self.data = data

    def recv(self, n):
        data, self.data = self.data[: min(n, 2)], self.data[min(n, 2) :]
        return data


class PairingTests(unittest.TestCase):
    def test_pin_transform(self):
        self.assertEqual(
            p.pin_password("012345"), hashlib.sha256(b"56789A").hexdigest()
        )
        self.assertEqual(
            p.pin_password("987654"), hashlib.sha256(b"EDCBA9").hexdigest()
        )
        for invalid in ["12345", "1234567", "１２３４５６", "abcdef"]:
            with self.assertRaises(ValueError):
                p.pin_password(invalid)

    def test_arguments(self):
        args = p.parse_args(["192.0.2.1", "--receive", "--existing-pin"])
        self.assertEqual(str(args.host), "192.0.2.1")
        self.assertTrue(args.receive and args.existing_pin)
        self.assertFalse(args.join_probe)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            p.parse_args(["192.0.2.1", "--receive", "--join-probe"])

    def test_hello_wire_bytes(self):
        self.assertEqual(p.hello("x").hex(), "0b0000000801180432050a01781006")

    def test_partial_frame_reads(self):
        self.assertEqual(p.read_frame(FakeChannel(b"\x03\x00\x00\x00abc")), b"abc")
        with self.assertRaises(EOFError):
            p.read_frame(FakeChannel(b"\x03\x00\x00\x00ab"))
        with self.assertRaises(ValueError):
            p.read_frame(FakeChannel(b"\xff\xff\xff\xff"))

    def test_hello_response(self):
        msg = p.field(1, "c") + p.field(2, "mac") + p.field(3, 6)
        body = p.field(3, 5) + p.field(7, msg)
        self.assertEqual(
            p.decode_reply(body)["hello_response"],
            {"cluster_id": "c", "client_id": "mac", "protocol_major": 6},
        )


if __name__ == "__main__":
    unittest.main()
