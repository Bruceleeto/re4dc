#include "ps2_enemy_ch23.h"
#if defined(RE4DC_ROUTE_CH23) && RE4DC_ROUTE_CH23 && \
    defined(RE4DC_PS2_ENEMY_RULES) && RE4DC_PS2_ENEMY_RULES
#include <stdio.h>
#include <string.h>

/* This translation unit is built only for ROUTE_CH23 && PS2_ENEMY_RULES.
 * The generator emits private game bytes only after the room activation
 * evidence is qualified. No external reads, allocation, or per-frame work.
 */
struct Ps2EnemyCh23Row {
    unsigned short index;
    unsigned char data[32];
};
struct Ps2EnemyCh23List {
    int list_no;
    const Ps2EnemyCh23Row *baseline;
    unsigned baseline_count;
    const Ps2EnemyCh23Row *replacement;
    unsigned replacement_count;
};
#include "ps2_enemy_ch23_data.inc"

extern "C" int re4dc_ps2EnemyListCh23(int list_no, void *data, unsigned size)
{
    const Ps2EnemyCh23List *list = NULL;
    unsigned i, j;
    for (i = 0; i < sizeof(ps2_enemy_ch23_lists) / sizeof(ps2_enemy_ch23_lists[0]); ++i) {
        if (ps2_enemy_ch23_lists[i].list_no == list_no) {
            list = &ps2_enemy_ch23_lists[i];
            break;
        }
    }
    if (!list) return 0;
    if (!data) {
        printf("PS2_ENEMY_CH23: FAIL list=%d null buffer\n", list_no);
        return -1;
    }
    unsigned char *bytes = static_cast<unsigned char *>(data);
    /* Check every byte of every selected row, including unchanged rooms,
     * rotations, HP, emset_no and reserved bytes, before writing anything.
     */
    for (i = 0; i < list->baseline_count; ++i) {
        const Ps2EnemyCh23Row &row = list->baseline[i];
        const unsigned offset = static_cast<unsigned>(row.index) * 32;
        if (offset > size || size - offset < 32) {
            printf("PS2_ENEMY_CH23: FAIL list=%d row=%u buffer=%u\n", list_no,
                   static_cast<unsigned>(row.index), size);
            return -1;
        }
        for (j = 0; j < 32; ++j) {
            if (bytes[offset + j] != row.data[j]) {
                printf("PS2_ENEMY_CH23: FAIL list=%d row=%u byte=%u expected=%02x got=%02x\n",
                       list_no, static_cast<unsigned>(row.index), j,
                       static_cast<unsigned>(row.data[j]),
                       static_cast<unsigned>(bytes[offset + j]));
                return -2;
            }
        }
    }
    for (i = 0; i < list->replacement_count; ++i) {
        const Ps2EnemyCh23Row &row = list->replacement[i];
        memcpy(bytes + static_cast<unsigned>(row.index) * 32, row.data, 32);
    }
    printf("PS2_ENEMY_CH23: list=%d verified=%u replaced=%u full32=1\n",
           list_no, list->baseline_count, list->replacement_count);
    return 1;
}
#endif
