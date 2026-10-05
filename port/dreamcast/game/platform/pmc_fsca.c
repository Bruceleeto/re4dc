/* platform/pmc_fsca.c -- GAME_ROT_FSCA (game30.mk; lane fm 2026-10-05). Last-bit FP policy (user decision
 * 2026-09-23 (3)), NOT exact. The C twin of platform/pmc_fsca_sh4.S, the loop that replaces platform/pmc_sh4.S
 * (GAME_PMC_KERNEL) as re4dc_pmc_run: cModel::partsMatCalc's four calls per part (RotMatrix(l_mat, &ang),
 * TransMatrix(l_mat, &pos), ScaleMatrix(l_mat, &scale), PSMTXCopy(l_mat, mat)) with the three angles' sin and cos
 * from FSCA plus the residual correction (include/re4dc_fsca.h) instead of RotMatrix's memo probe or its three
 * re4dc_sincosf calls.
 *
 * pmc_words: one part's twelve l_mat words. Per angle: |x| < 2^-27 keeps fdlibm's exact (x, 1), |x| > 2 pi (or
 * NaN) takes re4dc_sincosf (with GAME_TRIG_FSCA=1 the same words for the same angle, so the parts and RotMatrix's
 * other callers agree), else FSCA. Then RotMatrix's products and sums in its order (szcx, szsx, czsx, czcx, then
 * m[0][0] .. m[2][2], -sy), the 3x3 words times scale_c (ScaleMatrix), the translation column = pos (TransMatrix
 * after RotMatrix's zeros; moved, bits unchanged); mat = l_mat (PSMTXCopy).
 * re4dc_pmc_part_slow: the assembly loop's path for a part with an angle beyond 2 pi or NaN (pmc_words + stores).
 * =2: check build. The assembly loop runs as re4dc_pmc_run_asm, then every part is recomputed here: the C twin's
 * words against the 24 stored words (all must match: "twin" in the log line), and the exact rotation x scale
 * words (re4dc_exact_sincosf with GAME_TRIG_FSCA, else re4dc_sincosf) against the stored ones, differences counted
 * ("ROTF" log lines); the parts keep the assembly loop's words (the run behaves as =1).
 *
 * cParts offsets (static_asserts in model.cpp): mat 0x0C, l_mat 0x3C, pos 0x94, ang 0xA0, scale 0xAC,
 * pList 0xF4. Compiled like game30_trig.c (-O2 -ffp-contract=off).
 */
#include "include/re4dc_fsca.h"

typedef unsigned int pmc_u32;

void re4dc_sincosf(float x, float* s, float* c);
#if defined(RE4DC_TRIG_FSCA) && RE4DC_TRIG_FSCA
void re4dc_exact_sincosf(float x, float* s, float* c);
#define PMC_EXACT_SINCOS re4dc_exact_sincosf
#else
#define PMC_EXACT_SINCOS re4dc_sincosf
#endif

/* The part's fields through aligned may_alias pointers (the cParts words are 4-byte aligned). */
typedef float pmc_f32a __attribute__((may_alias));
typedef pmc_u32 pmc_u32a __attribute__((may_alias));
#define pmc_word(p, off) (*(const pmc_u32a*) ((p) + (off)))
#define pmc_float(p, off) (*(const pmc_f32a*) ((p) + (off)))

/* One angle: fdlibm's exact tiny results, re4dc_sincosf beyond 2 pi (or NaN), else FSCA. */
static inline __attribute__((always_inline)) void pmc_angle(pmc_u32 w, float x, float* s, float* c)
{
    if ((w & 0x7fffffffu) > RE4DC_FSCA_XMAX_BITS) {
        re4dc_sincosf(x, s, c);
    } else if ((w & 0x7fffffffu) < RE4DC_FSCA_TINY_BITS) {
        *s = x;
        *c = 1.0f;
    } else {
        float fs, fc;
        RE4DC_FSCA_SINCOS(x, fs, fc, "fr2", "fr3", "dr2");
        *s = fs;
        *c = fc;
    }
}

/* One part's twelve l_mat words (row-major 3x4: the 3x3 rotation x scale, the pos column). */
static void pmc_words(const unsigned char* p, float* o)
{
    float sx, cx, sy, cy, sz, cz;
    pmc_angle(pmc_word(p, 0xA0), pmc_float(p, 0xA0), &sx, &cx);
    pmc_angle(pmc_word(p, 0xA4), pmc_float(p, 0xA4), &sy, &cy);
    pmc_angle(pmc_word(p, 0xA8), pmc_float(p, 0xA8), &sz, &cz);
    /* RotMatrix (math_sub.cpp), same operations in the same order */
    const float szcx = sz * cx;
    const float szsx = sz * sx;
    const float czsx = cz * sx;
    const float czcx = cz * cx;
    const float m00 = cz * cy;
    const float m01 = czsx * sy - szcx;
    const float m02 = czcx * sy + szsx;
    const float m10 = sz * cy;
    const float m11 = szsx * sy + czcx;
    const float m12 = szcx * sy - czsx;
    const float m20 = -sy;
    const float m21 = cy * sx;
    const float m22 = cy * cx;
    /* ScaleMatrix: column c times scale_c; TransMatrix: the pos column */
    const float scx = pmc_float(p, 0xAC), scy = pmc_float(p, 0xB0), scz = pmc_float(p, 0xB4);
    o[0] = m00 * scx;
    o[1] = m01 * scy;
    o[2] = m02 * scz;
    o[4] = m10 * scx;
    o[5] = m11 * scy;
    o[6] = m12 * scz;
    o[8] = m20 * scx;
    o[9] = m21 * scy;
    o[10] = m22 * scz;
    ((pmc_u32a*) o)[3] = pmc_word(p, 0x94);
    ((pmc_u32a*) o)[7] = pmc_word(p, 0x98);
    ((pmc_u32a*) o)[11] = pmc_word(p, 0x9C);
}

/* The assembly loop's path for a part with an angle beyond 2 pi or NaN: the twin's words into l_mat and mat. */
void re4dc_pmc_part_slow(unsigned char* p)
{
    float o[12];
    pmc_words(p, o);
    pmc_u32a* l = (pmc_u32a*) (p + 0x3C);
    pmc_u32a* m = (pmc_u32a*) (p + 0x0C);
    for (int i = 0; i < 12; i++) {
        const pmc_u32 v = ((const pmc_u32a*) o)[i];
        l[i] = v;
        m[i] = v;
    }
}

#if defined(RE4DC_ROT_FSCA) && RE4DC_ROT_FSCA == 2
void re4dc_log(const char* fmt, ...);
void* re4dc_pmc_run_asm(void* first);
/* =2 statistics: parts, stored words that differ from the C twin (l_mat and mat, 24 per part), rotation x scale
   words identical to the exact ones, |difference| buckets <= 2^-27 .. 2^-21 and above, the largest |difference|
   (word) with its angle words. */
static pmc_u32 rotf_parts, rotf_twin, rotf_hist[9], rotf_max, rotf_max_ang[3];

static void rotf_check(const unsigned char* p)
{
    float sx, cx, sy, cy, sz, cz;
    float r[9];
    PMC_EXACT_SINCOS(pmc_float(p, 0xA0), &sx, &cx);
    PMC_EXACT_SINCOS(pmc_float(p, 0xA4), &sy, &cy);
    PMC_EXACT_SINCOS(pmc_float(p, 0xA8), &sz, &cz);
    {
        const float szcx = sz * cx, szsx = sz * sx, czsx = cz * sx, czcx = cz * cx;
        const float scx = pmc_float(p, 0xAC), scy = pmc_float(p, 0xB0), scz = pmc_float(p, 0xB4);
        r[0] = (cz * cy) * scx;
        r[1] = (czsx * sy - szcx) * scy;
        r[2] = (czcx * sy + szsx) * scz;
        r[3] = (sz * cy) * scx;
        r[4] = (szsx * sy + czcx) * scy;
        r[5] = (szcx * sy - czsx) * scz;
        r[6] = (-sy) * scx;
        r[7] = (cy * sx) * scy;
        r[8] = (cy * cx) * scz;
    }
    static const unsigned char idx[9] = {0, 1, 2, 4, 5, 6, 8, 9, 10};
    for (int i = 0; i < 9; i++) {
        const float g = pmc_float(p, 0x3C + 4 * idx[i]);
        float d = g - r[i];
        const pmc_u32 gb = pmc_word(p, 0x3C + 4 * idx[i]), rb = *(const pmc_u32a*) &r[i];
        if (d < 0.0f) d = -d;
        const pmc_u32 db = *(const pmc_u32a*) &d;
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
        rotf_hist[h]++;
        if (h && db > rotf_max) {
            rotf_max = db;
            rotf_max_ang[0] = pmc_word(p, 0xA0);
            rotf_max_ang[1] = pmc_word(p, 0xA4);
            rotf_max_ang[2] = pmc_word(p, 0xA8);
        }
    }
}

void* re4dc_pmc_run(void* first)
{
    re4dc_pmc_run_asm(first);
    for (const unsigned char* p = (const unsigned char*) first; p; p = *(unsigned char* const*) (p + 0xF4)) {
        float o[12];
        pmc_words(p, o);
        for (int i = 0; i < 12; i++) {
            const pmc_u32 v = ((const pmc_u32a*) o)[i];
            rotf_twin += (pmc_word(p, 0x3C + 4 * i) != v) + (pmc_word(p, 0x0C + 4 * i) != v);
        }
        rotf_check(p);
        if ((++rotf_parts & 0x3FFF) == 0) {
            re4dc_log("ROTF parts=%u twin=%u words same=%u le27=%u le26=%u le25=%u le24=%u le23=%u le22=%u le21=%u "
                      "gt21=%u max=%08x ang=%08x,%08x,%08x\n",
                      rotf_parts, rotf_twin, rotf_hist[0], rotf_hist[1], rotf_hist[2], rotf_hist[3], rotf_hist[4],
                      rotf_hist[5], rotf_hist[6], rotf_hist[7], rotf_hist[8], rotf_max, rotf_max_ang[0],
                      rotf_max_ang[1], rotf_max_ang[2]);
        }
    }
    return 0;
}
#endif
