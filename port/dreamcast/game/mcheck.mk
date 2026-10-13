# D367 machine checks (test 9; test builds only, default 0: nothing compiled, identical image). Each knob adds one
# log line that a host script turns into PASS / FAIL (tools/d367/mcheck/):
# MCHECK_PT=1 (needs TA_HASH >= 1, whose hooks see every TA burst): "pt_audit:" per scene: punch-through polygon /
#   sprite headers (PCW list type 4) and those whose blend is not SRCALPHA / INVSRCALPHA (ONE / ZERO draws the
#   cut-out texels as solid on PVR hardware: the test 8 branch-tip cards; PT_BLEND_FIX). pt_check.py.
# MCHECK_SAFE=1 (needs RENDER_OPTION=1): "safe_area:" the speed display's screen rectangle, the render size and the
#   tile rows LETTERBOX_CLIP cleared in that scene (issue #26: tile row 0 lost the counter on consoles; Flycast
#   draws it anyway). safe_check.py.
MCHECK_PT ?= 0
MCHECK_SAFE ?= 0
ifeq ($(MCHECK_PT),1)
ifeq ($(TA_HASH),0)
$(error MCHECK_PT=1 needs TA_HASH=1, 2 or 3)
endif
$(OBJDIR)/platform/native_ui.o: PLATFORM_CPPFLAGS += -DRE4DC_MCHECK_PT=1
endif
ifeq ($(MCHECK_SAFE),1)
ifneq ($(RENDER_OPTION),1)
$(error MCHECK_SAFE=1 needs RENDER_OPTION=1 (the speed display))
endif
$(OBJDIR)/platform/native_ui.o $(OBJDIR)/platform/letterbox_clip.o: PLATFORM_CPPFLAGS += -DRE4DC_MCHECK_SAFE=1
endif
