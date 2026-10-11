// re4dc_screen.h -- the render target size in pixels. SCREEN_320=1 (game30.mk, test builds) renders at
// 320x240 (KOS DM_320x240): every screen mapping (the 640 / 480 / 320 / 240 constants of the projection
// rows, the viewport normalisation and the clip / outcode bounds) takes these values, and the 2D UI (laid out
// in 640x480) is scaled at its emit sites by RE4DC_UI_X / RE4DC_UI_Y. The defaults leave every build unchanged.
#pragma once
#if defined(RE4DC_RES_MODES) && RE4DC_RES_MODES
// RES_MODES (game30.mk, test builds; platform/res_mode.cpp): the render size changes at run time (640x480,
// 640x240 line doubled, 1280x240 / 1280x480 into the FSAA scaler), so every mapping reads the current size.
#if defined(RE4DC_SCREEN_W) || defined(RE4DC_SCREEN_H)
#error RES_MODES and SCREEN_320 are exclusive
#endif
#ifdef __cplusplus
extern "C" {
#endif
extern int re4dc_screen_w, re4dc_screen_h;
extern float re4dc_screen_wf, re4dc_screen_hf, re4dc_ui_sx, re4dc_ui_sy;
#ifdef __cplusplus
}
#endif
#define RE4DC_SCREEN_W re4dc_screen_w
#define RE4DC_SCREEN_H re4dc_screen_h
#define RE4DC_SCREEN_WF (re4dc_screen_wf)
#define RE4DC_SCREEN_HF (re4dc_screen_hf)
#define RE4DC_SCREEN_HALF_WF (re4dc_screen_wf * 0.5f)
#define RE4DC_SCREEN_HALF_HF (re4dc_screen_hf * 0.5f)
#define RE4DC_UI_X(x) ((x) * re4dc_ui_sx)
#define RE4DC_UI_Y(y) ((y) * re4dc_ui_sy)
#else
#ifndef RE4DC_SCREEN_W
#define RE4DC_SCREEN_W 640
#endif
#ifndef RE4DC_SCREEN_H
#define RE4DC_SCREEN_H 480
#endif
#define RE4DC_SCREEN_WF (float(RE4DC_SCREEN_W))
#define RE4DC_SCREEN_HF (float(RE4DC_SCREEN_H))
#define RE4DC_SCREEN_HALF_WF (float(RE4DC_SCREEN_W) * 0.5f)
#define RE4DC_SCREEN_HALF_HF (float(RE4DC_SCREEN_H) * 0.5f)
#if RE4DC_SCREEN_W != 640 || RE4DC_SCREEN_H != 480
#define RE4DC_UI_X(x) ((x) * (float(RE4DC_SCREEN_W) / 640.0f))
#define RE4DC_UI_Y(y) ((y) * (float(RE4DC_SCREEN_H) / 480.0f))
#else
#define RE4DC_UI_X(x) (x)
#define RE4DC_UI_Y(y) (y)
#endif
#endif
