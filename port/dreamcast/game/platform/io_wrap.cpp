// D367 IO probe (IO_PROBE=1), diagnostic only: where the room-entry wall time blocks.
//
// Link-time wraps (Makefile: -Wl,--wrap=fs_open,fs_read,thd_sleep,genwait_wait) time every
// blocking call, from every thread, and add it to small tables:
//   fs_read by file path (fs_open records the path of each handle), with calls, us, bytes and
//     the reads into a destination that is not 32-byte aligned (KOS then takes the per-sector
//     PIO path instead of one DMA stream);
//   fs_read / fs_open / thd_sleep by caller (return address; symbolize with symbols-demangled.txt);
//   genwait_wait (the base of every KOS sem/cond/mutex/sleep block) by wait kind and thread label;
//   per-thread totals of fs_read and genwait time.
//   GD commands (cdrom_stream_start / cdrom_stream_request / cdrom_read_sectors_ex: the entry
//     points fs_iso9660 drives): streamed and per-sector bytes and commands, sectors below the
//     lowest streamed LBA seen since boot (the directory area genisoimage writes first: inode
//     cache misses), and the distance from the previous command's end LBA in buckets. These
//     counts, not Flycast's wall time, feed the hardware door model (design-doorload 2.1).
// ui_bridge.cpp resets the tables at the door request and prints them ("iowrap:" and "iocount:"
// lines) with the "iotime: door" line. Nothing here changes what is read or when.
#include <kos.h>
#include <string.h>

#include "re4dc_platform.h"

extern "C" {
ssize_t __real_fs_read(file_t hnd, void* buffer, size_t cnt);
file_t __real_fs_open(const char* fn, int mode);
void __real_thd_sleep(unsigned ms);
int __real_genwait_wait(void* obj, const char* mesg, unsigned int timeout);
int __real_cdrom_stream_start(int sector, int cnt, bool dma);
int __real_cdrom_stream_request(void* buffer, size_t size, bool block);
int __real_cdrom_read_sectors_ex(void* buffer, uint32_t sector, size_t cnt, bool dma);
}

namespace {
unsigned long long us_now() { return timer_us_gettime64(); }

struct Site { unsigned kind; void* ra; unsigned n, bytes, mis; unsigned long long us; };
struct PathRow { char path[24]; unsigned n, bytes; unsigned short mis, opens; unsigned us, open_us; };
struct WaitRow { const char* mesg; char thread[16]; unsigned n; unsigned long long us; };
struct ThreadRow { char thread[16]; unsigned reads; unsigned long long read_us, wait_us; };
struct Handle { file_t fd; short row1; };   // row1: path row + 1 (0 = empty)

constexpr unsigned kSites = 48, kPaths = 256, kWaits = 24, kThreads = 12, kHandles = 32;
Site sites[kSites]; unsigned nsites;
PathRow paths[kPaths]; unsigned npaths;
WaitRow waits[kWaits]; unsigned nwaits;
ThreadRow threads[kThreads]; unsigned nthreads;
Handle handles[kHandles];
unsigned dropped;
bool enabled;
const char* const kKind[] = {"fs_read", "fs_open", "thd_sleep"};

// GD command counters (reset with the tables). LBAs are the drive's (file sector + 150).
struct GdCount {
    unsigned stream_start, stream_sectors, stream_req, sector_cmd, sector_n, dir_sector, errors, opens;
    unsigned seq, lt1M, lt16M, lt128M, ge128M;
    unsigned long long bytes_stream, bytes_sector;
};
GdCount gd;
unsigned next_lba = ~0u;       // end of the previous command (the drive's position)
unsigned stream_lba;           // next LBA of the live stream
unsigned min_stream_lba = ~0u; // lowest streamed LBA since boot: file data starts there or later
struct DoorHud { unsigned wall_ds, mb_d, cmds, far; bool valid; };
DoorHud door_hud;

void gd_position(unsigned lba, unsigned sectors)
{
    if (next_lba != ~0u) {
        const unsigned d = lba > next_lba ? lba - next_lba : next_lba - lba;
        const unsigned long long b = (unsigned long long) d * 2048u;
        if (!d) ++gd.seq;
        else if (b < (1ull << 20)) ++gd.lt1M;
        else if (b < (16ull << 20)) ++gd.lt16M;
        else if (b < (128ull << 20)) ++gd.lt128M;
        else ++gd.ge128M;
    }
    next_lba = lba + sectors;
}

void label_of(char out[16])
{
    kthread_t* t = thd_get_current();
    const char* l = t ? t->label : "?";
    if (!l || !*l) l = "?";
    strncpy(out, l, 15); out[15] = 0;
}

Site* site(unsigned kind, void* ra)
{
    for (unsigned i = 0; i < nsites; ++i)
        if (sites[i].ra == ra && sites[i].kind == kind) return &sites[i];
    if (nsites == kSites) { ++dropped; return nullptr; }
    Site* s = &sites[nsites++]; memset(s, 0, sizeof(*s)); s->kind = kind; s->ra = ra; return s;
}

int path_row(const char* fn)
{
    const size_t len = strlen(fn);
    const char* tail = len > 23 ? fn + len - 23 : fn;   // keep the file name end
    for (unsigned i = 0; i < npaths; ++i) if (!strcmp(paths[i].path, tail)) return (int) i;
    if (npaths == kPaths) { ++dropped; return -1; }
    PathRow* p = &paths[npaths]; memset(p, 0, sizeof(*p)); strcpy(p->path, tail);
    return (int) npaths++;
}

ThreadRow* thread_row(const char* label)
{
    for (unsigned i = 0; i < nthreads; ++i) if (!strcmp(threads[i].thread, label)) return &threads[i];
    if (nthreads == kThreads) { ++dropped; return nullptr; }
    ThreadRow* t = &threads[nthreads++]; memset(t, 0, sizeof(*t)); strcpy(t->thread, label); return t;
}

int handle_row(file_t fd)
{
    for (auto& h : handles) if (h.row1 && h.fd == fd) return h.row1 - 1;
    return -1;
}
}

extern "C" file_t __wrap_fs_open(const char* fn, int mode)
{
    void* ra = __builtin_return_address(0);
    const unsigned long long t0 = us_now();
    const file_t fd = __real_fs_open(fn, mode);
    const unsigned us = (unsigned) (us_now() - t0);
    const int irq = irq_disable();
    if (enabled) {
        if (Site* s = site(1, ra)) { ++s->n; s->us += us; }
    }
    // The handle map is kept even while the tables are off, so reads of files opened before
    // the door still get their path.
    if (enabled && fd >= 0) ++gd.opens;
    if (fn && fd >= 0) {
        const int row = path_row(fn);
        if (row < 0) {
            // No row for this path: unmap the handle, so a reused fd never keeps another
            // file's row.
            for (auto& h : handles) if (h.row1 && h.fd == fd) h.row1 = 0;
        } else {
            if (enabled) { ++paths[row].opens; paths[row].open_us += us; }
            Handle* slot = nullptr;
            for (auto& h : handles) if (h.row1 && h.fd == fd) { slot = &h; break; }
            if (!slot) for (auto& h : handles) if (!h.row1) { slot = &h; break; }
            if (!slot) slot = &handles[(unsigned) fd % kHandles];
            slot->fd = fd; slot->row1 = (short) (row + 1);
        }
    }
    irq_restore(irq);
    return fd;
}

extern "C" ssize_t __wrap_fs_read(file_t hnd, void* buffer, size_t cnt)
{
    void* ra = __builtin_return_address(0);
    const unsigned long long t0 = us_now();
    const ssize_t r = __real_fs_read(hnd, buffer, cnt);
    if (!enabled) return r;
    const unsigned us = (unsigned) (us_now() - t0);
    const unsigned bytes = r > 0 ? (unsigned) r : 0u;
    const bool mis = ((unsigned) (uintptr_t) buffer & 31u) != 0;
    char label[16]; label_of(label);
    const int irq = irq_disable();
    if (Site* s = site(0, ra)) { ++s->n; s->us += us; s->bytes += bytes; s->mis += mis; }
    const int row = handle_row(hnd);
    if (row >= 0) { PathRow& p = paths[row]; ++p.n; p.us += us; p.bytes += bytes; p.mis += mis; }
    if (ThreadRow* t = thread_row(label)) { ++t->reads; t->read_us += us; }
    irq_restore(irq);
    return r;
}

extern "C" void __wrap_thd_sleep(unsigned ms)
{
    void* ra = __builtin_return_address(0);
    const unsigned long long t0 = us_now();
    __real_thd_sleep(ms);
    if (!enabled) return;
    const unsigned us = (unsigned) (us_now() - t0);
    const int irq = irq_disable();
    if (Site* s = site(2, ra)) { ++s->n; s->us += us; }
    irq_restore(irq);
}

extern "C" int __wrap_genwait_wait(void* obj, const char* mesg, unsigned int timeout)
{
    const unsigned long long t0 = us_now();
    const int r = __real_genwait_wait(obj, mesg, timeout);
    if (!enabled) return r;
    const unsigned us = (unsigned) (us_now() - t0);
    char label[16]; label_of(label);
    const int irq = irq_disable();
    WaitRow* w = nullptr;
    for (unsigned i = 0; i < nwaits; ++i)
        if (waits[i].mesg == mesg && !strcmp(waits[i].thread, label)) { w = &waits[i]; break; }
    if (!w && nwaits < kWaits) { w = &waits[nwaits++]; memset(w, 0, sizeof(*w)); w->mesg = mesg; strcpy(w->thread, label); }
    if (w) { ++w->n; w->us += us; } else ++dropped;
    if (ThreadRow* t = thread_row(label)) t->wait_us += us;
    irq_restore(irq);
    return r;
}

extern "C" int __wrap_cdrom_stream_start(int sector, int cnt, bool dma)
{
    const int r = __real_cdrom_stream_start(sector, cnt, dma);
    const int irq = irq_disable();
    const unsigned lba = (unsigned) sector;
    if (r == 0 && lba < min_stream_lba) min_stream_lba = lba;
    if (enabled) {
        ++gd.stream_start; gd.stream_sectors += (unsigned) cnt; gd.errors += r != 0;
        gd_position(lba, 0);
    } else {
        next_lba = lba;
    }
    stream_lba = lba;
    irq_restore(irq);
    return r;
}

extern "C" int __wrap_cdrom_stream_request(void* buffer, size_t size, bool block)
{
    const int r = __real_cdrom_stream_request(buffer, size, block);
    const int irq = irq_disable();
    const unsigned sectors = (unsigned) ((size + 2047) / 2048);
    if (enabled) { ++gd.stream_req; gd.bytes_stream += size; gd.errors += r != 0; }
    stream_lba += sectors;
    next_lba = stream_lba;
    irq_restore(irq);
    return r;
}

extern "C" int __wrap_cdrom_read_sectors_ex(void* buffer, uint32_t sector, size_t cnt, bool dma)
{
    const int r = __real_cdrom_read_sectors_ex(buffer, sector, cnt, dma);
    const int irq = irq_disable();
    if (enabled) {
        ++gd.sector_cmd; gd.sector_n += (unsigned) cnt; gd.bytes_sector += (unsigned long long) cnt * 2048u;
        gd.dir_sector += (unsigned) sector < min_stream_lba; gd.errors += r != 0;
        gd_position((unsigned) sector, (unsigned) cnt);
    } else {
        next_lba = (unsigned) sector + (unsigned) cnt;
    }
    irq_restore(irq);
    return r;
}

// PERF_HUD (IO row, after the probe numbers): the last door's wall (0.1 s), MB read (0.1),
// GD commands and seeks of 16 MB or more. 0 until the first door report.
extern "C" int re4dc_iocount_hud(unsigned v[4])
{
    if (!door_hud.valid) return 0;
    v[0] = door_hud.wall_ds; v[1] = door_hud.mb_d; v[2] = door_hud.cmds; v[3] = door_hud.far;
    return 4;
}

// Reset the tables and start collecting (door request).
extern "C" void re4dc_iowrap_reset(void)
{
    const int irq = irq_disable();
    nsites = nwaits = nthreads = 0; dropped = 0;
    for (unsigned i = 0; i < npaths; ++i) {
        PathRow& p = paths[i]; p.n = p.bytes = 0; p.mis = p.opens = 0; p.us = p.open_us = 0;
    }
    memset(&gd, 0, sizeof(gd));
    enabled = true;
    irq_restore(irq);
}

// Print the tables, largest time first ("iowrap:" lines), then reset.
extern "C" void re4dc_iowrap_report(const char* what, unsigned cycle, unsigned long long wall_us)
{
    // Sorted and printed in place: collection pauses until the reset at the end (the tables
    // cost bss, which comes out of the KOS malloc break).
    enabled = false;
    Site* s = sites; PathRow* p = paths; WaitRow* w = waits; ThreadRow* t = threads;
    const unsigned ns = nsites, np = npaths, nw = nwaits, nt = nthreads, dr = dropped;
    // selection order by time (small n)
    auto top = [](auto* a, unsigned n, auto key) {
        for (unsigned i = 0; i < n; ++i)
            for (unsigned j = i + 1; j < n; ++j)
                if (key(a[j]) > key(a[i])) { auto x = a[i]; a[i] = a[j]; a[j] = x; }
    };
    top(t, nt, [](const ThreadRow& r) { return r.read_us + r.wait_us; });
    for (unsigned i = 0; i < nt; ++i)
        re4dc_log("iowrap: %s cycle=%u thread=%s reads=%u read_us=%llu wait_us=%llu\n", what, cycle,
                  t[i].thread, t[i].reads, t[i].read_us, t[i].wait_us);
    top(w, nw, [](const WaitRow& r) { return r.us; });
    for (unsigned i = 0; i < nw && i < 24; ++i)
        re4dc_log("iowrap: %s cycle=%u wait=%s thread=%s n=%u us=%llu\n", what, cycle,
                  w[i].mesg ? w[i].mesg : "?", w[i].thread, w[i].n, w[i].us);
    top(s, ns, [](const Site& r) { return r.us; });
    for (unsigned i = 0; i < ns && i < 32; ++i)
        re4dc_log("iowrap: %s cycle=%u site=%s ra=0x%08x n=%u us=%llu bytes=%u mis=%u\n", what, cycle,
                  kKind[s[i].kind], (unsigned) (uintptr_t) s[i].ra, s[i].n, s[i].us, s[i].bytes, s[i].mis);
    top(p, np, [](const PathRow& r) { return r.us + r.open_us; });
    for (unsigned i = 0; i < np && i < 40; ++i) {
        if (!p[i].n && !p[i].opens) break;
        re4dc_log("iowrap: %s cycle=%u path=%s opens=%u open_us=%u reads=%u us=%u bytes=%u mis=%u\n", what, cycle,
                  p[i].path, (unsigned) p[i].opens, p[i].open_us, p[i].n, p[i].us, p[i].bytes, (unsigned) p[i].mis);
    }
    re4dc_log("iowrap: %s cycle=%u dropped=%u paths=%u\n", what, cycle, dr, np);
    const GdCount g = gd;
    re4dc_log("iocount: %s cycle=%u wall_us=%llu bytes_stream=%llu bytes_sector=%llu cmd_stream_start=%u stream_sectors=%u "
              "cmd_stream_req=%u cmd_sector=%u sectors=%u\n", what, cycle, wall_us, g.bytes_stream, g.bytes_sector,
              g.stream_start, g.stream_sectors, g.stream_req, g.sector_cmd, g.sector_n);
    re4dc_log("iocount: %s cycle=%u dir_sector=%u dir_lba_lt=%u seeks_seq=%u lt1M=%u lt16M=%u lt128M=%u ge128M=%u "
              "opens=%u errors=%u\n", what, cycle, g.dir_sector, min_stream_lba, g.seq, g.lt1M, g.lt16M, g.lt128M,
              g.ge128M, g.opens, g.errors);
    if (!strcmp(what, "door")) {
        door_hud.wall_ds = (unsigned) ((wall_us + 50000) / 100000);
        door_hud.mb_d = (unsigned) (((g.bytes_stream + g.bytes_sector) * 10 + (1u << 19)) >> 20);
        door_hud.cmds = g.stream_start + g.stream_req + g.sector_cmd;
        door_hud.far = g.lt128M + g.ge128M;
        door_hud.valid = true;
    }
    // Sorting moved the path rows: forget the handle map (files opened before this point lose
    // their path; the room loads open their files again).
    memset(handles, 0, sizeof(handles));
    npaths = 0;
    re4dc_iowrap_reset();
}
