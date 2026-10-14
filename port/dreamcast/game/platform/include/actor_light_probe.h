// actor_light_probe.h - the shared per-actor light probe (lane lp2, character lighting phase 2, 2026-10-14).
//
// One record per actor per frame, built by native_actor_fast.cpp (ACTOR_PROBE_LIGHT=1/2) from the GX light set the
// game's own LightSetModel selected for that actor (room lights and dynamic lights: muzzle flash, fire, effect lights).
// There is no offline table: the GameCube light data already on the disc (room .lit cuts + core lights) is the source,
// and the probe is its L0 + L1 fit at the actor's origin. Consumers (character lighting; the shadow lane's modifier
// volumes) read the same record, so the light and the shadow always agree.
//
// Format contract (owner: lane lp2; additions append fields, never reorder):
//   dir        view space (camera space of the frame it was built in), unit vector from the actor TOWARD the dominant
//              light. A shadow is cast along -dir. All zero when the lights cancel or there are none (no direction).
//   color      directional colour in GX units / 255 (attenuated at the actor's origin; 1.0 = a full-white GX light).
//   ambient    GX ambient / 255 + the folded residual of the other lights (0.25 x (1 - coherence) x their sum).
//   coherence  |sum luma(C_i) l_i| / sum luma(C_i), 0..1: 1 = one clear light (hard shadow), 0 = light from all sides
//              (no visible shadow). Suggested shadow strength = coherence x luma(color) / (luma(color) + luma(ambient)).
//   serial     the actor-frame serial the record was built in (compare two calls to see whether it is this frame's).
// Extension terms (zero in the default build; reserved so later options plug in without a redesign):
//   extra_n / extra_index  ACTOR_PROBE_LIGHT_EXTRA (options branch): source-light indices evaluated per part instead of
//              being folded into the probe (0..2).
//   flash      a global additive flash/tint term (explosion, flash grenade); characters would add it to ambient and the
//              world would take it through a post tint (Filter00 / POST_F00 path). Always 0 today.
#pragma once
#ifdef __cplusplus
extern "C" {
#endif
struct Re4dcLightProbe {
    unsigned serial;
    float dir[3];
    float color[3];
    float ambient[3];
    float coherence;
    unsigned char extra_n;
    unsigned char extra_index[2];
    unsigned char reserved0;
    float flash[3];
};
// The newest probe of `model` (a cModel*): 1 and *out filled, or 0 (no probe built for it in the last two frames, or
// ACTOR_PROBE_LIGHT=0). Valid after the model's first owner draw of the frame; before it, the previous frame's record.
int re4dc_actor_light_probe(const void* model, struct Re4dcLightProbe* out);
#ifdef __cplusplus
}
#endif
