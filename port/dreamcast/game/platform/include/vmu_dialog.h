#ifndef RE4DC_VMU_DIALOG_H
#define RE4DC_VMU_DIALOG_H

/* Presentation only. The virtual CARD channel is not a physical Maple port. */
#ifndef RE4DC_VMU_DIALOG
#define RE4DC_VMU_DIALOG 0
#endif
#if RE4DC_VMU_DIALOG
enum {
    RE4DC_VMU_DIALOG_SELECTED = 1,
    RE4DC_VMU_DIALOG_COUNTS = 2,
    RE4DC_VMU_DIALOG_LCD = 4
};
struct Re4dcVmuDialogSnapshot {
    unsigned flags;
    unsigned port;          /* 0..3 => A..D */
    unsigned slot;          /* actual Maple unit 1..2 */
    unsigned free_blocks;   /* cached free 512-byte blocks, only with COUNTS */
    unsigned free_files;    /* cached free directory entries, only with COUNTS */
    unsigned system_blocks;/* existing VMS + R4 header + system payload, rounded */
};
/* No I/O, allocation, worker join, save decision or device selection. Returns 0
 * for the raw GC test backend. A missing/unmounted device is not zero free space. */
extern "C" int re4dc_vmu_dialog_snapshot(Re4dcVmuDialogSnapshot* out);
#endif
#endif
