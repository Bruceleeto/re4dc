// game/esp47.cpp: effect id 0x47, a screen-space sprite that wraps around the screen: its
// position is kept inside the 480 x 448 screen (with a 32 pixel left margin) and, when the
// sprite overlaps an edge, it is drawn a second (and for corners a third) time shifted by 448
// so the wrap is seamless. Used for full-screen scrolling overlays (rain, dust).

#include "atari.h"
#include "light.h"
#include "esp.h"

#define SCR_W 480.0f
#define SCR_H 448.0f
#define SCR_L 32.0f

#if defined(RE4DC_ESP47_SKIP_LEAN) && RE4DC_ESP47_SKIP_LEAN
// ESP47_SKIP_LEAN (effects30.mk): on an iteration that draws nothing (pace.cpp re4dc_pace_skipping) the
// logic-only effect pass still queues this trans for its m_Pos screen wrap; the wrap and the shifted m_Pos
// round trips below run as before, only the sprite draws (EspCommonTrans, which writes no m_Pos) are left out.
extern "C" int re4dc_pace_skipping;
#define ESP47_DRAW(e) do { if (!re4dc_pace_skipping) { EspCommonTrans(e); } } while (0)
#else
#define ESP47_DRAW(e) EspCommonTrans(e)
#endif

// Screen-space sprite that wraps around the screen edges (drawn again on the opposite side).
class cEsp47 : public cEsp {
public:
    u32 xF8;

    virtual void move();
    virtual int SetFreeWork(EspGenWork* gen, u32* seed);
};

// EspCreateTbl[0x47] factory.
cEsp* Esp47_Create()
{
    return new cEsp47;
}

// Standard sprite update; released when the animation ends.
void cEsp47::move()
{
    if (CommonMove()) {
        if (!AnmMove()) {
            PushEsp(this);
        }
    }
}

// EspTransTbl[0x47]: wraps m_Pos into the screen, computes the sprite's pixel extent from the
// animation's Cx/Cy pivot, draws it with EspCommonTrans and repeats the draw shifted by 448 on
// every edge (and corner) it overlaps.
void Esp47_Trans(cEsp* pEsp)
{
    EspAnmData* anm;
    f32 sx = pEsp->m_Size_base_x * pEsp->m_Size_mul;
    f32 sy = pEsp->m_Size_base_y * pEsp->m_Size_mul;
    f32 rx;
    f32 ry;
    f32 w;
    f32 h;
    int flag;

    if (!EspGetAnmAddr(pEsp->m_Tex_id, &anm)) {
        pLog->err(0, 0, "ESP : TexId[%x] no data", pEsp->m_Tex_id);
        return;
    }
    if ((f32)anm->Cx == 0.0f) {
        rx = -0.5f;
    } else {
        rx = (f32)(-anm->Cx) / anm->Width;
    }
    if ((f32)anm->Cy == 0.0f) {
        ry = -0.5f;
    } else {
        ry = (f32)anm->Cy / anm->Height + -1.0f;
    }
    w = rx * sx;
    h = ry * sy;

    while (pEsp->m_Pos.x > SCR_W) {
        pEsp->m_Pos.x -= SCR_H;
    }
    while (pEsp->m_Pos.x < SCR_L) {
        pEsp->m_Pos.x += SCR_H;
    }
    while (pEsp->m_Pos.y > SCR_H) {
        pEsp->m_Pos.y -= SCR_H;
    }
    while (pEsp->m_Pos.y < 0.0f) {
        pEsp->m_Pos.y += SCR_H;
    }

    flag = 0;
    ESP47_DRAW(pEsp);
    if (pEsp->m_Pos.x + w < SCR_L) {
        flag = 1;
        pEsp->m_Pos.x += SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.x -= SCR_H;
    }
    if (pEsp->m_Pos.x - w > SCR_W) {
        flag |= 2;
        pEsp->m_Pos.x -= SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.x += SCR_H;
    }
    if (pEsp->m_Pos.y + h < 0.0f) {
        flag |= 4;
        pEsp->m_Pos.y += SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.y -= SCR_H;
    }
    if (pEsp->m_Pos.y - h > SCR_H) {
        flag |= 8;
        pEsp->m_Pos.y -= SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.y += SCR_H;
    }
    if (flag == 5) {
        pEsp->m_Pos.x += SCR_H;
        pEsp->m_Pos.y += SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.x -= SCR_H;
        pEsp->m_Pos.y -= SCR_H;
    }
    if (flag == 9) {
        pEsp->m_Pos.x += SCR_H;
        pEsp->m_Pos.y -= SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.x -= SCR_H;
        pEsp->m_Pos.y += SCR_H;
    }
    if (flag == 6) {
        pEsp->m_Pos.x -= SCR_H;
        pEsp->m_Pos.y += SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.x += SCR_H;
        pEsp->m_Pos.y -= SCR_H;
    }
    if (flag == 10) {
        pEsp->m_Pos.x -= SCR_H;
        pEsp->m_Pos.y -= SCR_H;
        ESP47_DRAW(pEsp);
        pEsp->m_Pos.x += SCR_H;
        pEsp->m_Pos.y += SCR_H;
    }
}

// No extra parameters.
int cEsp47::SetFreeWork(EspGenWork* gen, u32* seed)
{
    return 1;
}
