// bench_lever.h (BENCH_LEVERS=1, crowd.mk; DBG_WARP test builds only): runtime perf levers for the benchmark kit.
// The warp fixture's `lever <name>...` line sets re4dc_bench_lever at boot (dbgwarp_bridge.cpp); each hook below reads
// it. With BENCH_LEVERS=0 (default) RE4DC_LEVER() is 0 and no hook compiles in. Render / perf only: no lever changes
// game state, Rnd() draws or effect motion (levers that drop enemies use the rig's `dead` line instead).
#pragma once
#define RE4DC_LV_HWFOG     0x001u   // HW_FOG_HAZE replacement on (build has it with the replacement off by default)
#define RE4DC_LV_HAZE_OFF  0x002u   // every camera-haze sprite (Esp15, owner 0xD0) not drawn, no veil
#define RE4DC_LV_ROOMFX    0x004u   // every room-effect sprite (owners 0xD0 / 0x01) not drawn
#define RE4DC_LV_TORCH     0x008u   // torch / lamp glows (Esp0e, EFFECT_TORCH) not drawn
#define RE4DC_LV_FXOFF     0x010u   // every native effect sprite not drawn
#define RE4DC_LV_FX1       0x020u   // FX_LEVEL 1 at boot
#define RE4DC_LV_FX2       0x040u   // FX_LEVEL 2 at boot
#define RE4DC_LV_TRIM      0x080u   // FX_SPRITE_TRIM as built (else untrimmed quads)
#define RE4DC_LV_LRU       0x100u   // UI_SOURCE_LRU replacement (else the full table stays as is)
#define RE4DC_LV_FAR       0x200u   // far-Ganado update rate (when built)
#if defined(RE4DC_BENCH_LEVERS) && RE4DC_BENCH_LEVERS
#ifdef __cplusplus
extern "C" unsigned re4dc_bench_lever;
#else
extern unsigned re4dc_bench_lever;
#endif
#define RE4DC_LEVER(bit) ((re4dc_bench_lever & (bit)) != 0)
#else
#define RE4DC_LEVER(bit) 0
#endif
