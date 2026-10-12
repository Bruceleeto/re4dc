// Public fallback (port/dreamcast/game/public-assets): neutral stand-in for the private generated
// header of the same name, so the game builds from the public repository alone. It carries no game data.
// No extra source chunks: find() returns nullptr, so no Ganado part takes the original-chunk route.
#pragma once
#include "coarse_actor_transaction.h"
namespace ganado_extra {
struct Chunk { unsigned bin,asset_id,position_count,normal_count,palette_count,triangles; re4dc_source::ChunkInput input; const unsigned char* groups; unsigned group_count; };
static const Chunk chunks[] = {{0xFFFFFFFFu,0,0,0,0,0,{},nullptr,0}};
inline const Chunk* find(unsigned bin) {for(const auto& c:chunks)if(c.bin==bin && c.position_count)return &c;return nullptr;}
}
