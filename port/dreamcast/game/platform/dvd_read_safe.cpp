// DVD_READ_SAFE=1 (Phase 2 D4, default 0) and its test hook DVD_STUCK_TEST (default 0); built only with one of them.
//
// With the full test 7 data and the GC-bake r119 package, r119 after the boss logged "cdrom_stream_request: Previous
// DMA request is in progress" for every later disc stream request: 249 texture uploads failed and every tex.pak index
// re-read failed until the end of the run. The refusals never stop, so KOS's dma_in_progress flag (hardware/cdrom.c)
// is stuck, not briefly busy: once a stream command is running, the vblank handler leaves the flag alone (the command
// reports "streaming") and only a G1 DMA completion clears it. Which earlier request left it set depends on timing
// (the same configuration passes with the image a few hundred bytes larger).
//
// DVD_READ_SAFE=1 wraps cdrom_stream_start / cdrom_stream_request. A request KOS refuses (ERR_SYS) is retried for up
// to 10 ms (a genuine DMA would be done by then: fs_iso9660 serialises its reads and waits for each one); if it is
// still refused the flag is stale, so it is cleared the only public way, cdrom_abort_cmd(timeout, abort_dma=true),
// which aborts the stream command too (the G1 ATA semaphore is taken first: that abort path assumes it is held and
// signals it at the end). The stream is then started again where it stood (it is only restartable at a sector
// boundary of what was already handed out) and the request repeated. A request that succeeds the first time takes
// the old path, with one counter update.
//
// DVD_STUCK_TEST=<seconds> (test discs only, with DVD_STUCK_ADDR): sets the flag just before the first stream start after
// that much uptime: the stuck state on demand, with or without the fix.
#include <kos.h>
#include <dc/cdrom.h>

#include "re4dc_platform.h"

#ifndef RE4DC_DVD_READ_SAFE
#define RE4DC_DVD_READ_SAFE 0
#endif
#ifndef RE4DC_DVD_STUCK_TEST
#define RE4DC_DVD_STUCK_TEST 0
#endif

extern "C" int __real_cdrom_stream_start(int sector, int cnt, bool dma);
extern "C" int __real_cdrom_stream_request(void* buffer, size_t size, bool block);
extern "C" semaphore_t _g1_ata_sem;

namespace {
int s_sector, s_cnt;
bool s_dma;
size_t s_consumed;  // bytes requested from the current stream since its start
unsigned g_refused, g_recovered, g_failed;
#if RE4DC_DVD_STUCK_TEST
// Compile-time: DVD_STUCK_ADDR (address of KOS dma_in_progress from a first build's symbols; the value does not change
// the code size, so a second build keeps the address) and DVD_STUCK_TEST (seconds of uptime). No file reads here: this
// runs inside fs_iso9660 with its handle mutex held.
bool g_done;
void stuck_test()
{
    if (!g_done && timer_ms_gettime64() >= 1000ULL * RE4DC_DVD_STUCK_TEST) {
        g_done = true;
        *(volatile bool*) (uintptr_t) RE4DC_DVD_STUCK_ADDR = true;
        re4dc_log("dvd stuck test: dma_in_progress set before a stream start\n");
    }
}
#endif
}

extern "C" int __wrap_cdrom_stream_start(int sector, int cnt, bool dma)
{
#if RE4DC_DVD_STUCK_TEST
    stuck_test();
#endif
    s_sector = sector;
    s_cnt = cnt;
    s_dma = dma;
    s_consumed = 0;
    return __real_cdrom_stream_start(sector, cnt, dma);
}

extern "C" int __wrap_cdrom_stream_request(void* buffer, size_t size, bool block)
{
    int rv = __real_cdrom_stream_request(buffer, size, block);
    if (rv == ERR_OK) {
        s_consumed += size;
        return rv;
    }
#if RE4DC_DVD_READ_SAFE
    if (rv != ERR_SYS) return rv;
    ++g_refused;
    for (int i = 0; i < 5 && rv == ERR_SYS; ++i) {
        thd_sleep(2);
        rv = __real_cdrom_stream_request(buffer, size, block);
    }
    bool restarted = false;
    if (rv == ERR_SYS && sem_wait_timed(&_g1_ata_sem, 1000) == 0) {
        if (cdrom_abort_cmd(1000, true) == ERR_NO_ACTIVE) sem_signal(&_g1_ata_sem);  // took no ownership
        const size_t done_sectors = s_consumed / 2048;
        if (!(s_consumed % 2048) && (int) done_sectors < s_cnt &&
            __real_cdrom_stream_start(s_sector + (int) done_sectors, s_cnt - (int) done_sectors, s_dma) == ERR_OK) {
            s_sector += (int) done_sectors;
            s_cnt -= (int) done_sectors;
            s_consumed = 0;
            restarted = true;
            rv = __real_cdrom_stream_request(buffer, size, block);
        }
    }
    if (rv == ERR_OK) {
        s_consumed += size;
        ++g_recovered;
    } else {
        ++g_failed;
    }
    re4dc_log("dvd read safe: stream request refused, %s%s (%u bytes; refused %u recovered %u failed %u)\n",
              rv == ERR_OK ? "recovered" : "FAILED", restarted ? " after a stream restart" : "", (unsigned) size,
              g_refused, g_recovered, g_failed);
#endif
    return rv;
}
