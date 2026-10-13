// English option.dat lettering. Coordinates reference existing source textures;
// no extracted pixels or additional texture packages are stored here.
#include "texture.h"
#include "native_ui.h"
#include <string.h>

namespace {
struct OptionLetter { u8 texture, x, width, height; };
struct OptionSheet { u8 id; u16 width, height; };
const OptionSheet kOptionSheets[] = {
    {0x85, 171, 26}, // RETRY or LOAD
    {0x86, 216, 26}, // CONTROLLER SETUP
    {0x87, 226, 26}, // BRIGHTNESS ADJUST
    {0xAC, 122, 26}, // MONAURAL
    {0xAF,  49, 26}, // OFF
    {0xB4, 148, 31}, // QUICK KNIFE (Q, normalized to the other caps)
};
// Only the capitals used by the two labels and their existing values.
// Each right edge stops before the next letter's light pixels.
const OptionLetter kOptionLetters[26] = {
    {0xAC,44,13,26}, {}, {0x86,0,14,26}, {0x85,151,20,26},
    {0x86,109,14,26}, {0xAF,29,20,26}, {0x87,41,12,26}, {0x87,53,15,26},
    {0x87,30,11,26}, {}, {}, {0xAC,101,21,26}, {0xAC,0,16,26},
    {0xAC,30,14,26}, {0x86,14,13,26}, {0x86,196,20,26}, {0xB4,0,15,31},
    {0x86,123,19,26}, {0x87,121,17,26}, {0x86,42,12,26}, {0xAC,59,13,26},
    {}, {}, {}, {0x85,56,20,26}, {}
};
const TEXHeader* option_sheet(u8 id)
{
    TexWk* wk = IdGetTexWk(id, 1);
    if (!wk || !wk->pTpl || wk->pTpl->numDescriptors != 1) return nullptr;
    const TEXDescriptor* d = TEXGet(wk->pTpl, 0);
    return d ? d->textureHeader : nullptr;
}
bool option_art_ready()
{
    if (!pSys || (pSys->language != 1 && pSys->language != 2 && pSys->language != 7)) return false;
    for (const OptionSheet& s : kOptionSheets) {
        const TEXHeader* t = option_sheet(s.id);
        if (!t || !t->data || t->format != 2 || t->width != s.width || t->height != s.height) return false;
    }
    return true;
}
// Keep the shadow in the crop, but advance by the original letter's ink width
// plus its normal gap; this prevents the shadow padding from adding tracking.
int option_advance(char c)
{
    switch (c) {
    case ' ': return 7;
    case 'A': return 15;
    case 'U': return 14;
    case 'D': return 13;
    case 'G': return 14;
    case 'O': return 14;
    case 'T': return 13;
    case 'F': return 13;
    case 'L': return 13;
    case 'M': return 17;
    case 'P': return 14;
    case 'R': return 15;
    case 'S': return 13;
    case 'Y': return 15;
    case 'Q': return 14;
    default: return kOptionLetters[c - 'A'].width;
    }
}
int option_text_width(const char* text)
{
    int w = 0;
    for (; *text; ++text) w += option_advance(*text);
    return w;
}
void option_text(const char* text, float x, float y, float sx, float sy, unsigned argb)
{
    for (; *text; ++text) {
        const char c = *text;
        if (c != ' ') {
            const OptionLetter& l = kOptionLetters[c - 'A'];
            const TEXHeader* t = option_sheet(l.texture);
            Re4dcUiQuad q = {};
            q.image.pixels = t->data;
            q.image.width = t->width; q.image.height = t->height;
            q.image.format = t->format; q.image.palette_format = 0xFFFFFFFFU;
            // QUICK KNIFE uses larger, brighter caps. Keep its Q descender,
            // and match the 17-pixel cap height / grey of the other labels.
            const float scale = c == 'Q' ? 0.85f : 1.0f;
            const float right = x + l.width * sx * scale;
            const float bottom = y + l.height * sy * scale;
            const float xy[8] = {x,y,right,y,right,bottom,x,bottom};
            // Bilinear filtering must not sample the neighbouring letter at
            // either crop edge when menu scaling lands between screen pixels.
            const float left_u = (float(l.x) + 0.5f) / t->width;
            const float right_u = (float(l.x + l.width) - 0.5f) / t->width;
            const float uv[8] = {left_u,0,right_u,0,right_u,1,left_u,1};
            memcpy(q.xy, xy, sizeof(xy)); memcpy(q.uv, uv, sizeof(uv));
            q.color = argb;
            if (c == 'Q') {
                q.color = (argb & 0xFF000000U)
                    | ((((argb >> 16) & 255) * 12 / 15) << 16)
                    | ((((argb >> 8) & 255) * 12 / 15) << 8)
                    | ((argb & 255) * 12 / 15);
            }
            re4dc_ui_submit(&q);
        }
        x += option_advance(c) * sx;
    }
}
} // namespace

// Called alongside the existing AUDIO SETUP ID draw, while the native UI frame
// and source ordering table are active. The source quad supplies fade and scale.
extern "C" void re4dc_option_rows_art(const Re4dcUiQuad* audio)
{
    if (OptScrn._rno0 != 0 || !option_art_ready()) return;
    IdUnit* unit = IdSys.unitPtr(5, kIdOpt);
    IdUnit* bright = IdSys.unitPtr(4, kIdOpt);
    IdUnit* cursor = IdSys.unitPtr(8, kIdOpt);
    const float sx = (audio->xy[2] - audio->xy[0]) / 147.0f;
    const float sy = (audio->xy[7] - audio->xy[1]) / 26.0f;
    const float gap = bright->scr.y - unit->scr.y;
    const float center = (audio->xy[0] + audio->xy[2]) * 0.5f;
    const int label_width = option_text_width("FRAME PACING");
    const int value_width = option_text_width("STANDARD");
    const float value_x = center + (label_width + 16 - value_width) * 0.5f * sx;
    const char* labels[2] = {"FRAME PACING", "RENDERING"};
    const char* values[2] = {kPace[pace_value()], kRender[render_value()]};
    for (int row = 0; row != kRows; ++row) {
        const float x = value_x - (16 + option_text_width(labels[row])) * sx;
        const float y = audio->xy[1] + (row + 1) * gap * sy;
        unsigned col = (audio->color & 0xFF000000U) | 0xFFFFFFU;
        if (OptScrn._rno1 == kRowPacing + row) {
            const u32 c = rgba(cursor);
            col = (col & 0xFF000000U) | (c >> 8);
        }
        option_text(labels[row], x, y, sx, sy, col);
        option_text(values[row], value_x, y, sx, sy, col);
    }
}
