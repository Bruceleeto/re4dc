// Trace-only effect fields. Use C++ members: GCC places cEsp's vptr before
// EspInfo, whereas the recovered header comments describe a trailing vptr.
// Discrete fields and float bits are separate for the approved last-bit policy.
#pragma once

template<class Hash, class Esp>
bool re4dc_trace_effect(Hash& discrete, Hash& floats, unsigned slot, const Esp& e)
{
    if (!(e.m_Be_flg & 1)) return false;
    discrete.word(slot);
    discrete.add(e.info.Core_flg);
    discrete.add(e.info.Core_kind);
    discrete.add(e.info.owner);
    discrete.add(e.info.Call_no);
#define RE4DC_EP(field) discrete.add(e.field)
    RE4DC_EP(m_Be_flg); RE4DC_EP(m_Id); RE4DC_EP(m_Tex_id); RE4DC_EP(m_Type);
    RE4DC_EP(m_Rno0); RE4DC_EP(m_Rno1); RE4DC_EP(m_Rno2); RE4DC_EP(m_Rno3);
    RE4DC_EP(m_Del_near); RE4DC_EP(m_Del_far); RE4DC_EP(m_Tool_flg);
    RE4DC_EP(m_Guid_pMod); RE4DC_EP(m_Parts_no); RE4DC_EP(m_Release_time); RE4DC_EP(m_Flg);
    RE4DC_EP(m_Col_start_r); RE4DC_EP(m_Col_start_g); RE4DC_EP(m_Col_start_b); RE4DC_EP(m_Col_start_a);
    RE4DC_EP(xA4); RE4DC_EP(xA5); RE4DC_EP(xA6); RE4DC_EP(xA7);
    RE4DC_EP(m_Col_max_cnt); RE4DC_EP(m_Col_start_cnt); RE4DC_EP(m_Pos_start_cnt); RE4DC_EP(m_Size_start_cnt);
    RE4DC_EP(m_Life_max); RE4DC_EP(m_Life_time); RE4DC_EP(m_Ptn_no); RE4DC_EP(m_Anm_rate); RE4DC_EP(m_Anm_cnt);
    RE4DC_EP(m_Shimmer_type); RE4DC_EP(m_Shimmer_pow); RE4DC_EP(m_MaskAnm_cnt);
    RE4DC_EP(m_MaskPtn_no); RE4DC_EP(m_MaskTex_id); RE4DC_EP(m_Blend_type); RE4DC_EP(xF3);
#undef RE4DC_EP
    floats.word(slot);
#define RE4DC_EF(field) floats.add(e.field)
#define RE4DC_EV(field) RE4DC_EF(field.x); RE4DC_EF(field.y); RE4DC_EF(field.z)
    RE4DC_EV(m_Pos); RE4DC_EV(m_Speed); RE4DC_EF(m_D_speed); RE4DC_EV(m_Speed_plus);
    RE4DC_EV(m_Ang); RE4DC_EV(m_Ang_plus);
    RE4DC_EF(m_Size_base_x); RE4DC_EF(m_Size_base_y); RE4DC_EF(m_Size_mul);
    RE4DC_EF(m_Size_plus); RE4DC_EF(m_D_size_plus);
    RE4DC_EF(m_Col_r); RE4DC_EF(m_Col_g); RE4DC_EF(m_Col_b); RE4DC_EF(m_Col_a);
    RE4DC_EF(m_Col_d_r); RE4DC_EF(m_Col_d_g); RE4DC_EF(m_Col_d_b); RE4DC_EF(m_Col_d_a);
    RE4DC_EF(m_Radius);
#undef RE4DC_EV
#undef RE4DC_EF
    // Omit addresses, derived work, and the draw-produced m_Mat.
    return true;
}
