# Dell Network KVM receiver for Linux

Experimental Dell Network KVM receiver for Hyprland.

Share a Mac's keyboard and mouse with Linux through Dell Display and Peripheral Manager's **Network KVM**. Tested on **Omarchy**, with Hyprland **0.56**, macOS DDPM **2.3.0.1005**, and a Dell U4025QW. This is an independent project, unaffiliated with Dell.

Your keyboard and mouse stay connected to the Mac. Arrange the Linux client beside it in DDPM, then cross the pointer between screens. Linux uses its own display; this client does not transmit video or switch monitor inputs.

**Experimental:** one Linux display, horizontal arrangement, ten-minute sessions. Other Hyprland distributions and Dell monitor setups have not been live-tested; GNOME/KDE need another desktop backend.

## Quick start

Prerequisites: Linux with one active Hyprland display, Python 3.14 (the tested version), `/dev/uinput`, and a Mac running the tested DDPM version with Network KVM enabled. Other Python versions have not been live-tested. Obtain DDPM directly from Dell. Dependencies are installed only in a virtual environment.

1. Download or clone this repository, open a terminal in it, and install the pinned dependencies:

   ```sh
   git clone https://github.com/buddyh/dell-network-kvm-linux.git
   cd dell-network-kvm-linux
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.lock
   ```

2. Grant your current Linux user temporary access to uinput. Review this first: it permits applications running as your user to create virtual input devices. It is not limited to this script.

   ```sh
   test -e /dev/uinput &&
     pkexec /usr/bin/setfacl -m "u:$(id -un):rw" /dev/uinput
   ```

   This assumes uinput is already available and `pkexec`/`setfacl` are installed. No persistent udev rule is installed. Stop if the device is absent and resolve that prerequisite separately.

3. Enter your Mac's current LAN IPv4 address and start the receiver:

   ```sh
   read -r -p 'Mac LAN IPv4 address: ' MAC_IP
   .venv/bin/python pair_hello.py "$MAC_IP" --receive
   ```

   The first run requests the normal DDPM PIN on the Mac. If the Mac is already showing a PIN, add `--existing-pin` to skip the request. Enter it in the **Linux terminal**, where input is hidden. Empty input cancels. There is one authentication attempt per required SSH connection, with no guessed PINs or automatic authentication retry. First-contact server keys are pinned; verify the target address on your own network before pairing.

4. In DDPM on the Mac, arrange the new Linux client to the right of the Mac. Wait for `receiver_ready`, then move the pointer across the Mac's right edge. Move back across the Linux display's left edge to return, or press **Ctrl+Alt+Escape** while Linux has control.

The receiver stops after **10 minutes**. Keep a physical Linux keyboard available during testing. To remove the temporary input-device permission after stopping:

```sh
pkexec /usr/bin/setfacl -x "u:$(id -un)" /dev/uinput
```

## What works and what remains experimental

| Capability | Evidence and limit |
|---|---|
| UDP discovery, normal PIN pairing, Hello and Join | Recorded live against macOS DDPM 2.3.0.1005 |
| Keyboard/mouse receive and return handoff | Tested on the configuration above |
| Public-key reconnection | Recorded successful public-key-only authentication on both SSH ports |
| Linux input adapter | evdev/uinput; ignores inactive input and releases held keys/buttons on deactivation/disconnect |
| Other DDPM versions | Recovered descriptor schemas matched 2.3.0.1005 and 2.3.0.2004; 2004 runtime compatibility is unverified |
| Multiple Linux displays / vertical arrangements | Unsupported by the current receiver |
| Multi-monitor Mac boundary alignment | Not fully validated |
| Scrolling, international/media keys | Mapping exists, but behavior is not comprehensively validated |
| Clipboard, file transfer, Linux input export | Not implemented |
| DisplayPort/HDMI input switching, USB upstream switching | Not implemented; separate hardware-KVM problem |
| Autostart, automatic reconnect, sessions over 10 minutes | Not implemented |

This is network input sharing, distinct from the U4025QW's built-in USB KVM. [ScriptGod1337/kvm](https://github.com/ScriptGod1337/kvm) is useful hardware-KVM precedent, but is a different project and protocol. No code from it is included here.

For general software input sharing, [Lan Mouse](https://github.com/feschber/lan-mouse) and [Deskflow](https://github.com/deskflow/deskflow) are existing alternatives with their own protocols. This project focuses on interoperating with Dell's existing Network KVM service.

## Tests and diagnostics

```sh
# Offline: does not contact the Mac or open a real input device.
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -p 'test_*.py' -v

# Offline packet construction and decoding:
.venv/bin/python discovery.py

# Optional single-host discovery; this sends one UDP request:
.venv/bin/python discovery.py --probe "$MAC_IP"

# Optional authentication/Hello only (no Join or input device):
.venv/bin/python pair_hello.py "$MAC_IP"
```

The `--join-probe` mode briefly joins a cluster without injecting input. Joining may still enable DDPM pointer redirection, so keep the pointer near the Mac's center during that probe. See [troubleshooting](docs/troubleshooting.md).

## State and privacy

`state/` is generated locally at runtime. It contains the private RSA identity, pinned service keys, registration metadata, local client identity, topology and aggregate status. **Never commit or attach it to an issue.** PIN/password values are not intentionally persisted. The receiver does not log keyboard contents or mouse coordinates, but status/Hello/topology output can identify computers and addresses. Review terminal output before sharing it.

Pinned service keys and the key registration are stored per Mac IPv4 address. If the Mac's address changes (for example, a new DHCP lease), the next run treats it as a first contact: it pins the new service keys and asks for a PIN again. Give the Mac a DHCP reservation to avoid this.

Public-key registration creates continuing authorization on the paired Mac. Deleting the local state does not revoke that Mac-side authorization; manage/remove the paired client through DDPM when retiring access. See [security](SECURITY.md) for first-contact trust and input-control boundaries.

## Development

See [contributing](CONTRIBUTING.md), [protocol notes](docs/protocol.md), and [troubleshooting](docs/troubleshooting.md). Tests run offline; live compatibility has only been tested on the configuration above.

MIT license for original code and documentation. This is an independent project, unaffiliated with Dell; see [vendor notice](NOTICE.md).
