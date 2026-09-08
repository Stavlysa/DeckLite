#!/usr/bin/env bash
# Sourced only by Wine launchers, never the native desktop or Steam client.
# No font, audio stream, or synth is started until a WinMM MIDI output opens.
export DECKLITE_SOFT_MIDI="${DECKLITE_SOFT_MIDI:-1}"
if [[ "$DECKLITE_SOFT_MIDI" == 1 && ! -e /dev/snd/seq && \
        -r /opt/tiny/extra/libdecklite-soft-midi.so ]]; then
    _decklite_midi_preload="${LD_PRELOAD:-}"
    case ":${_decklite_midi_preload// /:}:" in
        *:/opt/tiny/extra/libdecklite-soft-midi.so:*) ;;
        *) export LD_PRELOAD="/opt/tiny/extra/libdecklite-soft-midi.so${LD_PRELOAD:+:$LD_PRELOAD}" ;;
    esac
    unset _decklite_midi_preload
fi
