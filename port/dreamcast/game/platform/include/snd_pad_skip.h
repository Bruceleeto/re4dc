#pragma once
// SND_PAD_SKIP (Makefile; lane doorpause16, 2026-10-16; default 0). Forced into src/game/dvd.cpp (-include), so the
// source keeps its line numbers: with the knob off the read statement is unchanged.
//
// A sound block's ARAM part on the disc keeps the GameCube part's size (the game's ARAM layout, UseAramSize, is
// sized from it), but a build-time converted ("prebuilt") bank fills only the first 96 + image bytes; the rest of the
// part is zero padding (0.85 to 2.7 MB per chapter 1 door) that re4dc_audio_arq never copies. With the knob on, the
// source queue does not read a piece of the part that lies wholly after a prebuilt image that has fully arrived; the
// piece still goes through the same transfer and ARQ path (with whatever DVD_BUFF holds, which the prebuilt copy
// ignores), so the queue's steps, sizes, addresses and callbacks are the same and only the disc read is left out.
#if defined(RE4DC_SND_PAD_SKIP) && RE4DC_SND_PAD_SKIP
extern "C" int re4dc_audio_pad_skip(unsigned dst, unsigned len);   // platform/audio_aica.cpp
#define RE4DC_SND_PAD_READ(type, dst, len, call) do { if (!((type) == 2 && re4dc_audio_pad_skip((dst), (len)))) call; } while (0)
#else
#define RE4DC_SND_PAD_READ(type, dst, len, call) call
#endif
