import unittest
from evdev import ecodes as E
from input_sink import InputSink, KEYMAP


class FakeDevice:
    def __init__(self):
        self.events = []

    def write(self, *event):
        self.events.append(event)

    def syn(self):
        pass

    def close(self):
        pass


class InputTests(unittest.TestCase):
    def test_dell_codes_are_not_evdev_codes(self):
        self.assertEqual(KEYMAP[1], E.KEY_A)
        self.assertEqual(KEYMAP[72], E.KEY_LEFTMETA)
        self.assertEqual(KEYMAP[66], E.KEY_ENTER)

    def test_ignore_inactive_and_release_on_deactivation(self):
        d = FakeDevice()
        s = InputSink(d)
        s.keyboard({"type": 1, "vkCode": 1})
        self.assertEqual(d.events, [])
        s.set_active(True)
        s.keyboard({"type": 1, "vkCode": 1})
        s.set_active(False)
        self.assertEqual(d.events, [(E.EV_KEY, E.KEY_A, 1), (E.EV_KEY, E.KEY_A, 0)])
        self.assertEqual(s.pressed, set())

    def test_mouse_movement_and_buttons(self):
        d = FakeDevice()
        s = InputSink(d)
        s.set_active(True)
        s.mouse({"type": 1, "dx": -3, "dy": 5})
        s.mouse({"type": 2})
        s.close()
        self.assertIn((E.EV_REL, E.REL_X, -3), d.events)
        self.assertIn((E.EV_REL, E.REL_Y, 5), d.events)
        self.assertEqual(
            d.events[-2:], [(E.EV_KEY, E.BTN_LEFT, 1), (E.EV_KEY, E.BTN_LEFT, 0)]
        )

    def test_wheel_accumulates_fine_deltas(self):
        d = FakeDevice()
        s = InputSink(d)
        s.set_active(True)
        for _ in range(3):
            s.mouse({"type": 8, "delta": 40})
        s.mouse({"type": 8, "delta": -240})
        self.assertEqual(
            d.events,
            [(E.EV_REL, E.REL_WHEEL, 1), (E.EV_REL, E.REL_WHEEL, -2)],
        )

    def test_unknown_key_not_injected(self):
        d = FakeDevice()
        s = InputSink(d)
        s.set_active(True)
        s.keyboard({"type": 1, "vkCode": 99999})
        self.assertEqual(d.events, [])
        self.assertEqual(s.unmapped_count, 1)


if __name__ == "__main__":
    unittest.main()
