#pragma once
// Selectable immutable EVD backing. It is not a mutable ARAM implementation.
#ifndef RE4DC_EVENT_FILES
#define RE4DC_EVENT_FILES 0
#endif
#define RE4DC_EVENT_FILE_FLAG 4
struct Re4dcEventFileStats {
    unsigned prepared, installed, moves, failures;
    unsigned bytes_read, worst_wait_us, metadata_bytes_read;
};
extern "C" {
int re4dc_event_file_name(const char* name);
int re4dc_event_file_prepare(const char* name, unsigned bytes);
// Binds an explicitly reviewed deferred-presentation contract to the existing
// qualification certificate. Unknown identities must keep the normal path.
int re4dc_event_file_reference(const char* name, unsigned bytes, unsigned certificate_crc);
int re4dc_event_file_install(const char* name, unsigned bytes, void* destination);
void re4dc_event_file_moved();
const Re4dcEventFileStats* re4dc_event_file_stats();
// Source unit ownership remains in DC; no duplicate range registry.
int re4dc_event_file_range(unsigned address, unsigned bytes);
void re4dc_event_file_reject_swap();
int re4dc_dvd_native_path(const char* name, char* output, unsigned capacity);
}

#if RE4DC_CABIN_SOURCE
extern "C" {
int re4dc_cabin_carrier_prepare(void*,const char*,unsigned,unsigned);
int re4dc_cabin_carrier_clear(void*);
int re4dc_cabin_carriers_reset();
int re4dc_cabin_carrier_rebase(void*,unsigned);
int re4dc_cabin_carrier_install(void*,void*);
unsigned re4dc_cabin_carrier_reserved(const void*);
int re4dc_cabin_carrier_unit_available(const void*);
int re4dc_cabin_carrier_mram_move(const void*,const void*);
int re4dc_cabin_carrier_park(void*,unsigned*);
int re4dc_cabin_carrier_before_free(const void*);
// Read-only lifetime and allocation check; it never clears a source unit.
int re4dc_cabin_carriers_before_heap(const void*,unsigned);
// Commit only after all affected ranges and media owners have passed preflight.
int re4dc_cabin_carriers_retire_heap(const void*,unsigned);
// Suspension is nondestructive: it cannot retire any overlapping owned bytes.
int re4dc_cabin_carriers_suspendable(const void*,unsigned);
void re4dc_cabin_carriers_before_events();
void re4dc_cabin_carriers_after_events();
int re4dc_cabin_carrier_event(const void*,const void*,const char*);
void re4dc_cabin_carrier_event_deleted(const void*);
// Same-generation before/after receipt for the void source MemorySwap API.
unsigned re4dc_cabin_carrier_reverse_token(const void*,const void*,const void*,unsigned,int*);
int re4dc_cabin_carrier_reverse_complete(const void*,const void*,const void*,unsigned,int,unsigned);
int re4dc_cabin_carrier_swap_begin(void*,unsigned,unsigned);
int re4dc_cabin_carrier_swap_scope(unsigned,unsigned);
int re4dc_cabin_carrier_swap_end(unsigned,int,const void*);
int re4dc_cabin_carrier_dma_admit(const void*,unsigned,unsigned,unsigned,unsigned);
int re4dc_cabin_carrier_dma_owned(const void*);
int re4dc_cabin_carrier_dma_copy(const void*,unsigned,unsigned,unsigned,unsigned);
const void* re4dc_cabin_carrier_dma_callback(unsigned);
int re4dc_cabin_carrier_dma_release(const void*,int);
}
#endif
