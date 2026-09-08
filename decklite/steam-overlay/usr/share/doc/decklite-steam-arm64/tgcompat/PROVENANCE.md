# tgcompat robust-list shim provenance

Source repository: `https://github.com/huntergdavis/termux-glibc-compat`

Source commit: `8d63206ac60eb1106cb5303f1ac75f5a3bd60a62`

The bundled `libtgcompat-robust.so` was compiled inside the target Debian 13
ARM64 Tiny Container on a Samsung SM-X810 with:

```sh
gcc -O2 -fPIC -shared -o libtgcompat-robust.so \
  robust_shim.c flock_shim.c robust_shim_aarch64.S -ldl
```

Bundled binary SHA-256:
`48d1eccfcb3e5546cea0c38b3fdabadd9845de6fa2aecb3335da9f40a0a79a83`

This shim is enabled only for Steam's launch process. It emulates the
current-thread `get_robust_list` query that Valve's ARM64 client requires and
provides an opt-in `flock` fallback. It does not claim kernel owner-death
recovery for synthetic robust mutexes.
