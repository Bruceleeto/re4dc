/* trig_fsca_check.c: the numerical check of GAME_TRIG_FSCA / GAME_ROT_FSCA (lane fm 2026-10-05; last-bit FP
 * policy). re4dc_sincosf of port/dreamcast/game/game30_trig.c built with RE4DC_SINCOS=1 RE4DC_TRIG_LEAN=1
 * RE4DC_TRIG_FSCA=1 (FSCA from the dumped hardware table, platform/include/re4dc_fsca.h's host path) against
 * re4dc_exact_sincosf (the exact GAME_TRIG_LEAN function, bit-identical to the game's fdlibm) and against the
 * true sin / cos (long double), for every one of the 2^32 float inputs.
 * Host float math (SSE, -ffp-contract=off) with MXCSR FTZ+DAZ, the SH-4 FPSCR.DN=1 behaviour; the FSCA table
 * is built as Flycast's sh4_rom.cpp builds it from fsca-table.h (0x8000 sin words for 0 .. pi, negated for
 * pi .. 2 pi, cos(i) = sin(i + 0x4000)).
 * Build/run: tools/game30/trig_fsca_check.sh <tree> <fsca-table.h>. Reports, per output and per argument
 * range (|x| < 2^-27, direct |x| <= 2 pi, reduced |x| <= 2^7 pi/2, beyond): inputs, identical words, the
 * |FSCA - exact| distribution and maximum (with its input), results more than 4 of their own ulps apart or
 * of opposite sign, and the maximum |error vs the true value| of both. Exit 0 when the beyond / tiny ranges
 * are identical and the direct / reduced maxima stay below 2^-22. */
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <xmmintrin.h>

#include "../../game/platform/include/re4dc_fsca.h"

void re4dc_sincosf(float, float*, float*);
void re4dc_exact_sincosf(float, float*, float*);

static float table[65536 * 2];
const float* re4dc_fsca_host_table = table;

#define NT 16
#define NR 4   /* 0 tiny, 1 direct, 2 reduced, 3 beyond */
#define NB 9   /* identical, <= 2^-27 .. 2^-21, above */
typedef struct {
    uint64_t n[NR], hist[NR][2][NB], rel4[NR][2];
    float maxd[NR][2], maxe_new[NR][2], maxe_ref[NR][2];
    uint32_t maxx[NR][2];
} Acc;
static Acc acc[NT];

static inline uint32_t bits(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }

static void note(Acc* a, int r, int o, float x, float got, float ref, long double t)
{
    const uint32_t gb = bits(got), rb = bits(ref);
    float d = fabsf(got - ref);
    int h;
    if (gb == rb) h = 0;
    else if (d <= 0x1p-27f) h = 1;
    else if (d <= 0x1p-26f) h = 2;
    else if (d <= 0x1p-25f) h = 3;
    else if (d <= 0x1p-24f) h = 4;
    else if (d <= 0x1p-23f) h = 5;
    else if (d <= 0x1p-22f) h = 6;
    else if (d <= 0x1p-21f) h = 7;
    else h = 8;
    a->hist[r][o][h]++;
    if (h && d > a->maxd[r][o]) { a->maxd[r][o] = d; a->maxx[r][o] = bits(x); }
    const int64_t u = (int64_t) (int32_t) gb - (int64_t) (int32_t) rb;
    if (((gb ^ rb) >> 31) || u > 4 || u < -4) a->rel4[r][o]++;
    const float en = (float) fabsl((long double) got - t), er = (float) fabsl((long double) ref - t);
    if (en > a->maxe_new[r][o]) a->maxe_new[r][o] = en;
    if (er > a->maxe_ref[r][o]) a->maxe_ref[r][o] = er;
}

static void* run(void* arg)
{
    const int t = (int) (intptr_t) arg;
    Acc* a = &acc[t];
    _mm_setcsr(_mm_getcsr() | 0x8040);   /* FTZ | DAZ */
    const uint64_t span = (1ull << 32) / NT;
    for (uint64_t k = t * span; k < (t + 1) * span; k++) {
        const uint32_t u = (uint32_t) k, ix = u & 0x7fffffffu;
        if (ix >= 0x7f800000u) continue;   /* inf / NaN: the exact path, compared below by bits only */
        float x, s, c, rs, rc;
        memcpy(&x, &u, 4);
        const int r = ix < 0x32000000u ? 0 : ix <= 0x40C90FDBu ? 1 : ix <= 0x43490f80u ? 2 : 3;
        re4dc_sincosf(x, &s, &c);
        re4dc_exact_sincosf(x, &rs, &rc);
        a->n[r]++;
        note(a, r, 0, x, s, rs, sinl((long double) x));
        note(a, r, 1, x, c, rc, cosl((long double) x));
    }
    return 0;
}

static int load_table(const char* path)
{
    FILE* f = fopen(path, "r");
    if (!f) { perror(path); return 0; }
    static uint32_t w[0x8000];
    int n = 0;
    char tok[64];
    while (n < 0x8000 && fscanf(f, " %63[^,\n]%*[,\n]", tok) == 1) {
        if (strncmp(tok, "0x", 2) == 0 || strncmp(tok, "0X", 2) == 0) w[n++] = (uint32_t) strtoul(tok, 0, 16);
    }
    fclose(f);
    if (n != 0x8000) { fprintf(stderr, "%s: %d words, want 32768\n", path, n); return 0; }
    for (int i = 0; i < 0x10000; i++) {
        float v;
        memcpy(&v, &w[i & 0x7FFF], 4);
        table[2 * i] = i < 0x8000 ? v : -v;
    }
    for (int i = 0; i < 0x10000; i++) table[2 * i + 1] = table[2 * ((i + 0x4000) & 0xFFFF)];
    return 1;
}

int main(int argc, char** argv)
{
    if (argc < 2 || !load_table(argv[1])) { fprintf(stderr, "usage: trig_fsca_check <fsca-table.h>\n"); return 2; }
    /* the non-finite inputs: bits only */
    uint64_t nonfinite_bad = 0;
    for (uint64_t k = 0; k < (1ull << 32); k += 1) {
        const uint32_t u = (uint32_t) k;
        if ((u & 0x7fffffffu) < 0x7f800000u) { k |= 0x7fffffull; continue; }   /* skip to the next exponent block */
        float x, s, c, rs, rc;
        memcpy(&x, &u, 4);
        re4dc_sincosf(x, &s, &c);
        re4dc_exact_sincosf(x, &rs, &rc);
        if (bits(s) != bits(rs) || bits(c) != bits(rc)) nonfinite_bad++;
    }
    pthread_t th[NT];
    for (int t = 0; t < NT; t++) pthread_create(&th[t], 0, run, (void*) (intptr_t) t);
    Acc z;
    memset(&z, 0, sizeof z);
    for (int t = 0; t < NT; t++) {
        pthread_join(th[t], 0);
        for (int r = 0; r < NR; r++) {
            z.n[r] += acc[t].n[r];
            for (int o = 0; o < 2; o++) {
                for (int h = 0; h < NB; h++) z.hist[r][o][h] += acc[t].hist[r][o][h];
                z.rel4[r][o] += acc[t].rel4[r][o];
                if (acc[t].maxd[r][o] > z.maxd[r][o]) { z.maxd[r][o] = acc[t].maxd[r][o]; z.maxx[r][o] = acc[t].maxx[r][o]; }
                if (acc[t].maxe_new[r][o] > z.maxe_new[r][o]) z.maxe_new[r][o] = acc[t].maxe_new[r][o];
                if (acc[t].maxe_ref[r][o] > z.maxe_ref[r][o]) z.maxe_ref[r][o] = acc[t].maxe_ref[r][o];
            }
        }
    }
    static const char* rn[NR] = {"tiny |x|<2^-27", "direct |x|<=2pi", "reduced |x|<=2^7pi/2", "beyond"};
    static const char* on[2] = {"sin", "cos"};
    int ok = nonfinite_bad == 0;
    printf("non-finite inputs: %s\n", nonfinite_bad ? "MISMATCH" : "identical words");
    for (int r = 0; r < NR; r++) {
        for (int o = 0; o < 2; o++) {
            const uint64_t* h = z.hist[r][o];
            printf("%-21s %s inputs %10llu same %10llu  |d|<=2^-27 %10llu 2^-26 %10llu 2^-25 %10llu 2^-24 %10llu "
                   "2^-23 %9llu 2^-22 %8llu 2^-21 %6llu >2^-21 %llu  max %.3g (2^%.2f) at %08x  rel>4ulp %llu  "
                   "err vs true: fsca %.3g exact %.3g\n",
                   rn[r], on[o], (unsigned long long) z.n[r], (unsigned long long) h[0], (unsigned long long) h[1],
                   (unsigned long long) h[2], (unsigned long long) h[3], (unsigned long long) h[4],
                   (unsigned long long) h[5], (unsigned long long) h[6], (unsigned long long) h[7],
                   (unsigned long long) h[8], z.maxd[r][o], z.maxd[r][o] > 0 ? log2(z.maxd[r][o]) : -999.0,
                   z.maxx[r][o], (unsigned long long) z.rel4[r][o], z.maxe_new[r][o], z.maxe_ref[r][o]);
            if ((r == 0 || r == 3) && h[0] != z.n[r]) ok = 0;
            if ((r == 1 || r == 2) && z.maxd[r][o] >= 0x1p-22f) ok = 0;
        }
    }
    printf("%s\n", ok ? "PASS: tiny / beyond / non-finite identical, direct / reduced |FSCA - exact| < 2^-22"
                      : "FAIL");
    return ok ? 0 : 1;
}
