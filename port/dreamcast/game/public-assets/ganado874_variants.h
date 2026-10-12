// Public fallback (port/dreamcast/game/public-assets): neutral stand-in for the private generated
// header of the same name, so the game builds from the public repository alone. It carries no game data.
// Its signatures and bind table never match a source model, so the native Ganado (COARSE_GANADO) path declines and
// the game draws that character with the original GameCube model read from the disc (the source path).
#pragma once
namespace ganado874 {
struct VariantSignature { unsigned role, positions, normals, palette, vertex_hash; };
static const VariantSignature variants[] = {{0,0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu}};
static const int parents[34] = {-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1};
}
