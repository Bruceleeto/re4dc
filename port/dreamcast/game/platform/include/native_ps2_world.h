#pragma once
// Only the ordinary r101 coarse image calls draw. No gameplay state is written.
extern "C" int re4dc_ps2_world_draw(unsigned room,const float screen[3][4],float far);
// True only for the current frame's unflushed PT/TR work.
extern "C" int re4dc_ps2_world_pending();
extern "C" void re4dc_ps2_world_flush();
extern "C" void re4dc_ps2_world_retire();
// PS2_WORLD_MESH (native_static.cpp): the converted R4IM world; camera from coarse.cpp setup_camera.
extern "C" void re4dc_ps2_mesh_camera(const float* view,const float* projection,const float* viewport);
extern "C" int re4dc_ps2_mesh_draw(unsigned pass,float zfar);
extern "C" void re4dc_ps2_mesh_log(unsigned frame);
extern "C" void re4dc_ps2_mesh_retire();
