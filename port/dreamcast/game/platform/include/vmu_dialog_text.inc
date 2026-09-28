/* Included by src/game/card.cpp after mes.h, under RE4DC_VMU_DIALOG.
 * Only the card screen's English message slot 0 is borrowed. MesSet establishes
 * every original stop/input/choice flag first. Nothing calls Message::move here.
 * Generated originals are exact private English memcard.das words, represented
 * as ASCII + the six observed control bytes. Every control survives unchanged.
 */
extern MessageFont MesFont[4]; // Defined in game/mes.cpp; mes.h supplies its type.
namespace {
struct CardVmuText {
    unsigned id, original_bytes, replacement_bytes;
    const char* original;
    const char* replacement;
};
#include "vmu_dialog_english.inc"

static unsigned short card_vmu_words[512]; // slot 0 only, replaced after each MesSet

static unsigned short card_vmu_glyph(unsigned char c)
{
    if (c == 0 || c == 1 || c == 3 || c == 4 || c == 7 || c == 8) return c;
    if (c == ' ') return 0x80;
    if (c >= '0' && c <= '9') return 0x83 + c - '0';
    if (c >= 'A' && c <= 'Z') return 0xa7 + c - 'A';
    if (c >= 'a' && c <= 'z') return 0xc1 + c - 'a';
    switch (c) {
    case ':': return 0x8d;
    case '%': return 0x8e;
    case '-': return 0x91;
    case '/': return 0x92;
    case ',': return 0x94;
    case '.': return 0x95;
    case '(': return 0x98;
    case ')': return 0x99;
    case '!': return 0x9a;
    case '?': return 0x9b;
    default: return 0xffff;
    }
}

static int card_vmu_append(const char* s, unsigned& used)
{
    for (; *s; ++s) {
        const unsigned short w = card_vmu_glyph((unsigned char) *s);
        if (w < 0x80 || w == 0xffff || used == 512) return 0;
        card_vmu_words[used++] = w;
    }
    return 1;
}

static void card_vmu_decimal(unsigned v, char* out)
{
    // Snapshot FAT has at most 241 blocks, directory at most 208 entries.
    char reverse[10];
    unsigned n = 0;
    do { reverse[n++] = (char) ('0' + v % 10); v /= 10; } while (v && n < 10);
    for (unsigned i = 0; i < n; ++i) out[i] = reverse[n - 1 - i];
    out[n] = 0;
}

static int card_vmu_device(const Re4dcVmuDialogSnapshot& s, unsigned& used)
{
    if (!(s.flags & RE4DC_VMU_DIALOG_SELECTED)) return card_vmu_append("VMU", used);
    if (s.port > 3 || s.slot < 1 || s.slot > 2) return 0;
    // Memory-only peripherals remain usable; do not claim they have an LCD.
    if (!card_vmu_append((s.flags & RE4DC_VMU_DIALOG_LCD) ? "VMU " : "memory unit ", used)) return 0;
    const char address[3] = {(char) ('A' + s.port), (char) ('0' + s.slot), 0};
    return card_vmu_append(address, used);
}

static int card_vmu_expand(const CardVmuText& t, const Re4dcVmuDialogSnapshot& s)
{
    unsigned used = 0;
    for (unsigned i = 0; i < t.replacement_bytes; ++i) {
        const unsigned char c = (unsigned char) t.replacement[i];
        if (c == '%') {
            if (++i == t.replacement_bytes) return 0;
            char number[11];
            switch (t.replacement[i]) {
            case 'D':
                if (!card_vmu_device(s, used)) return 0;
                break;
            case 'F':
                if (!(s.flags & RE4DC_VMU_DIALOG_COUNTS)) {
                    if (!card_vmu_append("Free space unavailable.", used)) return 0;
                } else {
                    if (s.free_blocks > 241) return 0;
                    card_vmu_decimal(s.free_blocks, number);
                    if (!card_vmu_append("Free: ", used) || !card_vmu_append(number, used) ||
                        !card_vmu_append(" VMU blocks.", used)) return 0;
                }
                break;
            case 'S':
                if (!s.system_blocks || s.system_blocks > 241) return 0;
                card_vmu_decimal(s.system_blocks, number);
                if (!card_vmu_append(number, used)) return 0;
                break;
            default: return 0;
            }
        } else {
            const unsigned short w = card_vmu_glyph(c);
            if (w == 0xffff || used == 512) return 0;
            card_vmu_words[used++] = w;
        }
    }
    if (!used || card_vmu_words[0] != 0 || card_vmu_words[used - 1] != 1) return 0;
    // Leave room for the source's choice/page marker glyphs in its 256-entry
    // page queue. This also makes a future oversized template decline safely.
    unsigned page_glyphs = 0;
    for (unsigned i = 0; i < used; ++i) {
        const unsigned short w = card_vmu_words[i];
        if (w == 0 || w == 4) page_glyphs = 0;
        else if (w >= 0x80 || w == 7 || w == 8) {
            if (++page_glyphs > 240) return 0;
        }
    }
    // Reject any accidental change to line/page/wait/choice commands. This table
    // has no argument-taking controls, jumps, inline glyphs or substitutions.
    unsigned a = 0, b = 0;
    for (;;) {
        while (a < t.original_bytes && (unsigned char) t.original[a] >= 0x20) ++a;
        while (b < used && card_vmu_words[b] >= 0x80) ++b;
        if (a == t.original_bytes || b == used) return a == t.original_bytes && b == used;
        if ((unsigned char) t.original[a++] != card_vmu_words[b++]) return 0;
    }
}

static void cardVmuDialogMessage(int id, int slot, int channel)
{
    if (slot != 0 || channel != 0 || MesData.lang != 1 || !(MesFont[0].be_flag & 1)) return;
    Message& m = cMes.mes[0];
    unsigned short* original = MesData.getAddr(id, 0);
    if (!original || m.m_pMes != original) return; // MesSet failed or another context owns it.
    const CardVmuText* entry = nullptr;
    for (unsigned i = 0; i < sizeof(card_vmu_text) / sizeof(card_vmu_text[0]); ++i)
        if (card_vmu_text[i].id == (unsigned) id) { entry = &card_vmu_text[i]; break; }
    if (!entry) return;
    // Exact original words, including the terminal control; no generic phrase
    // matching and no reading beyond a different/shorter message on mismatch.
    for (unsigned i = 0; i < entry->original_bytes; ++i)
        if (original[i] != card_vmu_glyph((unsigned char) entry->original[i])) return;
    Re4dcVmuDialogSnapshot state{};
    if (!re4dc_vmu_dialog_snapshot(&state)) return;
    if (card_vmu_expand(*entry, state)) m.m_pMes = card_vmu_words;
}
} // namespace
