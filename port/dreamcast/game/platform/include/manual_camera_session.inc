// ss_file.cpp only, after the four fixed, control-aligned camera text arrays.
// Called by the existing page setup and MessageDisplay::move; no new task/poll.
static const u16* file_prompt_owned;
enum { FILE_CAMERA_WORDS=sizeof(prompt_camera_source)/sizeof(u16),
       FILE_CAMERA_WAIT=FILE_CAMERA_WORDS-2, FILE_CAMERA_INVALID=3 };

static const u16* file_prompt_words(unsigned kind){
    if(kind==RE4DC_PROMPT_DPAD)return prompt_camera_dpad;
    if(kind==RE4DC_PROMPT_SECOND_ANALOG)return prompt_camera_second;
    return prompt_camera_unknown;
}
static bool file_prompt_context(const SsFileWork* fw){
    return fw && pSys && pSys->language==1 && fw->fileNo==1 && fw->msgBase==0 &&
        fw->page==4 && fw->layout==1 && fw->attr==0x80054;
}
// Reject any future array edit introducing a timed wait, choice, jump or command
// argument. WidthCk is used ONLY with this fixed {start,newline,wait,end} grammar.
static bool file_prompt_grammar(const u16* words){
    if(words[0]!=0 || words[45]!=3 || words[FILE_CAMERA_WAIT]!=8 ||
       words[FILE_CAMERA_WAIT+1]!=1)return false;
    for(unsigned i=1;i<FILE_CAMERA_WAIT;++i)
        if(i!=45 && (words[i]<0x80 || words[i]>0x13f))return false;
    return true;
}
static void file_prompt_bind(SsFileWork* fw){
    file_prompt_kind=RE4DC_PROMPT_UNKNOWN;file_prompt_owned=0;
    re4dc_manual_camera_text_choice(FILE_CAMERA_INVALID);
    if(!file_prompt_context(fw))return;
    Message* m=&cMes.mes[0];
    if(!m->m_pMes)return;
    for(unsigned i=0;i<FILE_CAMERA_WORDS;++i)
        if(m->m_pMes[i]!=prompt_camera_source[i])return;
    const unsigned kind=re4dc_manual_camera_live_kind();
    const u16* words=file_prompt_words(kind);
    if(!file_prompt_grammar(words))return;
    file_prompt_owned=words;file_prompt_kind=kind;
    m->m_pMes=const_cast<u16*>(words); // before its original first code00
    re4dc_manual_camera_text_choice(kind);
}
static void file_prompt_refresh(SsFileWork* fw,int closing){
    re4dc_manual_camera_text_choice(FILE_CAMERA_INVALID);
    if(!file_prompt_context(fw) || !file_prompt_owned)return;
    if(closing){
        // Keep a completed close-animation picture when its last published
        // instructions still match this controller. Do not reactivate, rebuild
        // or replace a closing/inactive message. Pending reads have no admitted
        // image, and free/new-session boundaries retire that image separately.
        if(file_prompt_kind==re4dc_manual_camera_live_kind())
            re4dc_manual_camera_text_choice(file_prompt_kind);
        return;
    }
    Message* m=&cMes.mes[0];
    if(!(m->be_flag&1) || m->m_attr!=0x80054)return;
    const unsigned kind=re4dc_manual_camera_live_kind();
    const u16* words=file_prompt_words(kind);
    if(!file_prompt_grammar(words))return;
    const bool at_start=m->m_pMes==file_prompt_owned;
    const bool at_wait=m->m_pMes==file_prompt_owned+FILE_CAMERA_WAIT;
    if(!at_start && !at_wait)return; // no publication from another command/slot
    if(kind!=file_prompt_kind){
        if(at_start){
            m->m_pMes=const_cast<u16*>(words);
        }else{
            if(!m->qbase || !m->qp || m->qp<m->qbase || m->qp>m->qbase+0x100 ||
               !m->m_pFont || !m->m_pFont->pWidth || !(m->m_pFont->be_flag&1) ||
               m->m_selTbl_size || m->m_pRetAddr || (m->flags2&8))return;
            // A stack value-copy borrows the existing 256-entry slot-0 queue.
            // WidthCk only measures this fixed grammar; it emits no glyphs,
            // allocation, sound, event, input or timer operations. All transient
            // width-pass mutations remain in draft. No code00/08/01 is replayed.
            Message draft=*m;
            draft.m_pMes=const_cast<u16*>(words);
            draft.WidthCk();
            draft.m_pos_x=draft.m_pos0_x[0];draft.m_lines=0;
            // <=68 literal words; queue capacity is the real MsgQueue[0][256].
            // No fallible operation/yield after writing starts. The scheduler
            // completes this callback before MessageControl::Move/Trans.
            for(unsigned i=1;i<FILE_CAMERA_WAIT;++i){
                if(words[i]==3){draft.code03();continue;}
                const unsigned code=words[i]-0x80U;
                if(code)draft.QueSet(code,0);
                else draft.m_pos_x+=(s16)((f32)MesData.getSpaceWidth()*draft.m_scale_w);
            }
            // Publish only glyph/layout fields. All live wait/cursor/speed,
            // choice/jump/return, active/finished and stop state is untouched.
            m->qp=draft.qp;m->m_pos_x=draft.m_pos_x;m->m_pos_y=draft.m_pos_y;
            m->m_lines=draft.m_lines;m->m_width_max=draft.m_width_max;
            m->m_number_width=draft.m_number_width;
            for(unsigned i=0;i<16;++i){
                m->m_pos0_x[i]=draft.m_pos0_x[i];m->m_width[i]=draft.m_width[i];
            }
            m->m_pMes=const_cast<u16*>(words+FILE_CAMERA_WAIT);
        }
        file_prompt_owned=words;file_prompt_kind=kind;
    }
    // Text and art consume the same kind in this source tick. Draw declines if
    // a later task changes the source policy before the original OT callback.
    re4dc_manual_camera_text_choice(kind);
}
