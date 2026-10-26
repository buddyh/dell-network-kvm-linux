"""Dell VirtualKey -> Linux uinput adapter. Instantiation alone creates no device.
The explicit open() method requires write access to /dev/uinput.
"""

from evdev import UInput, ecodes as E
from protocol import SCHEMA

SPECIAL = {
    "Equal": "EQUAL",
    "Minus": "MINUS",
    "RightBracket": "RIGHTBRACE",
    "LeftBracket": "LEFTBRACE",
    "Quote": "APOSTROPHE",
    "Semicolon": "SEMICOLON",
    "Backslash": "BACKSLASH",
    "Comma": "COMMA",
    "Slash": "SLASH",
    "Period": "DOT",
    "Grave": "GRAVE",
    "KeypadDecimal": "KPDOT",
    "KeypadMultiply": "KPASTERISK",
    "KeypadPlus": "KPPLUS",
    "KeypadClear": "NUMLOCK",
    "KeypadDivide": "KPSLASH",
    "KeypadEnter": "KPENTER",
    "KeypadMinus": "KPMINUS",
    "KeypadEquals": "KPEQUAL",
    "Return": "ENTER",
    "Tab": "TAB",
    "Space": "SPACE",
    "BackwardDelete": "BACKSPACE",
    "Backspace": "BACKSPACE",
    "Escape": "ESC",
    "CapsLock": "CAPSLOCK",
    "LeftCommand": "LEFTMETA",
    "RightCommand": "RIGHTMETA",
    "LeftWin": "LEFTMETA",
    "RightWin": "RIGHTMETA",
    "LeftShift": "LEFTSHIFT",
    "RightShift": "RIGHTSHIFT",
    "LeftOption": "LEFTALT",
    "RightOption": "RIGHTALT",
    "LeftControl": "LEFTCTRL",
    "RightControl": "RIGHTCTRL",
    "Home": "HOME",
    "End": "END",
    "PageUp": "PAGEUP",
    "PageDown": "PAGEDOWN",
    "ForwardDelete": "DELETE",
    "LeftArrow": "LEFT",
    "RightArrow": "RIGHT",
    "DownArrow": "DOWN",
    "UpArrow": "UP",
    "NumLock": "NUMLOCK",
    "Apps": "COMPOSE",
    "Insert": "INSERT",
    "PrintScreen": "SYSRQ",
    "Sleep": "SLEEP",
    "VolumeMute": "MUTE",
    "VolumeDown": "VOLUMEDOWN",
    "VolumeUp": "VOLUMEUP",
    "MediaNextTrack": "NEXTSONG",
    "MediaPreviousTrack": "PREVIOUSSONG",
    "MediaStop": "STOPCD",
    "MediaPlayPause": "PLAYPAUSE",
    "BrightnessDown": "BRIGHTNESSDOWN",
    "BrightnessUp": "BRIGHTNESSUP",
}


def keymap():
    result = {}
    for item in SCHEMA["enums"]["VirtualKey_EnumDescriptor"]:
        name = item["name"].removeprefix("Ansi")
        if len(name) == 1 and name.isalnum():
            target = name.upper()
        elif name.startswith("Keypad") and name[6:].isdigit():
            target = "KP" + name[6:]
        elif name.startswith("F") and name[1:].isdigit():
            target = name
        else:
            target = SPECIAL.get(name)
        if target and hasattr(E, "KEY_" + target):
            result[item["value"]] = getattr(E, "KEY_" + target)
    return result


KEYMAP = keymap()
BUTTONS = {
    2: (E.BTN_LEFT, 1),
    3: (E.BTN_LEFT, 0),
    4: (E.BTN_RIGHT, 1),
    5: (E.BTN_RIGHT, 0),
    6: (E.BTN_MIDDLE, 1),
    7: (E.BTN_MIDDLE, 0),
}


class InputSink:
    def __init__(self, device=None):
        self.device = device
        self.pressed = set()
        self.active = False
        self.unmapped_count = 0
        self.event_count = 0
        self.wheel_remainder = 0

    def open(self):
        if self.device is not None:
            raise RuntimeError("input device already open")
        self.device = UInput(
            {
                E.EV_KEY: sorted(
                    set(KEYMAP.values()) | {E.BTN_LEFT, E.BTN_RIGHT, E.BTN_MIDDLE}
                ),
                E.EV_REL: [E.REL_X, E.REL_Y, E.REL_WHEEL],
            },
            name="Dell Network KVM (Linux)",
        )
        return self

    def set_active(self, value):
        if not value:
            self.release_all()
            self.wheel_remainder = 0
        self.active = value

    def emit_key(self, code, value):
        if value:
            self.pressed.add(code)
        else:
            self.pressed.discard(code)
        self.device.write(E.EV_KEY, code, value)

    def keyboard(self, cmd):
        if not self.active:
            return
        code = KEYMAP.get(cmd.get("vkCode"))
        if code is None:
            self.unmapped_count += 1
            return
        kind = cmd.get("type")
        if kind not in (1, 2):
            return
        value = 1 if kind == 1 else 0
        # Repeated key-down uses EV_KEY repeat value; preserve held state.
        if value and code in self.pressed:
            value = 2
        self.emit_key(code, value)
        self.device.syn()
        self.event_count += 1

    def mouse(self, cmd):
        if not self.active:
            return
        kind = cmd.get("type")
        if kind == 1:
            for code, name in [(E.REL_X, "dx"), (E.REL_Y, "dy")]:
                if cmd.get(name):
                    self.device.write(E.EV_REL, code, cmd[name])
        elif kind in BUTTONS:
            self.emit_key(*BUTTONS[kind])
        elif kind == 8:
            # Dell sends Windows-style 120-per-notch deltas; accumulate fine
            # trackpad deltas instead of emitting one notch per event.
            self.wheel_remainder += cmd.get("delta", 0)
            steps = int(self.wheel_remainder / 120)
            if not steps:
                return
            self.wheel_remainder -= steps * 120
            self.device.write(E.EV_REL, E.REL_WHEEL, steps)
        else:
            return
        self.device.syn()
        self.event_count += 1

    def release_all(self):
        if self.device:
            for code in list(self.pressed):
                self.emit_key(code, 0)
            self.device.syn()

    def close(self):
        self.release_all()
        self.active = False
        if self.device:
            self.device.close()
            self.device = None
