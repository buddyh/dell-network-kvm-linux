"""Incremental Dell session decoder: protobuf or native compact dx,dy frames."""

import re
import protocol


class SessionFrames:
    def __init__(self, cluster_id, max_payload=1024 * 1024):
        self.cluster_id = cluster_id
        self.max_payload = max_payload
        self.buffer = bytearray()

    def feed(self, chunk):
        self.buffer.extend(chunk)
        result = []
        while len(self.buffer) >= 4:
            header = int.from_bytes(self.buffer[:4], "little")
            compact = self.buffer[3] == 0x40
            length = header & 0xFFFFFF if compact else header
            if length > self.max_payload:
                raise ValueError(f"oversized session frame (header=0x{header:08x})")
            if len(self.buffer) < 4 + length:
                break
            body = bytes(self.buffer[4 : 4 + length])
            del self.buffer[: 4 + length]
            if compact:
                if not re.fullmatch(rb"-?\d{1,10},-?\d{1,10}", body):
                    raise ValueError("invalid compact mouse frame")
                dx, dy = map(int, body.split(b","))
                if not all(-(1 << 31) <= v < (1 << 31) for v in (dx, dy)):
                    raise ValueError("compact mouse coordinate outside int32")
                result.append(
                    {
                        "type": 22,
                        "mouse": {
                            "clusterId": self.cluster_id,
                            "type": 1,
                            "dx": dx,
                            "dy": dy,
                            "delta": 0,
                        },
                    }
                )
            else:
                result.append(protocol.decode("BaseClusterCommand", body))
        return result
