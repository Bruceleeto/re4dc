#ifndef RE4DC_ACTOR_TRANSACTION_DIAG_H
#define RE4DC_ACTOR_TRANSACTION_DIAG_H
#ifndef RE4DC_ACTOR_TRANSACTION_DIAG
#define RE4DC_ACTOR_TRANSACTION_DIAG 0
#endif
class cModel;
#if defined(RE4DC_MCHECK_LEONGC) && RE4DC_MCHECK_LEONGC
// mcheck.mk MCHECK_LEONGC (test builds): the last transaction event of the player's model, read when the
// transaction hands Leon to the source (GameCube) path (re4dc_leon_gc_note, trans.cpp).
extern "C" void re4dc_leon_gc_atd(cModel*,unsigned,unsigned,unsigned);
#if RE4DC_ACTOR_TRANSACTION_DIAG
extern "C" void re4dc_actor_txdiag_note(cModel*,unsigned,unsigned,unsigned);
#define ATD(m,e,a,b) (re4dc_leon_gc_atd(m,e,a,b),re4dc_actor_txdiag_note(m,e,a,b))
#else
#define ATD(m,e,a,b) re4dc_leon_gc_atd(m,e,a,b)
#endif
#elif RE4DC_ACTOR_TRANSACTION_DIAG
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
