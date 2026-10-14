#!/usr/bin/env python3
"""Compile actual source-world readers with adversarial synthetic services."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[3]
INC=ROOT/'port/dreamcast/game/platform/include'
if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='re4-source-world-') as out:
        exe=Path(out)/'test'
        # This regression previously used invented3/5 table aliases, masking
        # a real integration bug. Compile the actual enum and require source
        # registration/Render scope agreement at the source boundary.
        header=(ROOT/'include/trans_ot.h').read_text()
        enum=re.search(r'enum OT_TYPE\s*\{.*?\};',header,re.S).group(0)
        maximum=re.search(r'^#define OT_MAX .*$',header,re.M).group(0)
        (Path(out)/'source_world_actual_ot.inc').write_text(maximum+'\n'+enum+'\n')
        backing=(ROOT/'port/dreamcast/game/parts_bridge.cpp').read_text()
        def function(text, marker):
            start=text.index(marker);brace=text.index('{',start);depth=1;end=brace+1
            while depth:
                depth+=(text[end]=='{')-(text[end]=='}');end+=1
            return text[start:end]
        pool_structs=backing[backing.index('template<class T> struct alignas(32) Chunk'):backing.index('static_assert(sizeof(Chunk')]
        (Path(out)/'source_world_actual_pools.inc').write_text(pool_structs+'\n'+
            function(backing,'template<class T> bool sparse')+'\n'+
            function(backing,'template<class T> Pool<T>* pool')+'\n'+
            function(backing,'template<class T> T* work_at')+'\n')
        trans=(ROOT/'src/game/trans.cpp').read_text()
        ots=(ROOT/'src/game/trans_ot.cpp').read_text()
        assert 'AddOtDirect(0xB, m, (void (*)()) ModelRender' in trans
        assert 'OtWork* w = otWork(13);' in ots and 'OtWork* w = otWork(17);' in ots
        for name in ['OT_TYPE_EFFECT_VU1','OT_TYPE_COCKPIT','OT_TYPE_DEBUG']:
            assert '{ SourceWorldRenderScope sourceWorldScope; ExecOt('+name+'); }' in trans
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O1','-g','-Wall','-Wextra',
            '-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',
            '-Wno-misleading-indentation','-I',str(INC),'-I',str(out),
            str(Path(__file__).with_name('fixtures')/'source_world_r200.cpp'),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
