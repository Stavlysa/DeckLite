#!/usr/bin/env bash
# Conservative defaults shared by Steam, Proton, standalone Wine and native
# Linux games.  Every value remains user-overridable before a launcher starts.
[[ -r /etc/profile.d/00-decklite-glibc-loader.sh ]] && \
    source /etc/profile.d/00-decklite-glibc-loader.sh
export MESA_SHADER_CACHE_DIR="${MESA_SHADER_CACHE_DIR:-$HOME/.cache/mesa_shader_cache}"
export MESA_SHADER_CACHE_MAX_SIZE="${MESA_SHADER_CACHE_MAX_SIZE:-1G}"
export MESA_SHADER_CACHE_DISABLE="${MESA_SHADER_CACHE_DISABLE:-false}"
export mesa_glthread="${mesa_glthread:-true}"
# Turnip's compressed render targets produce intermittent black checkerboards
# on the tested Adreno 740 + nested X11 path (both DXVK and WineD3D). Keep GPU
# rendering, but disable UBWC until this driver path is fixed. TU_DEBUG is read
# only by Turnip; other GPU drivers are unaffected. Preserve additional flags
# and avoid duplicates when this profile is sourced by several wrappers.
# Set DECKLITE_TURNIP_SAFE_RENDER=0 before launch for a diagnostic opt-out.
if [[ "${DECKLITE_TURNIP_SAFE_RENDER:-1}" != 0 ]]; then
    case ",${TU_DEBUG:-}," in
        *,noubwc,*) ;;
        *) export TU_DEBUG="${TU_DEBUG:+$TU_DEBUG,}noubwc" ;;
    esac
fi
# Wine games should not inherit the nested desktop compositor's refresh-rate
# limiter. These Mesa switches cover OpenGL/WineD3D and Vulkan/DXVK while still
# allowing a launcher to opt back into synchronization explicitly.
export vblank_mode="${vblank_mode:-0}"
export MESA_VK_WSI_PRESENT_MODE="${MESA_VK_WSI_PRESENT_MODE:-immediate}"
export __GL_SYNC_TO_VBLANK="${__GL_SYNC_TO_VBLANK:-0}"
export DXVK_STATE_CACHE="${DXVK_STATE_CACHE:-1}"
export DXVK_LOG_LEVEL="${DXVK_LOG_LEVEL:-none}"

# Tiny Audio forwards PulseAudio into Android.  A modest client buffer avoids
# bursty PRoot scheduling turning into repeated underruns without making rhythm
# games feel excessively delayed.
export PULSE_LATENCY_MSEC="${PULSE_LATENCY_MSEC:-80}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-pulseaudio}"
export ALSOFT_DRIVERS="${ALSOFT_DRIVERS:-pulse}"
export WINEDEBUG="${WINEDEBUG:--all}"
