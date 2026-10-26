"""Dell DDPM 2.3.0.1005 discovery framing (descriptors match 2.3.0.2004).
Default invocation prints a packet without networking. --probe sends one unicast
ping to the supplied literal IP. Pairing/input/monitor changes are not performed.
"""

import argparse
import ipaddress
import json
import socket
import struct
import uuid

MAGIC = bytes.fromhex("cb0a6764c259bdbfa1c462d3")


def varint(value):
    if not 0 <= value < 1 << 64:
        raise ValueError("integer outside uint64")
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    if isinstance(value, str):
        value = value.encode("utf-8")
    return varint((number << 3) | 2) + varint(len(value)) + value


def read_varint(data, pos):
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise ValueError("truncated varint")
        byte = data[pos]
        pos += 1
        if shift == 63 and byte > 1:
            raise ValueError("oversized varint")
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError("oversized varint")


def fields(data):
    pos = 0
    result = {}
    while pos < len(data):
        key, pos = read_varint(data, pos)
        number, wire = key >> 3, key & 7
        if not 0 < number < 1 << 29:
            raise ValueError("invalid field number")
        if wire == 0:
            value, pos = read_varint(data, pos)
        elif wire in (1, 2, 5):
            if wire == 2:
                n, pos = read_varint(data, pos)
            else:
                n = 8 if wire == 1 else 4
            if n > len(data) - pos:
                raise ValueError("truncated field")
            value = data[pos : pos + n]
            pos += n
        else:
            raise ValueError("unsupported protobuf wire type")
        result.setdefault(number, []).append(value)
    return result


def ping(tag):
    # BaseDiscoveryCommand: reportTag=1, type=2 (Ping=1), ping=3.
    # CommandPing: protocolMajorVersion=1 (6), minor defaults to 0.
    body = field(1, tag) + field(2, 1) + field(3, field(1, 6))
    return MAGIC + struct.pack("<I", len(body)) + body


def decode(packet):
    if len(packet) < 16 or packet[:12] != MAGIC:
        raise ValueError("invalid discovery header")
    n = struct.unpack_from("<I", packet, 12)[0]
    if n != len(packet) - 16:
        raise ValueError("discovery length mismatch")
    base = fields(packet[16:])
    tag = base.get(1, [b""])[-1].decode("utf-8")
    kind = base.get(2, [0])[-1]
    result = {"report_tag": tag, "type": kind}
    if kind == 2 and 4 in base:
        pong = fields(base[4][-1])
        result["pong"] = {}
        for num, name in enumerate(
            [
                "client_id",
                "client_name",
                "cluster_id",
                "cluster_name",
                "is_online",
                "is_same_monitor",
            ],
            1,
        ):
            if num in pong:
                value = pong[num][-1]
                result["pong"][name] = value.decode("utf-8") if num < 5 else bool(value)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe",
        type=ipaddress.ip_address,
        help="send one unicast discovery packet to this IP",
    )
    parser.add_argument("--port", type=int, default=5567)
    parser.add_argument("--timeout", type=float, default=4)
    parser.add_argument(
        "--decode", metavar="HEX", help="decode an existing packet without networking"
    )
    args = parser.parse_args()
    if args.decode:
        print(json.dumps(decode(bytes.fromhex(args.decode)), indent=2))
        return
    tag = str(uuid.uuid4())
    packet = ping(tag)
    if not args.probe:
        print(
            json.dumps(
                {"packet_hex": packet.hex(), "decoded": decode(packet)}, indent=2
            )
        )
        return
    if (
        args.probe.is_multicast
        or args.probe.is_unspecified
        or str(args.probe) == "255.255.255.255"
    ):
        parser.error("provide a single host IP")
    if not 0 < args.port < 65536 or not 0 < args.timeout <= 30:
        parser.error("invalid port or timeout")
    family = socket.AF_INET6 if args.probe.version == 6 else socket.AF_INET
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(args.timeout)
        # An ephemeral port avoids binding or disrupting DDPM's service port.
        sock.sendto(packet, (str(args.probe), args.port))
        try:
            data, peer = sock.recvfrom(65535)
            result = decode(data)
            result.update(peer=peer, tag_matches=result["report_tag"] == tag)
            print(json.dumps(result, indent=2))
        except socket.timeout:
            print(
                json.dumps(
                    {"status": "no reply", "target": str(args.probe), "port": args.port}
                )
            )


if __name__ == "__main__":
    main()
