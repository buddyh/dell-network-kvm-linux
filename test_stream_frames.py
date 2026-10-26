import unittest
import protocol as p
from stream_frames import SessionFrames


def compact(body):
    return (0x40000000 | len(body)).to_bytes(4, "little") + body


class StreamTests(unittest.TestCase):
    def test_handoff_then_compact_mouse_and_alive(self):
        wire = (
            p.frame(
                p.command(
                    1,
                    13,
                    setActive={"clusterId": "c", "term": 1, "toClientId": "linux"},
                )
            )
            + compact(b"-12,7")
            + p.frame(p.command(2, 17, alive={}))
        )
        d = SessionFrames("c")
        out = []
        for i in range(0, len(wire), 3):
            out += d.feed(wire[i : i + 3])
        self.assertEqual([x["type"] for x in out], [13, 22, 17])
        self.assertEqual(
            out[1]["mouse"],
            {"clusterId": "c", "type": 1, "dx": -12, "dy": 7, "delta": 0},
        )
        self.assertEqual(d.buffer, b"")

    def test_invalid_and_oversized(self):
        for raw in [
            compact(b"1,bad"),
            compact(b"2147483648,0"),
            (0x80000001).to_bytes(4, "little"),
        ]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                SessionFrames("c").feed(raw)

    def test_zero_and_coalesced_moves(self):
        out = SessionFrames("c").feed(compact(b"0,0") + compact(b"9,-9"))
        self.assertEqual(len(out), 2)
        self.assertEqual(out[1]["mouse"]["dy"], -9)


if __name__ == "__main__":
    unittest.main()
