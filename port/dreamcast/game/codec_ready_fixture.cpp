// CODEC_READY_FIXTURE=1 (test builds with DBG_WARP=1 only; compiled out of every other image): the
// deterministic external-ready contract for the source codec call (ss_term.cpp SsTermMain::OpeMesMove).
// One explicit fixture file, /cd/dc/codec_ready.txt ("K <n>", 1..30), required while the knob is on, is
// read through the existing fixture reader (os.cpp re4dc_fixture_read) at the first request.
//
// Ledger (one line each, the tick is pG->Frame_cnt):
//   "codec ready: request #n mdt=<m> id=<handle> tick=<t> release=<t+K> K=<K>"  (or "... failed id=0")
//   "codec ready: actual #n first ready tick=<t> (request+<d>)"              actual timing; may differ by arm
//   "codec ready: release #n tick=<t> (request+<K>) actual_first=<t>"
//   "codec ready: cancel #n tick=<t> (unreleased)"
//   "codec ready: FAIL #n <why> ..."  then re4dc_missing() halts the run.
//
// Only that poll is gated. Other stream status reads, the audio thread, callbacks, movies and source logic
// are unchanged, and readiness is never reported unless the stream's actual status is ready.
#include <stdlib.h>
#include <string.h>
#include "re4dc_platform.h"
#include "codec_ready_gate.h"

extern "C" int re4dc_fixture_read(const char* path, char* buffer, unsigned size);   // platform/os.cpp
extern "C" unsigned re4dc_fixture_source_frame(void);                             // ui_bridge.cpp: Frame_cnt

namespace {
CodecReadyGate g_gate;
bool g_loaded;

void load()
{
    if (g_loaded) return;
    g_loaded = true;
    char t[64];
    memset(t, 0, sizeof(t));
    const int n = re4dc_fixture_read("/cd/dc/codec_ready.txt", t, sizeof(t) - 1);
    unsigned long k = 0;
    if (n > 0 && t[0] == 'K' && t[1] == ' ') k = strtoul(t + 2, NULL, 10);
    if (k < 1 || k > 30) {
        re4dc_log("codec ready: FAIL config /cd/dc/codec_ready.txt read=%d (need \"K <1..30>\")\n", n);
        re4dc_missing("codec ready fixture: /cd/dc/codec_ready.txt missing or invalid");
    }
    g_gate.init((unsigned) k);
    re4dc_log("codec ready: fixture K=%u (CODEC_READY_FIXTURE)\n", (unsigned) k);
}
}  // namespace

extern "C" unsigned re4dc_codec_ready_request(int mdt, unsigned handle)
{
    load();
    const unsigned tick = re4dc_fixture_source_frame();
    if (g_gate.request(tick, handle))
        re4dc_log("codec ready: request #%u mdt=%d id=%u tick=%u release=%u K=%u\n", g_gate.requests, mdt, handle, tick,
                  g_gate.deadline, g_gate.k);
    else
        re4dc_log("codec ready: request #%u mdt=%d failed id=0 tick=%u (source: no ready wait)\n", g_gate.requests, mdt,
                  tick);
    return handle;
}

extern "C" int re4dc_codec_ready_poll(unsigned handle, int actual)
{
    load();
    const unsigned tick = re4dc_fixture_source_frame();
    const bool seen = g_gate.first_ready != CodecReadyGate::kNone;
    const CodecReadyGate::Result r = g_gate.poll(tick, handle, actual);
    if (!seen && g_gate.first_ready != CodecReadyGate::kNone)
        re4dc_log("codec ready: actual #%u first ready tick=%u (request+%u)\n", g_gate.requests, g_gate.first_ready,
                  g_gate.first_ready - g_gate.req_tick);
    switch (r) {
    case CodecReadyGate::HOLD:
        return 0;
    case CodecReadyGate::DELIVER:
        re4dc_log("codec ready: release #%u tick=%u (request+%u) actual_first=%u\n", g_gate.requests, tick, g_gate.k,
                  g_gate.first_ready);
        return actual;
    default:
        break;
    }
    static const char* const why[] = {"", "", "late: actual not ready at the scheduled poll",
                                       "missed: no poll at the scheduled tick", "poll without an armed request",
                                       "poll of a different stream handle"};
    re4dc_log("codec ready: FAIL #%u %s tick=%u request=%u release=%u id=%u/%u actual=%d\n", g_gate.requests, why[r],
              tick, g_gate.req_tick, g_gate.deadline, handle, g_gate.id, actual);
    re4dc_missing("codec ready fixture: ledger failure (see codec ready: FAIL)");
    return actual;   // not reached (re4dc_missing halts); the actual status, never a manufactured one
}

extern "C" void re4dc_codec_ready_cancel(unsigned handle)
{
    if (!g_loaded) return;
    if (g_gate.cancel(handle))
        re4dc_log("codec ready: cancel #%u tick=%u (unreleased)\n", g_gate.requests, re4dc_fixture_source_frame());
}
