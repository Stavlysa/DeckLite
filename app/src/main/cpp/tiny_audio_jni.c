/*
 * tiny_audio_jni.c -- This file is part of tiny_container.
 *
 * Copyright (C) 2026 Caten Hu
 *
 * Tiny Container is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published
 * by the Free Software Foundation, either version 3 of the License,
 * or any later version.
 *
 * Tiny Container is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty
 * of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see http://www.gnu.org/licenses/.
 */

/*
 * tiny_audio_jni.c – Native implementation for TinyAudio (Android playback)
 *
 * Architecture:
 *   [Socket reader thread]  ──ringbuffer──>  [AAudio data callback]
 *         ↑                                        ↓
 *   Unix domain socket                     AAudio OUTPUT device
 *
 * Uses AAudio data callback for output.  AAudio calls the callback
 * on a high-priority thread exactly when it needs data – no polling,
 * no blocking writes, no data loss.
 *
 * Socket I/O: NDK <sys/socket.h> / <sys/un.h>
 * Audio I/O:  NDK <aaudio/AAudio.h>
 */

#include <jni.h>
#include <android/log.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/un.h>

#include <aaudio/AAudio.h>

#define LOG_TAG "TinyAudio-JNI"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

/* ================================================================= */
/*  SPSC ringbuffer (single-producer, single-consumer, lock-free)    */
/* ================================================================= */
#define RING_SIZE               (768u * 1024u) /* 2 s @ 48 kHz F32 stereo */
#define PREBUFFER_FRAMES        4096u          /* 85 ms @ 48 kHz */
#define RING_LATENCY_FRAMES     8192u          /* 171 ms @ 48 kHz */
#define AAUDIO_BUFFER_BURSTS    8

typedef struct {
    uint8_t     buf[RING_SIZE];
    atomic_uint write_idx;
    atomic_uint read_idx;
} ring_t;

static void ring_init(ring_t *r)     { atomic_init(&r->write_idx,0); atomic_init(&r->read_idx,0); }

static uint32_t ring_available(ring_t *r)
{
    uint32_t rd = atomic_load_explicit(&r->read_idx, memory_order_relaxed);
    uint32_t w  = atomic_load_explicit(&r->write_idx, memory_order_acquire);
    return w - rd;
}

static uint32_t ring_write(ring_t *r, const uint8_t *src, uint32_t n,
                           uint32_t latency_limit)
{
    uint32_t w  = atomic_load_explicit(&r->write_idx, memory_order_relaxed);
    uint32_t rd = atomic_load_explicit(&r->read_idx,  memory_order_acquire);
    uint32_t used = w - rd;

    /*
     * Latency guard: if the ringbuffer has accumulated too much data,
     * the consumer (AAudio) has fallen behind.  Skip old frames so the
     * listener doesn't experience growing end-to-end delay.
     */
    if (used > latency_limit) {
        uint32_t new_rd = w - latency_limit;
        LOGI("ring: latency guard skip %u bytes", new_rd - rd);
        atomic_store_explicit(&r->read_idx, new_rd, memory_order_release);
        rd  = new_rd;
        used = latency_limit;
    }

    uint32_t space = RING_SIZE - used;
    if (n > space) n = space;
    if (!n) return 0;
    uint32_t off = w % RING_SIZE, c0 = RING_SIZE - off;
    if (c0 > n) c0 = n;
    memcpy(r->buf + off, src, c0);
    if (n > c0) memcpy(r->buf, src + c0, n - c0);
    atomic_store_explicit(&r->write_idx, w + n, memory_order_release);
    return n;
}

static uint32_t ring_read(ring_t *r, uint8_t *dst, uint32_t n)
{
    uint32_t rd = atomic_load_explicit(&r->read_idx,  memory_order_relaxed);
    uint32_t w  = atomic_load_explicit(&r->write_idx, memory_order_acquire);
    uint32_t avail = w - rd;
    if (n > avail) n = avail;
    if (!n) return 0;
    uint32_t off = rd % RING_SIZE, c0 = RING_SIZE - off;
    if (c0 > n) c0 = n;
    memcpy(dst, r->buf + off, c0);
    if (n > c0) memcpy(dst + c0, r->buf, n - c0);
    atomic_store_explicit(&r->read_idx, rd + n, memory_order_release);
    return n;
}

/* ================================================================= */
/*  State                                                            */
/* ================================================================= */
typedef struct {
    ring_t        ring;
    atomic_bool   running;
    atomic_bool   stream_started;
    atomic_bool   prebuffering;
    atomic_bool   aaudio_restart;
    atomic_uint   underrun_count;

    int32_t       sample_rate;
    int32_t       channel_count;
    int32_t       bytes_per_frame;
    uint32_t      prebuffer_bytes;
    uint32_t      latency_limit_bytes;
    uint32_t      reported_underruns;

    int           sock_fd;
    pthread_t     sock_thread;
    AAudioStream *stream;      /* owned by AAudio's callback context */
} st_t;

static st_t g;

/* ================================================================= */
/*  Socket helpers                                                   */
/* ================================================================= */
static int sock_read_exact(int fd, void *buf, size_t n)
{
    uint8_t *p = buf; size_t rem = n;
    while (rem) { ssize_t r = read(fd,p,rem); if (r<=0) return r==0?-1:(errno==EINTR?0:-1); p+=r; rem-=r; }
    return 0;
}
static uint32_t read_le32(const uint8_t *p) { return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24); }

static int connect_unix(const char *path)
{
    struct sockaddr_un a; int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd<0) return -1;
    memset(&a,0,sizeof(a)); a.sun_family=AF_UNIX;
    strncpy(a.sun_path,path,sizeof(a.sun_path)-1);
    if (connect(fd,(struct sockaddr*)&a,sizeof(a))<0) { close(fd); return -1; }
    LOGI("connected %s",path);
    return fd;
}

/* ================================================================= */
/*  AAudio output data callback                                      */
/*  (AAudio calls this when it needs audio – the only correct way)   */
/* ================================================================= */
static aaudio_data_callback_result_t out_cb(
        AAudioStream *s, void *ud, void *buf, int32_t nframes)
{
    (void)s; (void)ud;

    if (!atomic_load_explicit(&g.running, memory_order_acquire))
        return AAUDIO_CALLBACK_RESULT_STOP;

    int32_t bpf = g.bytes_per_frame;
    uint32_t want = (uint32_t)nframes * (uint32_t)bpf;

    /* After an underrun, hold silence until a useful amount of audio has
     * accumulated.  Resuming on the next tiny packet would create a rapid
     * play/silence cycle which is heard as stuttering. */
    if (atomic_load_explicit(&g.prebuffering, memory_order_acquire)) {
        if (ring_available(&g.ring) < g.prebuffer_bytes) {
            memset(buf, 0, want);
            return AAUDIO_CALLBACK_RESULT_CONTINUE;
        }
        atomic_store_explicit(&g.prebuffering, false, memory_order_release);
    }

    uint32_t got  = ring_read(&g.ring, (uint8_t*)buf, want);

    /* If underrun, pad with silence (zeroes) – memcpy won't touch tail */
    if (got < want) {
        memset((uint8_t*)buf + got, 0, want - got);
        atomic_fetch_add_explicit(&g.underrun_count, 1, memory_order_relaxed);
        atomic_store_explicit(&g.prebuffering, true, memory_order_release);
    }

    return AAUDIO_CALLBACK_RESULT_CONTINUE;
}

static void err_cb(AAudioStream *s, void *ud, aaudio_result_t e)
{
    (void)s; (void)ud;
    if (e == AAUDIO_ERROR_DISCONNECTED) {
        LOGI("AAudio disconnect → restart");
        atomic_store_explicit(&g.aaudio_restart, true, memory_order_release);
    } else LOGE("AAudio err: %d", (int)e);
}

/* ================================================================= */
/*  Stream lifecycle (called ONLY from socket thread)                */
/* ================================================================= */
static void stream_close(void) {
    if (g.stream) { AAudioStream_close(g.stream); g.stream = NULL; }
    atomic_store_explicit(&g.stream_started, false, memory_order_release);
    atomic_store_explicit(&g.prebuffering, true, memory_order_release);
}

static int stream_open(int32_t rate, int32_t ch)
{
    AAudioStreamBuilder *b = NULL;
    AAudioStream *s = NULL;
    aaudio_result_t r;

    stream_close();

    r = AAudio_createStreamBuilder(&b);
    if (r) return -1;

    AAudioStreamBuilder_setDirection(b, AAUDIO_DIRECTION_OUTPUT);
    AAudioStreamBuilder_setPerformanceMode(b, AAUDIO_PERFORMANCE_MODE_LOW_LATENCY);
    AAudioStreamBuilder_setSharingMode(b, AAUDIO_SHARING_MODE_EXCLUSIVE);
    AAudioStreamBuilder_setFormat(b, AAUDIO_FORMAT_PCM_FLOAT);
    AAudioStreamBuilder_setSampleRate(b, rate);
    AAudioStreamBuilder_setChannelCount(b, ch);
    AAudioStreamBuilder_setDataCallback(b, out_cb, NULL);
    AAudioStreamBuilder_setErrorCallback(b, err_cb, NULL);

    r = AAudioStreamBuilder_openStream(b, &s);
    AAudioStreamBuilder_delete(b);

    if (r) {
        /* fallback: shared */
        AAudio_createStreamBuilder(&b);
        AAudioStreamBuilder_setDirection(b, AAUDIO_DIRECTION_OUTPUT);
        AAudioStreamBuilder_setPerformanceMode(b, AAUDIO_PERFORMANCE_MODE_LOW_LATENCY);
        AAudioStreamBuilder_setSharingMode(b, AAUDIO_SHARING_MODE_SHARED);
        AAudioStreamBuilder_setFormat(b, AAUDIO_FORMAT_PCM_FLOAT);
        AAudioStreamBuilder_setSampleRate(b, rate);
        AAudioStreamBuilder_setChannelCount(b, ch);
        AAudioStreamBuilder_setDataCallback(b, out_cb, NULL);
        AAudioStreamBuilder_setErrorCallback(b, err_cb, NULL);
        r = AAudioStreamBuilder_openStream(b, &s);
        AAudioStreamBuilder_delete(b);
    }
    if (r) { LOGE("openStream: %d", (int)r); return -1; }
    if (AAudioStream_getFormat(s) != AAUDIO_FORMAT_PCM_FLOAT) { AAudioStream_close(s); return -1; }

    g.stream = s;
    g.sample_rate   = AAudioStream_getSampleRate(s);
    g.channel_count = AAudioStream_getChannelCount(s);
    g.bytes_per_frame = g.channel_count * (int32_t)sizeof(float);
    g.prebuffer_bytes = PREBUFFER_FRAMES * (uint32_t)g.bytes_per_frame;
    g.latency_limit_bytes = RING_LATENCY_FRAMES * (uint32_t)g.bytes_per_frame;

    int32_t burst = AAudioStream_getFramesPerBurst(s);
    int32_t capacity = AAudioStream_getBufferCapacityInFrames(s);
    int32_t requested = burst > 0 ? burst * AAUDIO_BUFFER_BURSTS : capacity;
    if (capacity > 0 && requested > capacity) requested = capacity;
    int32_t actual = requested > 0
            ? AAudioStream_setBufferSizeInFrames(s, requested)
            : AAudioStream_getBufferSizeInFrames(s);

    LOGI("AAudio OUT open: rate=%d ch=%d burst=%d capacity=%d buffer=%d prebuffer=%u",
         (int)g.sample_rate, (int)g.channel_count, (int)burst, (int)capacity,
         (int)actual, g.prebuffer_bytes);
    return 0;
}

static int stream_start_if_ready(void)
{
    if (!g.stream || atomic_load_explicit(&g.stream_started, memory_order_acquire))
        return 0;
    if (ring_available(&g.ring) < g.prebuffer_bytes)
        return 0;

    atomic_store_explicit(&g.prebuffering, false, memory_order_release);
    aaudio_result_t r = AAudioStream_requestStart(g.stream);
    if (r) {
        atomic_store_explicit(&g.prebuffering, true, memory_order_release);
        LOGE("requestStart: %d", (int)r);
        return -1;
    }
    atomic_store_explicit(&g.stream_started, true, memory_order_release);
    LOGI("AAudio OUT started with %u buffered bytes", ring_available(&g.ring));
    return 0;
}

/* ================================================================= */
/*  Socket reader thread                                             */
/* ================================================================= */
static void *sock_func(void *arg)
{
    (void)arg;
    int fd = g.sock_fd;

    /* 1. Read format header */
    uint8_t hdr[12];
    if (sock_read_exact(fd, hdr, sizeof(hdr)) < 0) goto out;
    g.sample_rate   = (int32_t)read_le32(hdr+0);
    g.channel_count = (int32_t)read_le32(hdr+4);
    LOGI("fmt: rate=%d ch=%d", (int)g.sample_rate, (int)g.channel_count);

    /* 2. Open AAudio.  Starting is delayed until PREBUFFER_FRAMES are ready;
     * Wine/PRoot scheduling is bursty enough that an immediately-started
     * low-latency callback otherwise begins with repeated underruns. */
    if (stream_open(g.sample_rate, g.channel_count) < 0) { LOGE("AAudio fail"); goto out; }

    /* 3. Read PCM → ringbuffer */
    uint8_t buf[16384];
    while (atomic_load_explicit(&g.running, memory_order_acquire)) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0) { if (n<0 && errno==EINTR) continue; break; }
        ring_write(&g.ring, buf, (uint32_t)n, g.latency_limit_bytes);
        if (stream_start_if_ready() < 0) break;

        uint32_t underruns = atomic_load_explicit(&g.underrun_count,
                                                  memory_order_relaxed);
        if (underruns != g.reported_underruns &&
                (g.reported_underruns == 0 || underruns - g.reported_underruns >= 10)) {
            LOGI("AAudio underruns=%u; rebuffering=%d", underruns,
                 atomic_load_explicit(&g.prebuffering, memory_order_relaxed));
            g.reported_underruns = underruns;
        }

        /* Handle AAudio restart – drain ringbuffer BEFORE opening new stream.
         * If we don't drain, the new stream plays through old buffered data,
         * causing the "latency after plug/unplug" problem. */
        if (atomic_exchange_explicit(&g.aaudio_restart, false, memory_order_acq_rel)) {
            int32_t sr = g.sample_rate > 0 ? g.sample_rate : 48000;
            int32_t ch = g.channel_count > 0 ? g.channel_count : 2;

            /* Close old stream first (stops its data callback). */
            stream_close();

            /* Abandon old ringbuffer data – start from "now". */
            {
                uint32_t w = atomic_load_explicit(&g.ring.write_idx,
                                                  memory_order_acquire);
                uint32_t rd = atomic_load_explicit(&g.ring.read_idx,
                                                   memory_order_relaxed);
                LOGI("restart: draining %u ringbuffer bytes", w - rd);
                atomic_store_explicit(&g.ring.read_idx, w,
                                      memory_order_release);
            }

            LOGI("restart AAudio: rate=%d ch=%d", (int)sr, (int)ch);
            stream_open(sr, ch);
        }
    }

    out:
    atomic_store_explicit(&g.running, false, memory_order_release);
    stream_close();
    LOGI("sock thread end");
    return NULL;
}

/* ================================================================= */
/*  JNI                                                              */
/* ================================================================= */
JNIEXPORT jboolean JNICALL
Java_com_fct_tc4_TinyAudio_nativeStart(JNIEnv *env, jclass cls, jstring sp)
{
    (void)cls;
    const char *p = (*env)->GetStringUTFChars(env, sp, NULL);
    if (!p) return JNI_FALSE;

    memset(&g, 0, sizeof(g));
    g.sock_fd = -1;
    ring_init(&g.ring);
    atomic_init(&g.running, true);
    atomic_init(&g.stream_started, false);
    atomic_init(&g.prebuffering, true);
    atomic_init(&g.aaudio_restart, false);
    atomic_init(&g.underrun_count, 0);

    { int fd = connect_unix(p); g.sock_fd = fd; }
    (*env)->ReleaseStringUTFChars(env, sp, p);
    if (g.sock_fd < 0) return JNI_FALSE;

    if (pthread_create(&g.sock_thread, NULL, sock_func, NULL)) {
        close(g.sock_fd); g.sock_fd = -1; return JNI_FALSE;
    }
    return JNI_TRUE;
}

JNIEXPORT void JNICALL
Java_com_fct_tc4_TinyAudio_nativeStop(JNIEnv *env, jclass cls)
{
    (void)env; (void)cls;
    atomic_store_explicit(&g.running, false, memory_order_release);
    if (g.sock_fd >= 0) { shutdown(g.sock_fd, SHUT_RDWR); close(g.sock_fd); g.sock_fd = -1; }
    pthread_join(g.sock_thread, NULL);
}
