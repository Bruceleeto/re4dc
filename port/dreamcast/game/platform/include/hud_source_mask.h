#ifndef RE4DC_HUD_SOURCE_MASK_H
#define RE4DC_HUD_SOURCE_MASK_H
#ifndef RE4DC_UI_HUD_MASK
#define RE4DC_UI_HUD_MASK 0
#endif
#if RE4DC_UI_HUD_MASK
struct Re4dcUiImage;
struct Re4dcUiQuad;
// Returns handled only for the two certified core HUD colour/mask pairs.
// Ordinary queue admission owns resource failure accounting and scene pins.
extern "C" int re4dc_ui_hud_mask_submit(const Re4dcUiQuad*, const Re4dcUiImage*);
#endif
#endif
