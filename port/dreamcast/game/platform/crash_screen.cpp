// CRASH_SCREEN=1 (hardware readiness, default 0): on a real Dreamcast the log ring cannot be read
// without a serial cable, so a fault, a source HALT() or a hang would only leave a frozen picture.
// This draws a report straight into frame buffer 0 and shows it: what stopped, where (PC / PR /
// stage / frame), the threads, and the newest log lines, for the player to photograph.
// - Fault and HALT: called from fault.cpp with interrupts off; it never calls into the BIOS
//   (the BIOS font lock is shared with GD-ROM syscalls), so the ASCII glyphs are copied from the
//   BIOS font into RAM at boot (96 x 36 bytes).
// - Hang: a low-cost watchdog thread checks once a second that the UI frame counter or the PVR
//   frame count moves; after 30 s of neither it draws the report (interrupts stay on, the game is
//   left as it is, so a game that resumes simply draws over it).
// Game logic is untouched: nothing here runs unless the game has already stopped.
#include <kos.h>
#include <dc/biosfont.h>
#include <dc/video.h>
#include <dc/pvr.h>
#include <stdio.h>
#include <string.h>

#include "re4dc_platform.h"

#if RE4DC_CRASH_SCREEN

extern "C" volatile unsigned long re4dc_stage;
extern "C" volatile unsigned long re4dc_log_head;
extern "C" char re4dc_logbuf[];
extern "C" unsigned re4dc_ui_frame();
extern "C" int re4dc_fixture_read(const char* path, char* buffer, unsigned size);
extern "C" void re4dc_halt(const char* file, int line);
static const unsigned kLogSize = 0x10000;  // mem.cpp RE4DC_LOG_SIZE

namespace {
constexpr int kGW = 12, kGH = 24;              // BIOS thin font
int kW = 640, kH = 480, kCols = 640 / kGW, kRows = 480 / kGH;  // from vid_mode at show()
unsigned short g_glyph[96][kGH];               // 12 bits per row, bit 11 = leftmost pixel
bool g_ready;
unsigned short* g_fb;  // the frame buffer being scanned out (FB_R_SOF1), as vid_set_start maps it
volatile int g_shown;

void put_text(int col, int row, const char* s, unsigned short fg)
{
    unsigned short* fb = g_fb;
    for (; *s && col < kCols; ++s, ++col) {
        int c = (unsigned char) *s;
        if (c < 32 || c > 127) c = '?';
        const unsigned short* g = g_glyph[c - 32];
        for (int y = 0; y < kGH; ++y) {
            unsigned short* p = fb + (row * kGH + y) * kW + col * kGW;
            for (int x = 0; x < kGW; ++x) p[x] = (g[y] >> (11 - x)) & 1 ? fg : 0x0008;
        }
    }
}

void show(const char* kind, const char* detail, bool wait_render)
{
    if (!g_ready || g_shown) return;
    g_shown = 1;
    if (wait_render) {
        for (volatile unsigned i = 0; i < 20000000u; ++i) {
        }  // let an in-flight PVR render finish before drawing over buffer 0
    }
    if (vid_mode) {
        kW = vid_mode->width;
        kH = vid_mode->height;
        kCols = kW / kGW;
        kRows = kH / kGH;
    }
    // Draw into the buffer on screen now; the display is left where it is.
    g_fb = (unsigned short*) (PVR_RAM_BASE | (PVR_GET(PVR_FB_ADDR) & (PVR_RAM_SIZE - 1)));
    unsigned short* fb = g_fb;
    for (int i = 0; i < kW * kH; ++i) fb[i] = 0x0008;
    char line[96];
    int row = 0;
    put_text(0, row++, "RE4DC stopped - please raise a ticket with a photo", 0xFFE0);
    put_text(0, row++, "of this screen: github.com/lamb2k/re4dc/issues", 0xFFE0);
    snprintf(line, sizeof(line), "%s %s", kind, detail);
    put_text(0, row++, line, 0xF800);
    snprintf(line, sizeof(line), "stage %08lx  ui frame %u", re4dc_stage, re4dc_ui_frame());
    put_text(0, row++, line, 0xFFFF);
    // Threads: id, state, pc, pr (the saved context; the running thread's is stale).
    for (int tid = 1; tid <= 24 && row < 10; ++tid) {
        kthread_t* t = thd_by_tid(tid);
        if (!t) continue;
        snprintf(line, sizeof(line), "t%d %.10s s%d pc %08lx pr %08lx%s", tid, t->label, (int) t->state,
                 (unsigned long) t->context.pc, (unsigned long) t->context.pr, t == thd_current ? " *" : "");
        put_text(0, row++, line, 0x07FF);
    }
    // Newest log lines, oldest first, cut to the screen width.
    const unsigned long head = re4dc_log_head;
    const int want = kRows - row;
    unsigned long pos = head, start = head > kLogSize ? head - kLogSize : 0;
    int lines = 0;
    while (pos > start && lines <= want) {
        --pos;
        if (re4dc_logbuf[pos % kLogSize] == '\n' && pos + 1 != head) ++lines;
    }
    if (lines > want) ++pos;  // pos is on the newline before the first shown line
    int col = 0;
    line[0] = 0;
    for (; pos < head && row < kRows; ++pos) {
        const char c = re4dc_logbuf[pos % kLogSize];
        if (c == '\n' || col == kCols) {
            line[col] = 0;
            put_text(0, row++, line, 0xC618);
            col = 0;
            if (c == '\n') continue;
        }
        line[col++] = c;
    }
    if (col && row < kRows) {
        line[col] = 0;
        put_text(0, row++, line, 0xC618);
    }
}

void* watchdog(void*)
{
    unsigned last_ui = re4dc_ui_frame(), still = 0;
    size_t last_pvr = 0;
    for (;;) {
        thd_sleep(1000);
        pvr_stats_t st;
        size_t pvr = pvr_get_stats(&st) == 0 ? st.frame_count : 0;
        const unsigned ui = re4dc_ui_frame();
        if (ui != last_ui || pvr != last_pvr) {
            last_ui = ui;
            last_pvr = pvr;
            still = 0;
            continue;
        }
        if (++still == 30) {
            re4dc_log("CRASH_SCREEN: no new frame for 30 s (ui frame %u)\n", ui);
            show("HANG", "no new frame for 30 s", false);
        }
    }
    return nullptr;
}

// Test hook: /cd/dc/crashtest.txt ("fault", "halt" or "hang") stops the game that way 20 s after boot,
// so the report can be checked in Flycast. The file is never on a play disc.
int g_test;
void* crash_test(void*)
{
    thd_sleep(20000);
    if (g_test == 1) {
        re4dc_log("CRASH_SCREEN test: fault\n");
        __asm__ volatile(".short 0xfffd");  // illegal instruction: an unhandled exception, the path an
                                            // address error takes on hardware (Flycast raises neither)
    } else if (g_test == 2) {
        re4dc_halt(__FILE__, __LINE__);
    } else if (g_test == 3) {
        for (;;) {
        }  // above the game's priority: no frame is drawn again
    }
    return nullptr;
}
}  // namespace

extern "C" void re4dc_crash_screen_init(void)
{
    // 12x24 glyphs drawn by the BIOS into a small 16 bpp scratch, kept as bit rows.
    static unsigned short scratch[kGW * kGH];
    char s[2] = {0, 0};
    for (int c = 32; c < 128; ++c) {
        s[0] = (char) (c == 127 ? '?' : c);
        memset(scratch, 0, sizeof(scratch));
        bfont_draw_str_ex(scratch, kGW, 0xFFFF, 0, 16, true, s);
        for (int y = 0; y < kGH; ++y) {
            unsigned short bits = 0;
            for (int x = 0; x < kGW; ++x)
                if (scratch[y * kGW + x]) bits |= (unsigned short) (1u << (11 - x));
            g_glyph[c - 32][y] = bits;
        }
    }
    g_ready = true;
    kthread_attr_t a = {};
    a.stack_size = 4096;
    a.prio = 8;  // above the game threads so a busy hang still lets it run; it sleeps 1 s at a time
    a.label = "re4crash";
    thd_create_ex(&a, watchdog, nullptr);
    re4dc_log("CRASH_SCREEN: ready (fault, halt, 30 s hang)\n");
    char t[16] = {0};
    if (re4dc_fixture_read("/cd/dc/crashtest.txt", t, sizeof(t) - 1) > 0) {
        g_test = !strncmp(t, "fault", 5) ? 1 : !strncmp(t, "halt", 4) ? 2 : !strncmp(t, "hang", 4) ? 3 : 0;
        kthread_attr_t b = {};
        b.stack_size = 4096;
        b.prio = 9;
        b.label = "re4ctest";
        if (g_test) thd_create_ex(&b, crash_test, nullptr);
        re4dc_log("CRASH_SCREEN: test %d armed\n", g_test);
    }
}

extern "C" void re4dc_crash_screen_fault(unsigned code, unsigned long pc, unsigned long pr, unsigned long addr)
{
    char d[80];
    snprintf(d, sizeof(d), "code %03x pc %08lx pr %08lx addr %08lx", code, pc, pr, addr);
    show("FAULT", d, true);
}

extern "C" void re4dc_crash_screen_halt(const char* file, int line)
{
    char d[80];
    const char* base = file ? strrchr(file, '/') : nullptr;
    snprintf(d, sizeof(d), "%s(%d)", base ? base + 1 : (file ? file : "?"), line);
    show("HALT", d, true);
}

#endif
