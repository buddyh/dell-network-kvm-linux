# Contributing

Keep changes small. Protocol fixes, desktop integrations and packaging can be developed independently.

## Code layout

- `discovery.py`: UDP discovery and low-level protobuf fields.
- `pair_hello.py`, `auth_identity.py`: pairing, host-key pinning and local identity.
- `protocol.py`, `schema/`: message codec and reconstructed wire schema.
- `join_probe.py`, `receiver.py`: Join handshake, session loop and Hyprland integration.
- `stream_frames.py`, `input_sink.py`: frame decoding and Linux input events.

## Tests

From the repository root, using the README's Linux virtual environment:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -p 'test_*.py' -v
```

Tests use synthetic packets, fake devices and in-memory channels. They do not contact DDPM or inject real input. CI runs the suite on Linux with Python 3.14.

On macOS, the dependency-free subset can run with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  test_discovery.py test_protocol.py test_stream_frames.py
```

Add regressions for protocol failures and verify key/button release when changing input handling. Keep live pairing and input injection out of automated tests. Describe the exact versions tested when reporting compatibility.

Python source uses Black's default formatting. Do not combine behavior changes with unrelated reformatting.

See [troubleshooting](docs/troubleshooting.md) for bug reports and [security](SECURITY.md) for sensitive reports. Contributions are under the MIT license; do not include vendor-owned code or binaries.
