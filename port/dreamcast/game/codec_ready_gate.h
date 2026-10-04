// codec_ready_gate.h: the CODEC_READY_FIXTURE scheduling rule (test builds only), free of game and KOS types
// so tools/d367/codec_ready_gate_test.cpp can test it on the host.
//
// The source codec call (src/Sscrn/ss_term.cpp SsTermMain::OpeMesMove) requests its voice stream, then polls
// SndStrStatusCk(str, 2) once per tick until the stream is ready. On the port, "ready" is completed by the
// wall-clock audio thread. The fixture pins WHEN the source sees it: the poll at tick request + K returns the
// actual status, and every earlier poll returns "not ready".
// - It never reports ready when the actual status is not ready.
// - Actual not ready at that exact poll: FAIL_LATE.
// - A poll after the deadline (the scheduled poll never ran): FAIL_MISSED.
// The caller halts on either; nothing is retried or moved.
// A request that failed (handle 0) arms nothing; the source then skips its ready wait itself.
#pragma once

struct CodecReadyGate {
    enum State { IDLE, ARMED, RELEASED, FAILED };
    enum Result { HOLD = 0, DELIVER = 1, FAIL_LATE = 2, FAIL_MISSED = 3, FAIL_UNARMED = 4, FAIL_ID = 5 };
    State state;
    unsigned k;            // ticks from the request tick to the one poll that may deliver
    unsigned id;           // SndStrReq handle of the armed request
    unsigned req_tick;
    unsigned deadline;     // req_tick + k
    unsigned first_ready;  // first tick a poll saw the actual status ready, kNone if not yet
    unsigned requests;     // requests seen (ledger numbering)
    static const unsigned kNone = 0xFFFFFFFFu;

    void init(unsigned k_ticks)
    {
        state = IDLE;
        k = k_ticks;
        id = 0;
        req_tick = deadline = 0;
        first_ready = kNone;
        requests = 0;
    }
    // Each request resets the gate. Returns true when it armed (a valid handle).
    bool request(unsigned tick, unsigned handle)
    {
        ++requests;
        id = handle;
        req_tick = tick;
        deadline = tick + k;
        first_ready = kNone;
        state = handle ? ARMED : IDLE;
        return handle != 0;
    }
    // One source poll at `tick` of `handle`, with the actual SndStrStatusCk(handle, 2) result.
    Result poll(unsigned tick, unsigned handle, int actual)
    {
        if (state != ARMED) {
            state = FAILED;
            return FAIL_UNARMED;
        }
        if (handle != id) {
            state = FAILED;
            return FAIL_ID;
        }
        if (actual && first_ready == kNone) first_ready = tick;
        if (tick < deadline) return HOLD;
        if (tick > deadline) {
            state = FAILED;
            return FAIL_MISSED;
        }
        if (!actual) {
            state = FAILED;
            return FAIL_LATE;
        }
        state = RELEASED;
        return DELIVER;
    }
    // Stream stopped (skip, sequence end, START close) or a new op: an armed request ends unreleased.
    bool cancel(unsigned handle)
    {
        const bool was_armed = state == ARMED && handle == id;
        if (state == ARMED || state == RELEASED) state = IDLE;
        return was_armed;
    }
};
