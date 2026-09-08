# steamclienttermux compatibility work provenance

Source repository: `https://github.com/huntergdavis/steamclienttermux`

Source commit: `dee92b8432424e873011542e6926b12651bc823c`

DeckLite's scoped `/usr/bin/lsof` responder is adapted from `bin/lsof`. The
three Steam UI network-method guards in `patch-steam-ui.py` are a Python
implementation of the exact replacements documented by
`bin/patch-steam-network-ui.sh`. The `/dev/shm` webhelper argument and software
CEF launch settings follow the same project's measured Android fixes.

The adaptations keep the original narrow boundaries: unrelated lsof commands
delegate to Debian's preserved binary, and the UI patch refuses to edit an
unexpected Steam JavaScript build.
