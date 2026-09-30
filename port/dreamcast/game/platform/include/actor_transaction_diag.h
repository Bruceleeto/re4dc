#ifndef RE4DC_ACTOR_TRANSACTION_DIAG_H
#define RE4DC_ACTOR_TRANSACTION_DIAG_H
#ifndef RE4DC_ACTOR_TRANSACTION_DIAG
#define RE4DC_ACTOR_TRANSACTION_DIAG 0
#endif
class cModel;
#if RE4DC_ACTOR_TRANSACTION_DIAG
extern "C" void re4dc_actor_txdiag_note(cModel*,unsigned,unsigned,unsigned);
#define ATD(m,e,a,b) re4dc_actor_txdiag_note(m,e,a,b)
#elif defined(RE4DC_ENC_CENSUS) && RE4DC_ENC_CENSUS
// ENC_CENSUS (diagnostic, default 0): the last transaction event code, read by the census after each draw.
extern "C" unsigned re4dc_enc_atd;
#define ATD(m,e,a,b) ((void)(re4dc_enc_atd=(e)))
#else
#define ATD(m,e,a,b) ((void)0)
#endif
#endif
