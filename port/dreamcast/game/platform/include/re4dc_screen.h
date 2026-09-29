// re4dc_screen.h -- the render target size in pixels. SCREEN_320=1 (game30.mk, test builds) renders at
// 320x240 (KOS DM_320x240): every screen mapping (the 640 / 480 / 320 / 240 constants of the projection
// rows, the viewport normalisation and the clip / outcode bounds) takes these values, and the 2D UI (laid out
// in 640x480) is scaled at its emit sites by RE4DC_UI_X / RE4DC_UI_Y. The defaults leave every build unchanged.
#pragma once
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
