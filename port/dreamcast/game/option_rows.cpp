// RENDER_OPTION=1 (game30.mk; Phase 2 C6, user decisions 2026-09-24 / 2026-10-12): two rows in the GameCube Options
// screen (option.cpp top menu, title and pause), below AUDIO SETUP:
//   FRAME PACING  SMOOTH / FAST / OFF       (pace.cpp; stored as quality.cpp set_pace)
//   RENDERING     QUALITY / STANDARD / FAST (res_mode.cpp; stored as quality.cpp set_render)
// The screen's labels are pictures in the option archive; these two rows are drawn as message text in the game's
// own message font (two message slots, a message table of their own swapped in only while MesSet resolves it, the
// quality picker's mechanism). EXIT and the help line move down two rows. The highlighted row takes the screen's
// pulsing cursor colour (unit 8, as option.cpp setColor); cursor and value sounds are the screen's own (0x34 move,
// 0x3A set). Left / right or A changes the value at once and stores RE4DCCFG. Cursor order: rows 0..3, the two new
// rows, EXIT. Text: letters and spaces only (the verified glyph codes of the English font).
#include "types.h"
#include "global.h"
#include "main.h"
#include "mes.h"
#include "id_sys.h"
#include "snd.h"
#include "option.h"
#include "platform/quality.h"
#include <stddef.h>

extern "C" void re4dc_log(const char* fmt, ...);
extern "C" int re4dc_pace_get_mode(void);                          // pace.cpp: 0 smooth, 1 fast, 2 off
extern "C" void re4dc_pace_set_mode(int mode, const char* why);    // pace.cpp: this boot's mode now
extern "C" int re4dc_res_vga(void);                                // res_mode.cpp: 1 on a VGA cable

namespace {
constexpr int kRowPacing = 5, kRowRender = 6, kBack = 4;
#if RE4DC_RENDER_QUALITY_ONLY
constexpr int kRows = 1;  // game30.mk RENDER_QUALITY_ONLY: no Rendering row
#else
constexpr int kRows = 2;
#endif
constexpr int kSlot0 = 13;  // message slots of the two rows (slot 0 is the screen's help line)
constexpr u32 kKeyA = 0x80000000, kKeyB = 0x40000000, kKeyUp = 0x01000000, kKeyDown = 0x02000000,
              kKeyLeft = 0x08000000, kKeyRight = 0x04000000;
constexpr u8 kIdOpt = 0x2A;

// English common_p.fnt glyph codes (quality_picker.cpp): space 0x80, 'A'-'Z' = ch + 0x66, 'a'-'z' = ch + 0x60.
enum : u16 { PAGE = 0x00, END = 0x01 };
struct Table {
    u32 hdr;
    u32 lang[8];
    u32 x0, count, ofs[4];
    u16 text[200];
};
alignas(4) Table table;
unsigned text_n;
void put(u16 w) { if (text_n < sizeof(table.text) / 2) table.text[text_n++] = w; }
void put(const char* s)
{
    for (; *s; ++s) {
        const char c = *s;
        if (c == ' ') put(u16(0x80));
        else if (c >= 'A' && c <= 'Z') put(u16(c + 0x66));
        else if (c >= 'a' && c <= 'z') put(u16(c + 0x60));
    }
}
const char* const kPace[3] = {"SMOOTH", "FAST", "OFF"};
#if defined(RE4DC_RENDER_FSAA) && RE4DC_RENDER_FSAA
const char* const kRender[3] = {"QUALITY", "FSAA", "FSAA LITE"};  // game30.mk RENDER_FSAA (console test)
#else
const char* const kRender[3] = {"QUALITY", "STANDARD", "FAST"};
#endif
int pace_value() { const int m = re4dc_pace_get_mode(); return m < 0 || m > 2 ? 0 : m; }
int render_value() { const int r = re4dc_quality_render(); return r < 0 || r > 2 ? 0 : r; }
// Messages: 0 pacing row, 1 rendering row, 2 pacing help, 3 rendering help.
void build()
{
    text_n = 0;
    const u32 block = offsetof(Table, x0);
    const u32 text0 = offsetof(Table, text) - block;
    table.hdr = 8;
    for (u32& l : table.lang) l = block;
    table.x0 = 0;
    table.count = 4;
    table.ofs[0] = text0 + 2 * text_n;
    put(PAGE); put("FRAME PACING   "); put(kPace[pace_value()]); put(END);
    table.ofs[1] = text0 + 2 * text_n;
    put(PAGE); put("RENDERING   "); put(kRender[render_value()]); put(END);
    table.ofs[2] = text0 + 2 * text_n;
    put(PAGE); put("How frames are paced when the game is busy"); put(END);
    table.ofs[3] = text0 + 2 * text_n;
#if defined(RE4DC_RENDER_FSAA) && RE4DC_RENDER_FSAA
    put(PAGE); put("Edge smoothing test  this boot only"); put(END);
#else
    put(PAGE); put(re4dc_res_vga() ? "Fewer pixels for more speed  doubled lines on VGA" : "Fewer pixels for more speed"); put(END);
#endif
}
void mes(int no, int x, int y, u32 attr, int slot)
{
    if (slot) {  // the help line's slot 0 has the screen's layout (font size, spacing): the row slots take it
        Message* d = cMes.getMes(slot);
        const Message* h = cMes.getMes(0);
#if RE4DC_OPTION_ROW_STYLE
        // Menu rows use the same cap height as the archive labels. The help
        // layout is deliberately taller and must not determine their aspect.
        d->m_font_w = 22;
        d->m_font_h = 22;
        d->charSpace = 0;
#else
        d->m_font_w = h->m_font_w;
        d->m_font_h = h->m_font_h;
        d->charSpace = h->charSpace;
#endif
        d->m_line_gap = h->m_line_gap;
        d->m_ot_type = h->m_ot_type;
        d->m_ot_no = h->m_ot_no;
    }
    u8* const saved = MesData.ptr[3];
    MesData.ptr[3] = (u8*) &table;
    cMes.MesSet(no, x, y, (attr & ~0x0FU) | 0x08U | 0x40U, slot, 0, 4);  // file 3 = this table, instant
    MesData.ptr[3] = saved;
}
u32 rgba(const IdUnit* u) { return (u32(u8(u->col[0])) << 24) | (u32(u8(u->col[1])) << 16) | (u32(u8(u->col[2])) << 8) | u8(u->col[3]); }
// Cursor order 0, 1, 2, 3, 5, 6, 4 (rows 0..3, the two new rows, EXIT).
constexpr int kOrderN = 5 + kRows;
const s8 kOrder[7] = {0, 1, 2, 3, kRowPacing, kRows == 2 ? kRowRender : kBack, kBack};
int order_index(int row) { for (int i = 0; i < kOrderN; ++i) if (kOrder[i] == row) return i; return 0; }
void change(int row, int dir)
{
    if (row == kRowPacing) {
        const int m = (pace_value() + 3 + dir) % 3;
        re4dc_quality_set_pace(m + 1);   // stored: 1 smooth, 2 fast, 3 off
        re4dc_pace_set_mode(m, "options");
    } else {
        re4dc_quality_set_render((render_value() + 3 + dir) % 3);
    }
    SndCall(0, 0x3A, 0, 0, 0, 0);
    re4dc_log("options: %s %s\n", row == kRowPacing ? "frame pacing" : "rendering",
              row == kRowPacing ? kPace[pace_value()] : kRender[render_value()]);
}
}  // namespace

#if RE4DC_OPTION_ROW_STYLE
#include "option_rows_art.inc"
#endif

// Top menu input (option.cpp top_menu, after START): 1 when consumed (cursor move, value change, B on a new row).
extern "C" int re4dc_option_rows_key(s8* rno1)
{
    const u32 t = Key.trg;
    const int row = *rno1;
    if (row == kRowPacing || row == kRowRender) {
        if (t & (kKeyA | kKeyRight)) { change(row, 1); return 1; }
        if (t & kKeyLeft) { change(row, -1); return 1; }
        if (t & kKeyB) { *rno1 = kBack; SndCall(0, 0x39, 0, 0, 0, 0); return 1; }
    }
    if (t & (kKeyUp | kKeyDown)) {
        int i = order_index(row) + ((t & kKeyUp) ? -1 : 1);
        i = i < 0 ? 0 : (i > kOrderN - 1 ? kOrderN - 1 : i);
        if (kOrder[i] == 0 && (pG->Status_flg[2] & 0x8000)) i = 1;  // retry / load disabled
        if (kOrder[i] != row) { *rno1 = kOrder[i]; SndCall(0, 0x34, 0, 0, 0, 0); re4dc_log("options: cursor %d\n", kOrder[i]); }
        return 1;
    }
    // On a new row every frame is consumed: option.cpp's own branch clamps the cursor to 0..4.
    return row == kRowPacing || row == kRowRender;
}

// Top menu drawing (option.cpp top_menu, before the help line): moves EXIT down two rows, draws the two rows, and
// for a new row shows its help (returns 1: option.cpp skips its own help). *y0 = the help line's moved y.
extern "C" int re4dc_option_rows_draw(OptionScreen* o, int x0, int* y0)
{
    IdUnit* audio = IdSys.unitPtr(5, kIdOpt);
    IdUnit* bright = IdSys.unitPtr(4, kIdOpt);
    IdUnit* back = IdSys.unitPtr(6, kIdOpt);
    IdUnit* base = IdSys.unitPtr(8, kIdOpt);
    const f32 gap = bright->scr.y - audio->scr.y;  // one row (screen y grows upwards in id units)
    back->scr.y = audio->scr.y - f32(kRows + 1) * gap;
    build();
#if RE4DC_OPTION_ROW_STYLE
    if (option_art_ready()) {
        cMes.Delete(kSlot0);
        cMes.Delete(kSlot0 + 1);
    } else
#endif
    for (int k = 0; k < kRows; ++k) {
        // Message coordinates: (240 - scr.y) x 0.8 (ss_term.cpp OpeMesSet), the row's centre line.
        const f32 sy = audio->scr.y - f32(k + 1) * gap;
#if RE4DC_OPTION_ROW_STYLE
        const int y = int((240.0f - sy) * 0.8f) - 15;
#else
        const int y = int((240.0f - sy) * 0.8f) - 21;  // text top (calibrated on the Options screen still)
#endif
        mes(k, x0, y, o->_msg_attr, kSlot0 + k);
        cMes.getMes(kSlot0 + k)->m_col = (o->_rno1 == kRowPacing + k) ? rgba(base) : 0xFFFFFFFFU;
    }
    *y0 += int(f32(kRows) * gap * 0.8f);
    if (o->_rno1 == kRowPacing || o->_rno1 == kRowRender) {
        mes(o->_rno1 == kRowPacing ? 2 : 3, x0, *y0, o->_msg_attr, 0);
        return 1;
    }
    return 0;
}

// Leaving the top menu (sub menu, close): the rows' message slots go.
extern "C" void re4dc_option_rows_hide()
{
    cMes.Delete(kSlot0);
    cMes.Delete(kSlot0 + 1);
}
