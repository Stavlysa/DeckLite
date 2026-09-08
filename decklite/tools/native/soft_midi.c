/* Process-local ALSA MIDI output fallback for Wine on Android.
 * Uses public ALSA/FluidSynth APIs, not Wine-private structs or kernel devices.
 * MIDI input and PCM are not intercepted. Real sequencers are forwarded.
 * Enabled by Wine launchers with DECKLITE_SOFT_MIDI=1 when /dev/snd/seq
 * is absent. This implements Wine's output API subset, not a full sequencer.
 */
#define _GNU_SOURCE
#include <alsa/asoundlib.h>
#include <fluidsynth.h>
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Keep FluidSynth and its codec dependencies out of non-MIDI Wine processes.
 * No font, audio thread, or synthesizer is created merely to enumerate ports. */
#define FLUID_FUNCTIONS(X) \
    X(new_fluid_settings) X(delete_fluid_settings) \
    X(fluid_settings_setstr) X(fluid_settings_setnum) X(fluid_settings_setint) \
    X(new_fluid_synth) X(delete_fluid_synth) X(fluid_synth_sfload) \
    X(new_fluid_audio_driver) X(delete_fluid_audio_driver) \
    X(fluid_synth_noteon) X(fluid_synth_noteoff) X(fluid_synth_key_pressure) \
    X(fluid_synth_cc) X(fluid_synth_program_change) X(fluid_synth_channel_pressure) \
    X(fluid_synth_pitch_bend) X(fluid_synth_sysex) X(fluid_synth_system_reset)
#define DECLARE_FLUID(name) static __typeof__(&name) p_##name;
FLUID_FUNCTIONS(DECLARE_FLUID)
#undef DECLARE_FLUID
static void *fluid_library;

/* Called only with mutex held. Publish the library after every symbol exists. */
static int load_fluid(void)
{
    void *library;
    if (fluid_library) return 0;
    library = dlopen("libfluidsynth.so.3", RTLD_NOW | RTLD_LOCAL);
    if (!library) return -ENOENT;
#define LOAD_FLUID(name) do { \
    p_##name = (__typeof__(&name))dlsym(library, #name); \
    if (!p_##name) { dlclose(library); return -ENOSYS; } \
} while (0);
    FLUID_FUNCTIONS(LOAD_FLUID)
#undef LOAD_FLUID
    fluid_library = library;
    return 0;
}

#define new_fluid_settings p_new_fluid_settings
#define delete_fluid_settings p_delete_fluid_settings
#define fluid_settings_setstr p_fluid_settings_setstr
#define fluid_settings_setnum p_fluid_settings_setnum
#define fluid_settings_setint p_fluid_settings_setint
#define new_fluid_synth p_new_fluid_synth
#define delete_fluid_synth p_delete_fluid_synth
#define fluid_synth_sfload p_fluid_synth_sfload
#define new_fluid_audio_driver p_new_fluid_audio_driver
#define delete_fluid_audio_driver p_delete_fluid_audio_driver
#define fluid_synth_noteon p_fluid_synth_noteon
#define fluid_synth_noteoff p_fluid_synth_noteoff
#define fluid_synth_key_pressure p_fluid_synth_key_pressure
#define fluid_synth_cc p_fluid_synth_cc
#define fluid_synth_program_change p_fluid_synth_program_change
#define fluid_synth_channel_pressure p_fluid_synth_channel_pressure
#define fluid_synth_pitch_bend p_fluid_synth_pitch_bend
#define fluid_synth_sysex p_fluid_synth_sysex
#define fluid_synth_system_reset p_fluid_synth_system_reset

struct soft_seq {
    struct soft_seq *next;
    int next_port, output_port;
    unsigned long events;
    fluid_settings_t *settings;
    fluid_synth_t *synth;
    fluid_audio_driver_t *audio;
};
static struct soft_seq *sequences;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
#define FORWARD(fn, args) do { \
    __typeof__(&fn) real = (__typeof__(&fn))dlsym(RTLD_NEXT, #fn); \
    return real ? real args : -ENOSYS; \
} while (0)

static struct soft_seq *lookup(snd_seq_t *seq)
{
    struct soft_seq *s;
    for (s = sequences; s; s = s->next) if ((snd_seq_t *)s == seq) return s;
    return NULL;
}

static void stop_synth(struct soft_seq *s)
{
    if (s->audio) delete_fluid_audio_driver(s->audio);
    if (s->synth) delete_fluid_synth(s->synth);
    if (s->settings) delete_fluid_settings(s->settings);
    s->audio = NULL; s->synth = NULL; s->settings = NULL;
}

static int start_synth(struct soft_seq *s)
{
    const char *font = getenv("DECKLITE_MIDI_SOUNDFONT");
    if (!font || !*font) font = "/usr/share/sounds/sf2/TimGM6mb.sf2";
    if (access(font, R_OK)) return -ENOENT;
    int result = load_fluid();
    if (result) return result;
    s->settings = new_fluid_settings();
    if (!s->settings) return -ENOMEM;
    fluid_settings_setstr(s->settings, "audio.driver", "pulseaudio");
    fluid_settings_setnum(s->settings, "synth.sample-rate", 48000);
    fluid_settings_setnum(s->settings, "synth.gain", 0.35);
    fluid_settings_setint(s->settings, "synth.cpu-cores", 1);
    fluid_settings_setint(s->settings, "synth.polyphony", 256);
    fluid_settings_setint(s->settings, "audio.period-size", 512);
    fluid_settings_setint(s->settings, "audio.periods", 4);
    /* Android does not grant this container real-time scheduler privileges. */
    fluid_settings_setint(s->settings, "audio.realtime-prio", 0);
    s->synth = new_fluid_synth(s->settings);
    if (!s->synth || fluid_synth_sfload(s->synth, font, 1) < 0) goto fail;
    /* Some applications open WinMM MIDI at startup even when their actual
     * music uses PCM/FM. Start an audio stream only on the first real note. */
    return 0;
fail:
    stop_synth(s);
    return -EIO;
}

int snd_seq_open(snd_seq_t **handle, const char *name, int streams, int mode)
{
    const char *enable = getenv("DECKLITE_SOFT_MIDI");
    struct soft_seq *s;
    if (!enable || strcmp(enable, "1") || !name || strcmp(name, "default") ||
        access("/dev/snd/seq", F_OK) == 0 || errno != ENOENT)
        FORWARD(snd_seq_open, (handle, name, streams, mode));
    if (!handle || !(streams & SND_SEQ_OPEN_OUTPUT)) return -ENODEV;
    s = calloc(1, sizeof(*s));
    if (!s) return -ENOMEM;
    s->output_port = -1;
    pthread_mutex_lock(&mutex);
    s->next = sequences; sequences = s;
    pthread_mutex_unlock(&mutex);
    *handle = (snd_seq_t *)s;
    return 0;
}

int snd_seq_close(snd_seq_t *handle)
{
    struct soft_seq *s, **prev;
    pthread_mutex_lock(&mutex);
    for (prev = &sequences; (s = *prev); prev = &s->next) {
        if ((snd_seq_t *)s != handle) continue;
        *prev = s->next;
        stop_synth(s);
        if (getenv("DECKLITE_MIDI_TRACE")) fprintf(stderr, "DeckLite MIDI: close; %lu events\n", s->events);
        free(s);
        pthread_mutex_unlock(&mutex);
        return 0;
    }
    pthread_mutex_unlock(&mutex);
    FORWARD(snd_seq_close, (handle));
}

int snd_seq_set_client_name(snd_seq_t *handle, const char *name)
{
    int ours;
    pthread_mutex_lock(&mutex); ours = lookup(handle) != NULL; pthread_mutex_unlock(&mutex);
    if (ours) return 0;
    FORWARD(snd_seq_set_client_name, (handle, name));
}

int snd_seq_query_next_client(snd_seq_t *handle, snd_seq_client_info_t *info)
{
    int ours;
    pthread_mutex_lock(&mutex); ours = lookup(handle) != NULL; pthread_mutex_unlock(&mutex);
    if (!ours) FORWARD(snd_seq_query_next_client, (handle, info));
    if (snd_seq_client_info_get_client(info) >= 128) return -ENOENT;
    snd_seq_client_info_set_client(info, 128);
    snd_seq_client_info_set_name(info, "DeckLite");
    return 0;
}

int snd_seq_query_next_port(snd_seq_t *handle, snd_seq_port_info_t *info)
{
    int ours;
    pthread_mutex_lock(&mutex); ours = lookup(handle) != NULL; pthread_mutex_unlock(&mutex);
    if (!ours) FORWARD(snd_seq_query_next_port, (handle, info));
    /* ALSA stores the initial -1 port sentinel in an unsigned 8-bit field. */
    int previous = snd_seq_port_info_get_port(info);
    if (snd_seq_port_info_get_client(info) != 128 || (previous != -1 && previous != 255)) return -ENOENT;
    snd_seq_port_info_set_port(info, 0);
    snd_seq_port_info_set_name(info, "Software MIDI");
    snd_seq_port_info_set_capability(info, SND_SEQ_PORT_CAP_WRITE | SND_SEQ_PORT_CAP_SUBS_WRITE);
    /* Wine routes SysEx only through MOD_MIDIPORT, not MOD_SYNTH. Do not
     * advertise the ALSA volume controls which this output does not expose. */
    snd_seq_port_info_set_type(info, SND_SEQ_PORT_TYPE_MIDI_GENERIC | SND_SEQ_PORT_TYPE_APPLICATION);
    return 0;
}

int snd_seq_create_simple_port(snd_seq_t *handle, const char *name, unsigned int caps, unsigned int type)
{
    struct soft_seq *s;
    int result;
    pthread_mutex_lock(&mutex);
    s = lookup(handle);
    if (!s) { pthread_mutex_unlock(&mutex); FORWARD(snd_seq_create_simple_port, (handle, name, caps, type)); }
    /* An ALSA-readable application port sends data to our write-only synth. */
    if (!(caps & SND_SEQ_PORT_CAP_READ)) result = -ENODEV;
    else if (s->output_port >= 0) result = -EBUSY;
    else if ((result = start_synth(s)) == 0) result = s->output_port = s->next_port++;
    pthread_mutex_unlock(&mutex);
    return result;
}

int snd_seq_delete_simple_port(snd_seq_t *handle, int port)
{
    struct soft_seq *s;
    int result = -ENOENT;
    pthread_mutex_lock(&mutex);
    s = lookup(handle);
    if (!s) { pthread_mutex_unlock(&mutex); FORWARD(snd_seq_delete_simple_port, (handle, port)); }
    if (port == s->output_port) { stop_synth(s); s->output_port = -1; result = 0; }
    pthread_mutex_unlock(&mutex);
    return result;
}

int snd_seq_connect_to(snd_seq_t *handle, int port, int client, int dest)
{
    struct soft_seq *s;
    int result;
    pthread_mutex_lock(&mutex);
    s = lookup(handle);
    if (!s) { pthread_mutex_unlock(&mutex); FORWARD(snd_seq_connect_to, (handle, port, client, dest)); }
    result = port == s->output_port && client == 128 && dest == 0 ? 0 : -ENOENT;
    pthread_mutex_unlock(&mutex);
    return result;
}

int snd_seq_event_output_direct(snd_seq_t *handle, snd_seq_event_t *ev)
{
    struct soft_seq *s;
    int result = FLUID_OK;
    pthread_mutex_lock(&mutex);
    s = lookup(handle);
    if (!s) { pthread_mutex_unlock(&mutex); FORWARD(snd_seq_event_output_direct, (handle, ev)); }
    if (!ev || !s->synth || ev->source.port != s->output_port) { pthread_mutex_unlock(&mutex); return -EINVAL; }
    switch (ev->type) {
    case SND_SEQ_EVENT_NOTEON:
        result = fluid_synth_noteon(s->synth, ev->data.note.channel, ev->data.note.note, ev->data.note.velocity);
        if (result == FLUID_OK && ev->data.note.velocity && !s->audio) {
            s->audio = new_fluid_audio_driver(s->settings, s->synth);
            if (!s->audio) result = FLUID_FAILED;
        }
        break;
    case SND_SEQ_EVENT_NOTEOFF: result = fluid_synth_noteoff(s->synth, ev->data.note.channel, ev->data.note.note); break;
    case SND_SEQ_EVENT_KEYPRESS: result = fluid_synth_key_pressure(s->synth, ev->data.note.channel, ev->data.note.note, ev->data.note.velocity); break;
    case SND_SEQ_EVENT_CONTROLLER: result = fluid_synth_cc(s->synth, ev->data.control.channel, ev->data.control.param, ev->data.control.value); break;
    case SND_SEQ_EVENT_PGMCHANGE: result = fluid_synth_program_change(s->synth, ev->data.control.channel, ev->data.control.value); break;
    case SND_SEQ_EVENT_CHANPRESS: result = fluid_synth_channel_pressure(s->synth, ev->data.control.channel, ev->data.control.value); break;
    case SND_SEQ_EVENT_PITCHBEND: result = fluid_synth_pitch_bend(s->synth, ev->data.control.channel, ev->data.control.value + 8192); break;
    case SND_SEQ_EVENT_SYSEX: {
        const unsigned char *data = ev->data.ext.ptr;
        unsigned len = ev->data.ext.len;
        int handled = 0;
        if (!data || len < 2 || len > 1024 * 1024 || data[0] != 0xf0 || data[len - 1] != 0xf7) {
            result = FLUID_FAILED; break;
        }
        result = fluid_synth_sysex(s->synth, (const char *)data + 1, (int)len - 2, NULL, NULL, &handled, 0);
        break;
    }
    case SND_SEQ_EVENT_RESET: result = fluid_synth_system_reset(s->synth); break;
    /* External transport clock messages do not control this tone generator. */
    case SND_SEQ_EVENT_CLOCK: case SND_SEQ_EVENT_START: case SND_SEQ_EVENT_CONTINUE:
    case SND_SEQ_EVENT_STOP: case SND_SEQ_EVENT_SENSING: case SND_SEQ_EVENT_TUNE_REQUEST: break;
    default: result = FLUID_FAILED; break;
    }
    s->events++;
    pthread_mutex_unlock(&mutex);
    return result == FLUID_OK ? (int)sizeof(*ev) : -EINVAL;
}
