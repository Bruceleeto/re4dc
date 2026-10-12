// Public fallback (port/dreamcast/game/public-assets): neutral stand-in for the private generated
// header of the same name, so the game builds from the public repository alone. It carries no game data.
// Its signatures and bind table never match a source model, so the native Ganado (COARSE_GANADO) path declines and
// the game draws that character with the original GameCube model read from the disc (the source path).
#pragma once
#include <cstdint>
namespace ganado874 {
struct Weight { unsigned char bone[3], count; float value[3]; };
struct Chunk { unsigned source_info, position_count, normal_count, palette_count, triangles, stream_bytes; const unsigned char *positions, *normals, *uv; unsigned char *stream; const Weight *weights; };
// Empty arrays under the generated names (the owner path names them through macros).
alignas(32) static const unsigned char i0_pos[4] = {};
alignas(32) static const unsigned char i0_nrm[4] = {};
alignas(32) static const unsigned char i0_uv[4] = {};
alignas(32) static unsigned char i0_gx[4] = {};
static const Weight i0_weights[1] = {};
alignas(32) static const unsigned char i1_pos[4] = {};
alignas(32) static const unsigned char i1_nrm[4] = {};
alignas(32) static const unsigned char i1_uv[4] = {};
alignas(32) static unsigned char i1_gx[4] = {};
static const Weight i1_weights[1] = {};
alignas(32) static const unsigned char i2_pos[4] = {};
alignas(32) static const unsigned char i2_nrm[4] = {};
alignas(32) static const unsigned char i2_uv[4] = {};
alignas(32) static unsigned char i2_gx[4] = {};
static const Weight i2_weights[1] = {};
alignas(32) static const unsigned char i3_pos[4] = {};
alignas(32) static const unsigned char i3_nrm[4] = {};
alignas(32) static const unsigned char i3_uv[4] = {};
alignas(32) static unsigned char i3_gx[4] = {};
static const Weight i3_weights[1] = {};

static Chunk chunks[] = {
{0,0,0,0,0,0,nullptr,nullptr,nullptr,nullptr,nullptr},{1,0,0,0,0,0,nullptr,nullptr,nullptr,nullptr,nullptr},
{2,0,0,0,0,0,nullptr,nullptr,nullptr,nullptr,nullptr},{3,0,0,0,0,0,nullptr,nullptr,nullptr,nullptr,nullptr},
};
static constexpr unsigned bone_count=34;
struct SourceSignature { unsigned positions, normals, palette, vertex_hash; };
static const SourceSignature signatures[4] = {
{0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu},
{0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu},
{0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu},
{0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu,0xFFFFFFFFu}
};
static const float bind[34][12] = {{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f},{1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f,1e30f}};
}
