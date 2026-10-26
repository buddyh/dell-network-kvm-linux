# Troubleshooting

| Symptom | Check |
|---|---|
| No PIN dialog on the Mac | Confirm DDPM Network KVM is enabled and the target IPv4 address is the Mac. Reopen the pairing helper only after the previous attempt has exited. A prior helper waiting for input is not a successful pairing. |
| PIN entry appears blank | Input is deliberately hidden in the Linux terminal. Enter the currently displayed six ASCII digits. Empty input cancels. Do not paste the PIN into an issue. |
| A registered-key reconnect fails | Check that DDPM still recognizes the paired client and that the target address is current. Do not copy someone else's state or automatically fall back to PIN loops. |
| PIN requested again after pairing | Pairing is stored per Mac IPv4 address. A changed address starts a new first contact; verify it is the same Mac before entering the PIN. |
| Host key changed | Investigate the address/service and verify the new key. Do not blindly delete pinned keys. |
| Permission denied on `/dev/uinput` | Check the temporary per-user ACL. Reboot/device recreation normally removes it. Do not run the entire receiver as root or make the device world-writable. |
| Receiver rejects multiple monitors | The current implementation requires exactly one active Linux monitor. |
| Connection closes around ten seconds after Join | Verify that established sessions read on 5566 and write on 5567, reversing the handshake roles. |
| Handoff fails at cursor placement | The receiver tries Lua-configured Hyprland 0.56's `hyprctl eval` call, then falls back to `hyprctl dispatch movecursor`. Older/different compositor versions need separate validation. |
| Handoff fails on an unexpected header | Use the compact-mouse decoder; smooth-mouse-disabled settings do not exclude compact frames. |
| Cursor enters at an unexpected height | Multi-monitor Mac Y-boundary alignment is not fully implemented. Test a simple horizontal arrangement. |
| Wheel or special key behaves unexpectedly | Mapping and scaling are experimental. Do not assume full international/media-key compatibility. |
| Session ends after ten minutes | This is the original intentional test limit, not automatic reconnect or an installed service. |
| Monitor still shows the Mac | Expected: this receiver shares input only. Select the desired video input separately or use a separate Linux display. |

For useful bug reports, provide the DDPM version, Linux/Python/Hyprland versions, number and arrangement of displays, the error class, and a minimal sanitized reproduction. Exclude host addresses/names, client/cluster IDs, private keys, PINs, topology responses, state and raw terminal transcripts.
