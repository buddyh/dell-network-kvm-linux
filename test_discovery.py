import struct
import unittest
import discovery as d


class DiscoveryTests(unittest.TestCase):
    def test_static_golden_ping(self):
        self.assertEqual(
            d.ping("x").hex(), "cb0a6764c259bdbfa1c462d3090000000a017810011a020806"
        )

    def test_pong_fields(self):
        pong = d.field(1, "mac-id") + d.field(2, "Mac") + d.field(5, 1)
        body = d.field(1, "test") + d.field(2, 2) + d.field(4, pong)
        result = d.decode(d.MAGIC + struct.pack("<I", len(body)) + body)
        self.assertEqual(
            result,
            {
                "report_tag": "test",
                "type": 2,
                "pong": {
                    "client_id": "mac-id",
                    "client_name": "Mac",
                    "is_online": True,
                },
            },
        )

    def test_reject_truncated_or_invalid(self):
        packet = d.ping("x")
        for bad in [b"", packet[:15], packet[:-1], b"X" + packet[1:], packet + b"X"]:
            with self.subTest(data=bad), self.assertRaises(ValueError):
                d.decode(bad)

    def test_malformed_protobuf(self):
        for bad in [b"\x00", b"\x0a\x10x", b"\x08" + b"\x80" * 11, b"\x0f"]:
            with self.subTest(data=bad), self.assertRaises(ValueError):
                d.fields(bad)

    def test_unknown_fields_are_preserved(self):
        self.assertEqual(d.fields(d.field(70, b"abc")), {70: [b"abc"]})


if __name__ == "__main__":
    unittest.main()
