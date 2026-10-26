# Security and operational boundaries

This experimental receiver can deliver keyboard and mouse events to your Linux desktop. Pair only with a Mac you control, using the PIN shown by its DDPM application, on a network you trust. No host scanning or automatic PIN guessing is implemented.

Both SSH connections use Paramiko and pin the first observed service keys. **Trust on first use is not independent verification of the first server key.** A changed key stops the connection; investigate it rather than deleting the pin to silence the error.

Normal public-key registration authorizes future sessions on the Mac. The local private key is generated per installation and written with mode 0600. State-directory creation requests 0700, and other state-file creation requests 0600. Existing directories/files are not automatically repaired to those modes; protect the checkout and state directory yourself. Do not copy an identity to another person or include any state file in a bug report.

Temporary `/dev/uinput` access permits input-device creation by your user, not just this program. The README uses a per-user ACL rather than a world-writable device or persistent rule. Revoke that ACL when testing is finished. The receiver itself should run as your normal user, not root.

The receiver releases held keys/buttons on normal deactivation and cleanup, attempts return to the Mac when exiting while active, and sends Leave. Abrupt termination, compositor failure and malformed peer traffic are not fully hardened. Keep physical input available; Ctrl+Alt+Escape and the ten-minute session limit are conveniences, not guaranteed recovery mechanisms after every failure.

No clipboard or files are transferred. Console output and generated state can still contain local addresses, client names, registration metadata and topology. Redact these before sharing diagnostics. Never post PINs, private keys, pairing responses or full terminal captures.

This code has not undergone a comprehensive security audit. Report suspected issues privately through GitHub's private vulnerability reporting feature if available on the published repository. Otherwise, open a minimal issue asking for a private contact without attaching sensitive evidence.
