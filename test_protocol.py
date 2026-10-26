import struct
import unittest
import protocol as p
from discovery import field


class ProtocolTests(unittest.TestCase):
    def test_golden_hello(self):
        self.assertEqual(
            p.command(1, 4, hello={"clientId": "x", "protocolMajorVersion": 6}).hex(),
            "0801180432050a01781006",
        )

    def test_signed_mouse(self):
        data = bytes.fromhex("180120feffffffffffffffff01")
        self.assertEqual(p.decode("CommandMouse", data), {"dx": 1, "dy": -2})

    def test_recorded_hello_response(self):
        # Field tags and values from the successful Hello response.
        data = (
            field(1, 16)
            + field(2, 1)
            + field(3, 5)
            + field(7, field(2, "mac") + field(3, 6) + field(5, 1))
        )
        r = p.decode("BaseClusterCommand", data)
        self.assertEqual(
            r["helloResponse"],
            {"clientId": "mac", "protocolMajorVersion": 6, "isActive": True},
        )
        self.assertEqual(r["correlationId"], 1)

    def test_packed_fixed_width(self):
        # Packed fixed-width values are raw little-endian, not varints.
        p.MESSAGES["_PackedTest"] = {
            "fields": [
                {
                    "name": "values",
                    "number": 1,
                    "type": "float",
                    "repeated": True,
                    "packed": True,
                    "specific": None,
                }
            ]
        }
        try:
            data = field(1, struct.pack("<ff", 1.5, -2.0))
            self.assertEqual(p.decode("_PackedTest", data), {"values": [1.5, -2.0]})
        finally:
            del p.MESSAGES["_PackedTest"]

    def test_bad_field_name(self):
        with self.assertRaises(ValueError):
            p.encode("CommandJoin", {"unexpected": True})

    def test_join_no_active_request(self):
        req = p.decode(
            "BaseClusterCommand",
            p.command(
                2,
                6,
                join={
                    "setup": 2,
                    "client": {
                        "clientId": "linux",
                        "os": "Linux",
                        "supportedMonitorCount": 0,
                    },
                    "requestActive": False,
                },
            ),
        )
        self.assertFalse(req["join"]["requestActive"])
        self.assertEqual(req["join"]["client"]["os"], "Linux")


if __name__ == "__main__":
    unittest.main()
