# Wine MIDI output on Android

The normal EXE association, `run-exe`, and Wine Manager run through
`wine-prefix-run`. They enable a software WinMM MIDI output if Android does
not expose `/dev/snd/seq`. No per-game EXE, DLL override, registry patch, or
special shortcut is required. A real sequencer is left to ALSA unchanged.

This is a native ARM64 ALSA-output adapter for Hangover 11.16's Wine ALSA
driver. WinMM continues to handle 32/64-bit translation, MIDI buffers,
callbacks and stream timing; FluidSynth renders notes into the existing
PulseAudio-compatible PipeWire output. PCM audio and MIDI input are not
intercepted. This is not a complete ALSA sequencer emulation and requires
regression testing when Wine is updated. Native Steam/Proton launchers and
raw `/usr/bin/wine` commands do not source this helper automatically.

Enumeration does not load FluidSynth, the soundfont or audio threads.
Opening an output loads the synth/font on demand, but the audio stream starts
only on the first nonzero-velocity note. This avoids a silent audio stream
when an application opens MIDI yet uses another music backend. Closing releases the synthesizer
and audio stream; dependency libraries and some idle library worker threads
can remain until that Wine process exits. There is no separate MIDI server,
listening network port, startup daemon, or always-running synthesizer.

The existing `TimGM6mb.sf2` General MIDI font is used. Unsupported GS banks
may use the corresponding GM bank; this is not bit-exact Roland hardware
emulation. A readable alternative font can be selected per launch using
`DECKLITE_MIDI_SOUNDFONT=/absolute/path/font.sf2`. A missing font causes an
output-open error rather than silently pretending to play.

`DECKLITE_SOFT_MIDI=0 run-exe /path/program.exe` disables the fallback.
For manual raw Wine commands, source
`/opt/tiny/wine-manager/wine-midi-env.sh` inside that command's subshell.
Do not globally preload this into unrelated Linux applications.

Native source and build instructions live at `tools/native/soft_midi.c`
and `tools/native/build_soft_midi.sh` in the container project. Build on
ARM64 with ALSA and FluidSynth development headers. The shipped library
links ALSA and loads FluidSynth 3 lazily. Keep the binary and runtime font
in the container, not merely on the developer's test device.

Tested on Samsung SM-X810 with Hangover 11.16: WinMM enumeration, mapper,
short messages, GM-reset SysEx, timed MIDI streams, output callbacks,
close/reopen in both 32 and 64 bit, plus TH08's MIDI mode. The user confirmed
TH08's music was audible. This does not resolve the separate PC-98 DOSBox-X
PCM stuttering investigation.
