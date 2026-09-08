# Debugging toolbox (Tiny Computer 4.3.0)

Default off. Turn on Debugging in Tiny Computer Settings to collect a bounded
private Android log. Pair only a trusted computer: its SSH key grants shell
access to the container and shared files. Pairing uses Android-authorized ADB:

    adb shell am broadcast -n com.fct.tc4/.debug.DebugPairingReceiver -a com.fct.tc4.action.PAIR_DEBUG_SSH --es public_key "ssh-ed25519 BASE64_PUBLIC_KEY"

Restart the container after enabling or pairing. Then on that computer:

    adb forward tcp:2227 tcp:8027
    ssh -p 2227 -i YOUR_PRIVATE_KEY tiny@127.0.0.1

The server binds 127.0.0.1 only, requires the paired Ed25519 key and disables
password/root login and SSH forwarding. Android USB debugging itself must be
enabled and authorized in Android Settings; this app cannot turn it on.

Turn the switch off to stop the optional Android collector immediately and
the managed SSH server/connections within about two seconds. Detached programs
started during a debug session may outlive SSH. Clear debugging logs and pairing
forgets the computer and removes the optional Android logs; exported ZIPs and
the guest's bounded SSH error/startup log are not deleted by that action.

Private host keys are generated on first use, never included in this image.
Consent/public keys are bound from the APK's private no-backup directory. A
container imported into an older APK has no such consent and cannot start SSH.
StrictModes is disabled for PRoot's emulated Unix ownership; Android app-private
storage remains the outer permission boundary. PRoot is not a security sandbox
for untrusted Windows programs. Debugging does not disable shortcut verification.
