#pragma once
// Presentation only. No pad type is inferred from a config key or C/Z buttons.
#ifndef RE4DC_PAD_PROMPTS
#define RE4DC_PAD_PROMPTS 0
#endif
#if RE4DC_PAD_PROMPTS
enum { RE4DC_PROMPT_UNKNOWN=0, RE4DC_PROMPT_DPAD=1, RE4DC_PROMPT_SECOND_ANALOG=2 };
// index is the game's nth MAPLE_FUNC_CONTROLLER, not a physical port number.
// live_zoom requires the last real PADRead to have used ZOOM context (2).
// Otherwise returns the mapping suitable for prospective free-camera help.
extern "C" unsigned re4dc_pad_prompt_kind(unsigned index, int live_zoom);
#if RE4DC_PAD_PROMPT_MANUAL_ART
// Last real sample, exact standard capabilities and nondual mapping.
// No claim to detect the casing/model of an arbitrary third-party device.
extern "C" unsigned re4dc_pad_manual_standard(unsigned index);
#endif
struct Re4dcUiImage;
extern "C" int re4dc_ui_binocular_prompt(const Re4dcUiImage*,unsigned,Re4dcUiImage*);
#endif
