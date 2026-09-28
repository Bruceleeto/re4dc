#pragma once
// Only the ordinary r101 coarse image calls draw. No gameplay state is written.
extern "C" int re4dc_ps2_world_draw(unsigned room,const float screen[3][4],float far);
// True only for the current frame's unflushed PT/TR work.
extern "C" int re4dc_ps2_world_pending();
extern "C" void re4dc_ps2_world_flush();
extern "C" void re4dc_ps2_world_retire();
