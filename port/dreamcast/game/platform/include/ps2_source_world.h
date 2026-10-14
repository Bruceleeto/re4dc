#pragma once
// Default-off, r200 event-image presentation only. All ownership is a bounded
// read of the existing accepted OTs, scroll work table and loaded native owner.
class cModel;
struct Re4dcSourceWorldTexture { unsigned generation,crc,fnv,width,height,bytes; };
extern "C" {
int re4dc_ps2_source_package(unsigned* generation);
int re4dc_ps2_source_texture(unsigned generation,Re4dcSourceWorldTexture* out);
int re4dc_ps2_source_draw(unsigned generation);
int re4dc_ps2_source_passes_complete();
void re4dc_source_world_flush_result(unsigned native_frame,int complete);
int re4dc_scroll_source_member(cModel*,unsigned serial,unsigned* work);
int re4dc_source_world_prepare(unsigned native_frame,unsigned* generation);
int re4dc_source_world_current(unsigned native_frame,unsigned generation);
void re4dc_source_world_prepared(unsigned native_frame,unsigned generation,int ready);
}
