#pragma once
// Default-off, r200 event-image presentation only. All ownership is a bounded
// read of the existing accepted OTs, scroll work table and loaded native owner.
class cModel;
// Scalar snapshot only: diagnostics never read a rejected allocation.
struct Re4dcSourceWorldOtMemory { unsigned long begin,end;unsigned epoch,live; };
struct Re4dcSourceWorldTexture { unsigned generation,crc,fnv,width,height,bytes; };
extern "C" {
unsigned re4dc_source_world_ot_epoch();
void re4dc_source_world_ot_memory(Re4dcSourceWorldOtMemory*);
int re4dc_source_world_ot_retained(const void*,unsigned bytes);
int re4dc_ps2_source_package(unsigned* generation);
int re4dc_ps2_source_texture(unsigned generation,Re4dcSourceWorldTexture* out);
int re4dc_ps2_source_draw(unsigned generation);
int re4dc_ps2_source_passes_complete();
void re4dc_source_world_flush_result(unsigned native_frame,int complete);
int re4dc_scroll_source_member(cModel*,unsigned serial,unsigned* work);
// Exact currently published source pool slots, before any candidate field read.
int re4dc_source_world_pool(const void*,unsigned type);
int re4dc_scroll_source_probe(cModel*,unsigned* serial,unsigned* work);
int re4dc_source_world_prepare(unsigned native_frame,unsigned* generation);
int re4dc_source_world_current(unsigned native_frame,unsigned generation);
#if RE4DC_PS2_WORLD_TRANSITION_PIN
// Texture cache retention only; never authorizes source geometry consumption.
int re4dc_source_world_transition(unsigned native_frame,unsigned generation);
#endif
void re4dc_source_world_prepared(unsigned native_frame,unsigned generation,int ready);
}
