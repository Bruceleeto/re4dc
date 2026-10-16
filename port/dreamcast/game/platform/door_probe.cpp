// DOOR_PROBE=1 (Makefile; lane doorpause16, 2026-10-16): where the door pause goes. Diagnostic, log only, default 0
// (this file is not built with the knob off). Needs DISC_READ_METER=1 (dvd_read_safe.cpp's game-read counters).
//
// A door window runs from the door press (sceAtFunc_door, or the door demo / stage init when nothing pressed) to the
// next room's first gameMainLoop frame. Each phase mark (RE4DC_DOORPH in game.cpp / stage.cpp / sce_at.cpp) logs,
// for the time since the previous mark:
//   dt   wall ms;
//   blk  ms the game threads (main + re4-task) spent inside GD-ROM drive calls, rd = those calls, kb = bytes;
//   cpu  ms of CPU per thread class from KOS's per-thread accounting (thd cpu_time, ms ticks): main ([kernel], the
//        game loop), task (re4-task source threads), oth (sound, stream, other KOS threads), idle ([idle]: nothing
//        runnable, i.e. waiting on the drive's DMA or on the next vblank).
// At the end: "DOORPH: end" (totals), the files read in the window ("DOORFILE:", from fs_open / fs_read wraps:
// calls, KB, wall us inside fs_read, the phase of the first read) and the CPU per thread label ("DOORTHD:").
// Nothing here changes what is read or when; the wraps only time the calls.
#include <kos.h>
#include <string.h>

#include "re4dc_platform.h"
#include "door_probe.h"

extern "C" {
ssize_t __real_fs_read(file_t hnd, void* buffer, size_t cnt);
file_t __real_fs_open(const char* fn, int mode);
void re4dc_disc_meter_totals(unsigned* reads, unsigned long long* bytes, unsigned long long* block_us);  // dvd_read_safe.cpp
}

namespace {
struct Cpu { unsigned long long main, task, oth, idle; };
struct Snap { unsigned long long t_us, bytes, block_us, spin_us, spin_ms; unsigned reads; Cpu cpu; };
struct FileRow { char path[28]; unsigned n, bytes, us; const char* first; };
struct ThdRow { char label[16]; unsigned long long ms0, ms; };
constexpr unsigned kFiles = 128, kHandles = 32, kThds = 16;

FileRow files[kFiles]; unsigned nfiles, dropped;
char names[kHandles][28];   // the path tail of each open handle (fs_open)
struct Handle { file_t fd; short row1; } handles[kHandles];
ThdRow thds[kThds]; unsigned nthds;
bool active;
Snap s0, prev;
const char* cur_mark = "-";
unsigned from_room, marks;
unsigned long long spin_us, spin_t0;   // main loop vblank spin (main.cpp): wall time of the busy waits
unsigned long long spin_ms, spin_c0;   // and the main thread's own CPU in them (KOS ms accounting): tasks (prio 15) preempt it

unsigned long long thd_ms(kthread_t* t)
{
    unsigned long long ms = thd_get_cpu_time(t);
    if (t == thd_current) {
        const unsigned long long now = timer_ms_gettime64();
        if (now > t->cpu_time.scheduled) ms += now - t->cpu_time.scheduled;
    }
    return ms;
}

int cpu_cb(kthread_t* t, void* u)
{
    Cpu* c = (Cpu*) u;
    const unsigned long long ms = thd_ms(t);
    const char* l = t->label;
    if (!strcmp(l, "[idle]")) c->idle += ms;
    else if (!strcmp(l, "[kernel]")) c->main += ms;
    else if (!strncmp(l, "re4-task", 8)) c->task += ms;
    else c->oth += ms;
    return 0;
}

// Per-label table for the end summary (ms0 at the window start).
int thd_cb(kthread_t* t, void* u)
{
    const bool start = u != nullptr;
    const char* l = t->label[0] ? t->label : "?";
    ThdRow* r = nullptr;
    for (unsigned i = 0; i < nthds; ++i) if (!strncmp(thds[i].label, l, 15)) { r = &thds[i]; break; }
    if (!r) {
        if (!start || nthds == kThds) return 0;
        r = &thds[nthds++];
        strncpy(r->label, l, 15); r->label[15] = 0;
        r->ms0 = r->ms = 0;
    }
    if (start) r->ms0 += thd_ms(t); else r->ms += thd_ms(t);
    return 0;
}

void snap(Snap& s)
{
    s.t_us = timer_us_gettime64();
    re4dc_disc_meter_totals(&s.reads, &s.bytes, &s.block_us);
    s.spin_us = spin_us;
    s.spin_ms = spin_ms;
    s.cpu = Cpu{};
    const int o = irq_disable();
    thd_each(cpu_cb, &s.cpu);
    irq_restore(o);
}

unsigned ms(unsigned long long a, unsigned long long b) { return a > b ? (unsigned) (a - b) : 0u; }

void start(const char* why, unsigned room)
{
    const int o = irq_disable();
    nfiles = 0; dropped = 0; nthds = 0; marks = 0;
    thd_each(thd_cb, (void*) 1);
    irq_restore(o);
    snap(s0);
    prev = s0;
    active = true;
    from_room = room;
    re4dc_log("DOORPH: start why=%s room=%03x\n", why, from_room);
}

int file_row(const char* fn)
{
    const size_t len = strlen(fn);
    const char* tail = len > 27 ? fn + len - 27 : fn;
    for (unsigned i = 0; i < nfiles; ++i) if (!strcmp(files[i].path, tail)) return (int) i;
    if (nfiles == kFiles) { ++dropped; return -1; }
    FileRow* f = &files[nfiles];
    memset(f, 0, sizeof(*f));
    strcpy(f->path, tail);
    f->first = cur_mark;
    return (int) nfiles++;
}
}  // namespace

extern "C" file_t __wrap_fs_open(const char* fn, int mode)
{
    const file_t fd = __real_fs_open(fn, mode);
    if (fd < 0 || !fn) return fd;
    const int o = irq_disable();
    Handle* slot = nullptr;
    for (auto& h : handles) if (h.row1 && h.fd == fd) { slot = &h; break; }
    if (!slot) for (auto& h : handles) if (!h.row1) { slot = &h; break; }
    if (!slot) slot = &handles[(unsigned) fd % kHandles];
    slot->fd = fd;
    // the row is made at the first read inside a window; until then the handle keeps its path tail (row1 < 0)
    const size_t len = strlen(fn);
    const unsigned k = (unsigned) (slot - handles);
    strncpy(names[k], len > 27 ? fn + len - 27 : fn, 27);
    names[k][27] = 0;
    slot->row1 = (short) (-(int) k - 1);
    irq_restore(o);
    return fd;
}

extern "C" ssize_t __wrap_fs_read(file_t hnd, void* buffer, size_t cnt)
{
    if (!active) return __real_fs_read(hnd, buffer, cnt);
    const unsigned long long t0 = timer_us_gettime64();
    const ssize_t r = __real_fs_read(hnd, buffer, cnt);
    const unsigned us = (unsigned) (timer_us_gettime64() - t0);
    const int o = irq_disable();
    for (auto& h : handles) {
        if (!h.row1 || h.fd != hnd) continue;
        if (h.row1 < 0) {
            const int row = file_row(names[-h.row1 - 1]);
            if (row < 0) break;
            h.row1 = (short) (row + 1);
        }
        FileRow& f = files[h.row1 - 1];
        ++f.n; f.us += us; f.bytes += r > 0 ? (unsigned) r : 0u;
        break;
    }
    irq_restore(o);
    return r;
}

extern "C" void re4dc_doorspin(int end)
{
    if (!active) return;
    if (!end) { spin_t0 = timer_us_gettime64(); spin_c0 = thd_ms(thd_current); return; }
    if (spin_t0) { spin_us += timer_us_gettime64() - spin_t0; spin_ms += thd_ms(thd_current) - spin_c0; }
    spin_t0 = 0;
}

extern "C" void re4dc_doorph(const char* mark, unsigned room)
{
    if (!active) {
        // a window starts at the door press; without one (warp jump, title, continue) at the door demo or stage init
        if (strcmp(mark, "press") && strcmp(mark, "demo") && strcmp(mark, "stage")) return;
        start(mark, room);
    }
    Snap s;
    snap(s);
    ++marks;
    re4dc_log("DOORPH: %s room=%03x t=%u dt=%u blk=%u rd=%u kb=%u cpu main=%u task=%u oth=%u idle=%u spin=%u/%u\n", mark,
              room, ms(s.t_us, s0.t_us) / 1000, ms(s.t_us, prev.t_us) / 1000,
              ms(s.block_us, prev.block_us) / 1000, s.reads - prev.reads, (unsigned) ((s.bytes - prev.bytes) / 1024),
              ms(s.cpu.main, prev.cpu.main), ms(s.cpu.task, prev.cpu.task), ms(s.cpu.oth, prev.cpu.oth),
              ms(s.cpu.idle, prev.cpu.idle), ms(s.spin_us, prev.spin_us) / 1000, ms(s.spin_ms, prev.spin_ms));
    prev = s;
    cur_mark = mark;
}

extern "C" void re4dc_doorph_end(unsigned room)
{
    if (!active) return;
    re4dc_doorph("play", room);
    active = false;
    const Snap& s = prev;
    re4dc_log("DOORPH: end from=%03x room=%03x total=%u blk=%u rd=%u kb=%u cpu main=%u task=%u oth=%u idle=%u spin=%u/%u marks=%u\n",
              from_room, room, ms(s.t_us, s0.t_us) / 1000, ms(s.block_us, s0.block_us) / 1000, s.reads - s0.reads,
              (unsigned) ((s.bytes - s0.bytes) / 1024), ms(s.cpu.main, s0.cpu.main), ms(s.cpu.task, s0.cpu.task),
              ms(s.cpu.oth, s0.cpu.oth), ms(s.cpu.idle, s0.cpu.idle), ms(s.spin_us, s0.spin_us) / 1000, ms(s.spin_ms, s0.spin_ms), marks);
    // files, largest first (selection over at most kFiles rows)
    bool shown[kFiles] = {};
    for (unsigned k = 0; k < nfiles; ++k) {
        int best = -1;
        for (unsigned i = 0; i < nfiles; ++i)
            if (!shown[i] && (best < 0 || files[i].bytes > files[best].bytes)) best = (int) i;
        if (best < 0) break;
        shown[best] = true;
        const FileRow& f = files[best];
        re4dc_log("DOORFILE: room=%03x %s n=%u kb=%u us=%u first=%s\n", room, f.path, f.n, f.bytes / 1024, f.us, f.first);
    }
    if (dropped) re4dc_log("DOORFILE: room=%03x dropped=%u\n", room, dropped);
    const int o = irq_disable();
    thd_each(thd_cb, nullptr);
    irq_restore(o);
    for (unsigned i = 0; i < nthds; ++i)
        re4dc_log("DOORTHD: room=%03x %s cpu=%u\n", room, thds[i].label, ms(thds[i].ms, thds[i].ms0));
    cur_mark = "-";
}
