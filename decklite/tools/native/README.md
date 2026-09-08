# Custom native helpers

`wine-display-launch.c` is the current ARM64 Windows PE entry point. It includes
`wine-game-launch.c` for the explicitly selected legacy focus/borderless path.
Building only the latter does **not** produce the current automatic display helper.

On Windows, pass a directory containing LLVM clang, llvm-dlltool and ld.lld:

```powershell
./build_wine_game_launch.ps1 -LlvmBin /path/to/llvm/bin
```

The output goes to ignored `decklite/build/native/`; the script does not replace
the reviewed overlay binary. Revalidate the helper before including a new build
in an image. No game or Windows SDK headers/libraries are required.

Build the affinity shim natively on ARM64 Linux:

```sh
gcc -shared -fPIC -O2 -Wall -Wextra -Werror \
  affinity_shim.c affinity_shim_aarch64.S -ldl -o libdecklite-affinity.so
```

For the software MIDI bridge, use `bash build_soft_midi.sh OUTPUT.so` and install
the Debian dependencies listed in that script. These Linux preload libraries are
not Android libraries. Do not build them with the Android NDK's Bionic toolchain.
