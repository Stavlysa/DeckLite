export PATH="$HOME/.local/bin:$PATH"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-${USER:-alarm}}"
export STEAMOS=1

if [[ $- == *i* ]] && [[ -z "${DECKLITE_WELCOME_SHOWN:-}" ]]; then
    export DECKLITE_WELCOME_SHOWN=1
    printf '\nDeckLite (Arch Linux ARM / Tiny Container)\n'
    printf 'Run decklite-info for status. Desktop and Steam layers are optional.\n\n'
fi

