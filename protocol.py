"""Wire codec derived from the recorded DDPM 2.3.0.1005 GPB descriptors.
Names retain Objective-C spelling; these are reconstructed schemas, not Dell source.
"""

import json
from pathlib import Path
import struct
from discovery import field, fields, read_varint, varint

SCHEMA = json.loads((Path(__file__).parent / "schema/ddpm-2.3.0.1005.json").read_text())
MESSAGES = SCHEMA["messages"]
FIXED = {
    "float": "f",
    "double": "d",
    "fixed32": "I",
    "sfixed32": "i",
    "fixed64": "Q",
    "sfixed64": "q",
}
TYPES = {
    "double": 1,
    "fixed64": 1,
    "sfixed64": 1,
    "float": 5,
    "fixed32": 5,
    "sfixed32": 5,
    "string": 2,
    "bytes": 2,
    "message": 2,
}


def child(f):
    return f["specific"].removeprefix("_OBJC_CLASS_$_")


def encode(name, values):
    known = {f["name"]: f for f in MESSAGES[name]["fields"]}
    unknown = set(values) - known.keys()
    if unknown:
        raise ValueError(f"{name}: unknown fields {unknown}")
    out = bytearray()
    for key, value in values.items():
        f = known[key]
        typ = f["type"]
        number = f["number"]
        for v in value if f["repeated"] else [value]:
            if typ == "message":
                out += field(number, encode(child(f), v))
            elif typ in ("string", "bytes"):
                out += field(number, v)
            elif typ in FIXED:
                out += varint(number << 3 | TYPES[typ]) + struct.pack(
                    "<" + FIXED[typ], v
                )
            elif typ in ("sint32", "sint64"):
                bits = 32 if typ == "sint32" else 64
                out += field(number, (v << 1) ^ (v >> (bits - 1)))
            else:
                out += field(number, int(v) & ((1 << 64) - 1))
    return bytes(out)


def decode(name, data, depth=0):
    if depth > 24:
        raise ValueError("message nesting limit")
    raw = fields(data)
    result = {}
    for f in MESSAGES[name]["fields"]:
        if f["number"] not in raw:
            continue
        values = raw.pop(f["number"])
        typ = f["type"]
        decoded = []
        if f["packed"]:
            packed = []
            for v in values:
                if isinstance(v, int):
                    packed.append(v)
                    continue
                if typ in FIXED:
                    size = struct.calcsize("<" + FIXED[typ])
                    if len(v) % size:
                        raise ValueError("truncated packed field")
                    packed.extend(v[i : i + size] for i in range(0, len(v), size))
                    continue
                pos = 0
                while pos < len(v):
                    item, pos = read_varint(v, pos)
                    packed.append(item)
            values = packed
        for v in values:
            if typ == "message":
                v = decode(child(f), v, depth + 1)
            elif typ == "string":
                v = v.decode("utf-8")
            elif typ == "bytes":
                v = {"hex": v.hex()}
            elif typ == "bool":
                v = bool(v)
            elif typ in FIXED:
                v = struct.unpack("<" + FIXED[typ], v)[0]
            elif typ in ("sint32", "sint64"):
                v = (v >> 1) ^ -(v & 1)
            elif typ in ("int32", "int64"):
                bits = 32 if typ == "int32" else 64
                v &= (1 << bits) - 1
                if v & (1 << (bits - 1)):
                    v -= 1 << bits
            decoded.append(v)
        result[f["name"]] = decoded if f["repeated"] else decoded[-1]
    if raw:
        result["_unknown_field_numbers"] = sorted(raw)
    return result


def command(command_id, kind, **payload):
    return encode("BaseClusterCommand", {"id_p": command_id, "type": kind, **payload})


def frame(payload):
    return struct.pack("<I", len(payload)) + payload
