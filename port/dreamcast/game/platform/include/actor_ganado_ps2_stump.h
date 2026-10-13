// ACTOR_GANADO_PS2_STUMP: exact source BIN479 / TPL477 head variant, default off.
#pragma once
#ifndef RE4DC_ACTOR_GANADO_PS2_STUMP
#define RE4DC_ACTOR_GANADO_PS2_STUMP 0
#endif
#if RE4DC_ACTOR_GANADO_PS2_STUMP
// Fixed chunks 1..46 precede optional far chunks 47..66. The registry and
// player costume/hand IDs start after this additional immutable geometry.
#if RE4DC_CROWD_FAR
constexpr unsigned kRe4dcGanadoStumpAsset=67u;
#else
constexpr unsigned kRe4dcGanadoStumpAsset=47u;
#endif
#endif
