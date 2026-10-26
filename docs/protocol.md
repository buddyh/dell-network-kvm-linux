# Protocol notes

These are observations from the October 22, 2026 interoperability experiment. They describe the implemented subset, not an official protocol specification.

## Transport and ordering

- Discovery is a single UDP Ping to port 5567. The framing prefix is `cb0a6764c259bdbfa1c462d3`, followed by a little-endian uint32 payload size and a Protocol Buffers message. The client uses an ephemeral local source port.
- The tested Mac advertises SSH services on TCP 5566 and 5567. The client opens two authenticated PTY/shell channels using Dell's `SKvm_Multiple` service username.
- During Hello and Join, send on 5566 and receive on 5567.
- **After JoinResponse, the channel roles reverse:** receive on 5566 and send on 5567. Missing this reversal caused the early connection to close around ten seconds after joining.
- The implemented protocol major/minor is 6.0. Join reports Linux truthfully, with no supported Dell monitor and no request to take active control. The multiple-display setup enum is 4; value 2 means SingleDisplay.

## Frames and input

Normal stream messages have a little-endian length prefix and a protobuf payload. The native implementation also emits compact mouse frames whose header has high byte `0x40` and a lower-24-bit payload length. Their payload is ASCII signed `dx,dy`.

Disabling smooth mouse does not eliminate compact frames. The first working handoff initially failed immediately when one arrived. `stream_frames.py` now incrementally decodes split/coalesced packets in both formats, with bounds and signed-int32 checks. Its regression tests include handoff → compact movement → Alive.

The receiver gates input on the active client and cluster, converts Dell virtual-key enums to Linux evdev codes, releases held input on deactivation, handles Alive/Success, and returns control at the horizontal boundary. The Hyprland 0.56 cursor call uses `hyprctl eval` with `hl.dispatch(hl.dsp.cursor.move(...))` and numeric coordinates calculated from the monitor geometry. If that call fails, the receiver falls back to `hyprctl dispatch movecursor` for hyprlang-configured setups. Scroll deltas are treated as 120 units per notch and accumulated, so fine trackpad deltas do not each emit a full notch.

## Pairing and reconnection

The first run uses DDPM's normal displayed PIN. The implementation transforms it as observed in the native authentication path; the value remains in memory and is not intentionally written to disk. It makes one attempt per required stream.

Once joined, command 27 (`SshCopyId`) registers only the client's generated RSA public identity with relay disabled. A correlated command 28 response records successful registration locally. Subsequent runs use that private identity; original readback verified public-key-only authentication separately on both ports.

## Schema

`schema/ddpm-2.3.0.1005.json` contains 45 reconstructed message definitions, 201 fields and 12 enums. It retains wire names, tags, types, repetition/packing flags and type references needed by the Python codec.

The recovered 1005/2004 descriptors matched in the original experiment, as did the observed framing constants. That comparison does not establish runtime compatibility with 2004, future releases, Windows peers or every message type.

The schema-driven codec supports the subset exercised by this client and its tests. It is not a general, hardened protobuf implementation. Treat malformed/untrusted peer traffic and unexercised field encodings as limitations.
