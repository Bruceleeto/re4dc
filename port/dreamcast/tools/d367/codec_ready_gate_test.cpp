// Host test of the CODEC_READY_FIXTURE scheduling rule (port/dreamcast/game/codec_ready_gate.h).
//   g++ -std=c++11 -Wall -Werror -I port/dreamcast/game tools/d367/codec_ready_gate_test.cpp -o /tmp/crg && /tmp/crg
// Each case drives the gate the way SsTermMain::OpeMesMove does: one request, then one poll per tick with the
// actual SndStrStatusCk(str, 2) result. The negative cases must fail and never report ready.
#include <stdio.h>
#include "codec_ready_gate.h"

static int g_fail;
#define CHECK(c)                                                         \
    do {                                                                 \
        if (!(c)) {                                                      \
            printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c);           \
            ++g_fail;                                                    \
        }                                                                \
    } while (0)

typedef CodecReadyGate G;

// actual ready from `ready_at` on; polls every tick from request+1 until the gate stops holding.
static G::Result run(G& g, unsigned req, unsigned id, unsigned ready_at, unsigned* end_tick)
{
    g.request(req, id);
    for (unsigned t = req + 1; t < req + 100; ++t) {
        const G::Result r = g.poll(t, id, t >= ready_at);
        if (r != G::HOLD) {
            *end_tick = t;
            return r;
        }
    }
    *end_tick = 0;
    return G::HOLD;
}

int main()
{
    unsigned end;
    G g;

    // Ready early (natural +2): held until request+K, delivered exactly there; first actual logged.
    g.init(5);
    CHECK(run(g, 771, 0x31, 773, &end) == G::DELIVER);
    CHECK(end == 776 && g.first_ready == 773 && g.state == G::RELEASED);

    // Ready exactly at the scheduled poll.
    g.init(5);
    CHECK(run(g, 100, 7, 105, &end) == G::DELIVER);
    CHECK(end == 105 && g.first_ready == 105);

    // Late completion: not ready at request+K. FAIL_LATE at that poll, nothing reported ready before it.
    g.init(5);
    g.request(100, 7);
    for (unsigned t = 101; t < 105; ++t) CHECK(g.poll(t, 7, 0) == G::HOLD);
    CHECK(g.poll(105, 7, 0) == G::FAIL_LATE);
    CHECK(g.state == G::FAILED && g.first_ready == G::kNone);
    // A failed gate stays failed: a later ready poll is not turned into a success (no retry, no moved deadline).
    CHECK(g.poll(106, 7, 1) == G::FAIL_UNARMED);

    // Missing completion forever: same FAIL_LATE at the deadline (never a hold beyond it).
    g.init(4);
    CHECK(run(g, 10, 3, 1000, &end) == G::FAIL_LATE);
    CHECK(end == 14);

    // Missed scheduled poll (the source skipped tick request+K): FAIL_MISSED, even though actual is ready.
    g.init(5);
    g.request(100, 7);
    CHECK(g.poll(102, 7, 1) == G::HOLD);
    CHECK(g.poll(106, 7, 1) == G::FAIL_MISSED);
    CHECK(g.state == G::FAILED);

    // Cancellation (stream stopped while armed): ends unreleased; a poll after it fails; a new request re-arms
    // with a fresh deadline and a fresh first-ready.
    g.init(5);
    g.request(200, 9);
    CHECK(g.poll(201, 9, 1) == G::HOLD && g.first_ready == 201);
    CHECK(g.cancel(9) == true);
    CHECK(g.state == G::IDLE);
    CHECK(g.poll(202, 9, 1) == G::FAIL_UNARMED);
    CHECK(run(g, 300, 11, 302, &end) == G::DELIVER);
    CHECK(end == 305 && g.first_ready == 302 && g.requests == 2);
    // Cancel after release (normal stop at the sequence end) is not an unreleased cancel.
    CHECK(g.cancel(11) == false && g.state == G::IDLE);

    // Re-request while armed resets the deadline (each request is its own contract).
    g.init(5);
    g.request(400, 1);
    CHECK(g.poll(401, 1, 1) == G::HOLD);
    g.request(402, 2);
    CHECK(g.first_ready == G::kNone && g.deadline == 407);
    CHECK(g.poll(406, 2, 1) == G::HOLD);
    CHECK(g.poll(407, 2, 1) == G::DELIVER);

    // Failed request (handle 0): arms nothing (the source skips its wait because str == 0).
    g.init(5);
    CHECK(g.request(500, 0) == false && g.state == G::IDLE);

    // Poll of another handle while armed: FAIL_ID, not a delivery.
    g.init(5);
    g.request(600, 5);
    CHECK(g.poll(605, 6, 1) == G::FAIL_ID);

    // Unarmed poll (no request seen): FAIL_UNARMED.
    g.init(5);
    CHECK(g.poll(1, 5, 1) == G::FAIL_UNARMED);

    // Exhaustive: for every K 1..8 and ready offset 0..12, the gate reports ready only at request+K and only
    // when actual is ready there; otherwise it fails at request+K.
    for (unsigned k = 1; k <= 8; ++k)
        for (unsigned d = 0; d <= 12; ++d) {
            g.init(k);
            g.request(1000, 42);
            for (unsigned t = 1001; t <= 1000 + k; ++t) {
                const int actual = t >= 1000 + d;
                const G::Result r = g.poll(t, 42, actual);
                if (t < 1000 + k) CHECK(r == G::HOLD);
                else CHECK(r == (actual ? G::DELIVER : G::FAIL_LATE));
            }
        }

    if (g_fail) {
        printf("codec_ready_gate_test: %d FAILED\n", g_fail);
        return 1;
    }
    printf("codec_ready_gate_test: all passed\n");
    return 0;
}
