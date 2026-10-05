/* re4dc_fsca.h -- GAME_TRIG_FSCA / GAME_ROT_FSCA (game30.mk; lane fm 2026-10-05). Last-bit FP policy
 * (user decision 2026-09-23 (3)), NOT exact: sin and cos of one float angle from the SH-4 FSCA instruction
 * plus a first-order residual correction.
 *
 *   k  = ftrc(x * 65536/(2 pi))                  (FPUL; FSCA uses its low 16 bits: angle k * 2 pi/65536)
 *   s0, c0 = FSCA(k)                              (the hardware table: Flycast's fsca-table.h is a dump of it)
 *   d  = (x - k * S1) - k * S2                    (S1 = 2 pi/65536 to 8 significant bits: k * S1 is exact for
 *                                                  |k| <= 2^16; S2 = the rest; d in (-step, step), step 9.6e-5)
 *   sin x = s0 + c0 * d,  cos x = c0 - s0 * d     (sin(a + d) = sin a cos d + cos a sin d; the dropped
 *                                                  s0 * d^2/2 term is below 4.6e-9)
 *
 * For |x| <= 2 pi (word test RE4DC_FSCA_XMAX_BITS; |k| <= 65536). The callers keep the exact results of the
 * game's fdlibm for |x| < 2^-27 (sin = x, cos = 1: +-0 keeps its sign) and their own exact or reduced paths
 * outside the range. Accuracy is absolute, like FTRV / FIPR (the GAME_SKEL_FTRV / GAME_PWC_KERNEL=3
 * precedent): the table's own error is at most 1.12e-7 (2^-23.09, results near +-1) and 1.5e-8 for small
 * results; host check over every float input: tools/game30/trig_fsca_check.sh.
 * Deterministic on the SH-4 and in Flycast (FSCA from the hardware table, IEEE single fmul / fadd);
 * -ffp-contract=off in the including objects keeps the two products and two sums separate.
 */
#ifndef RE4DC_FSCA_H
#define RE4DC_FSCA_H

#define RE4DC_FSCA_XMAX_BITS 0x40C90FDB  /* 6.2831855f: 2 pi rounded up; x * K rounds to at most 65536 */
#define RE4DC_FSCA_TINY_BITS 0x32000000  /* 2^-27 */

#define RE4DC_FSCA_K 10430.378f          /* 65536 / (2 pi), 0x4622f983 */
#define RE4DC_FSCA_S1 9.5844268798828125e-05f   /* 0x38c90000: 1.5703125 * 2^-14 (8 significant bits) */
#define RE4DC_FSCA_S2 2.9530444e-08f     /* 0x32fdaa22 = float(2 pi / 65536 - S1); S1 + S2 - step ~ 1.6e-16 */

#if defined(__sh__)
/* FSCA writes the pair DR<n> (fr<2n> = sin, fr<2n+1> = cos); the pair is fixed per expansion. */
#define RE4DC_FSCA_PAIR(k, s0, c0, FRS, FRC, DR)                                                   \
    do {                                                                                        \
        register float re4dc_fs_ __asm__(FRS);                                                  \
        register float re4dc_fc_ __asm__(FRC);                                                  \
        __asm__("fsca\tfpul," DR : "=f"(re4dc_fs_), "=f"(re4dc_fc_) : "y"(k));                  \
        (s0) = re4dc_fs_;                                                                       \
        (c0) = re4dc_fc_;                                                                       \
    } while (0)
#else
/* Host check builds (tools/game30/trig_fsca_check.c): FSCA from the dumped table, 65536 (sin, cos) pairs. */
extern const float* re4dc_fsca_host_table;
#define RE4DC_FSCA_PAIR(k, s0, c0, FRS, FRC, DR)                                                   \
    do {                                                                                        \
        const unsigned re4dc_i_ = (unsigned) (k) & 0xFFFFu;                                     \
        (s0) = re4dc_fsca_host_table[2 * re4dc_i_];                                             \
        (c0) = re4dc_fsca_host_table[2 * re4dc_i_ + 1];                                         \
    } while (0)
#endif

/* sin / cos of x, |x| <= 2 pi (callers test RE4DC_FSCA_XMAX_BITS first). */
#define RE4DC_FSCA_SINCOS(x, s, c, FRS, FRC, DR)                                                   \
    do {                                                                                        \
        const float re4dc_x_ = (x);                                                             \
        const int re4dc_k_ = (int) (re4dc_x_ * RE4DC_FSCA_K);                                   \
        float re4dc_s0_, re4dc_c0_;                                                             \
        RE4DC_FSCA_PAIR(re4dc_k_, re4dc_s0_, re4dc_c0_, FRS, FRC, DR);                          \
        const float re4dc_kf_ = (float) re4dc_k_;                                               \
        const float re4dc_d_ = (re4dc_x_ - re4dc_kf_ * RE4DC_FSCA_S1) - re4dc_kf_ * RE4DC_FSCA_S2; \
        (s) = re4dc_s0_ + re4dc_c0_ * re4dc_d_;                                                 \
        (c) = re4dc_c0_ - re4dc_s0_ * re4dc_d_;                                                 \
    } while (0)

/* The same after an exact reduction x = n * pi/2 + y0 + y1 (|y0| <= pi/4, game30_trig.c's lrem_pio2f):
   FSCA of index ftrc(y0 * K) + n * 16384, the residual from y0 plus the tail y1. */
#define RE4DC_FSCA_SINCOS_RED(y0, y1, n, s, c, FRS, FRC, DR)                                       \
    do {                                                                                        \
        const float re4dc_y_ = (y0);                                                            \
        const int re4dc_k_ = (int) (re4dc_y_ * RE4DC_FSCA_K);                                   \
        const int re4dc_q_ = re4dc_k_ + (n) * 16384;                                            \
        float re4dc_s0_, re4dc_c0_;                                                             \
        RE4DC_FSCA_PAIR(re4dc_q_, re4dc_s0_, re4dc_c0_, FRS, FRC, DR);                          \
        const float re4dc_kf_ = (float) re4dc_k_;                                               \
        const float re4dc_d_ = ((re4dc_y_ - re4dc_kf_ * RE4DC_FSCA_S1) - re4dc_kf_ * RE4DC_FSCA_S2) + (y1); \
        (s) = re4dc_s0_ + re4dc_c0_ * re4dc_d_;                                                 \
        (c) = re4dc_c0_ - re4dc_s0_ * re4dc_d_;                                                 \
    } while (0)

#endif /* RE4DC_FSCA_H */
