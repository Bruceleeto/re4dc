// Public fallback (port/dreamcast/game/public-assets): neutral stand-in for the private generated
// header of the same name, so the game builds from the public repository alone. It carries no game data.
// Its signatures and bind table never match a source model, so the native Leon hair path declines and
// the game draws that character with the original GameCube model read from the disc (the source path).
#pragma once
namespace leon_hair_runs {
struct Run { const unsigned char* stream; unsigned bytes,triangles,material,asset_id; };
alignas(32) static const unsigned char uv[4] = {};
static const Run runs[14] = {};
static constexpr unsigned role=7,palette_count=229,run_count=14;
}
