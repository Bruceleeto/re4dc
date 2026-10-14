#!/usr/bin/env python3
"""Real OSAlloc/main_mem/InitOt host regression; target ABI remains a separate gate."""
from pathlib import Path
import contextlib,hashlib,json,os,re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[3]
INC=ROOT/'port/dreamcast/game/platform/include'
FLAGS=['-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all',
       '-fno-omit-frame-pointer','-fno-pie','-no-pie']
WRAPS=['OSCreateHeap','OSDestroyHeap','OSInitAlloc','OSFreeToHeap']
def function(text,marker):
    start=text.index(marker);brace=text.index('{',start)
    return text[start:text.index('\n}',brace)+2]
def generate(out):
    out=Path(out)
    header=(ROOT/'include/main_mem.h').read_text()
    types='\n'.join(function(header,'struct '+name)+';' for name in ('OSHeapCell','OSHeapDescriptor','MemHeap'))
    # OSAlloc always uses a literal32-byte cell header. Only padding changes
    # for host64 pointers; both C SDK and C++ readers share their real layout.
    types=types.replace('u8 pad_C[0x20 - 0x0C];','u8 pad_C[32 - 2*sizeof(void*) - sizeof(s32)];')
    (out/'source_world_actual_memory_types.inc').write_text(types+'\n')
    source=(ROOT/'src/game/main_mem.cpp').read_text()
    markers=['void SystemMemInit()','void memInitHeapTbl()','void MemSuspendHeap(',
             'void MemSignalHeap(','int memGetHeapSattus(','int memCheckHeapActive(',
             'int MemSetCurrentHeap(','u32 MemCheckHeapEnd(','int MemCreateHeap(',
             'int MemDestroyHeap(','int MemReplaceHeap(','void MemClearAllHeap()',
             'void* mem_alloc(','void Mem_free_h(','void Debug_free_h(']
    bodies=function(source,'struct SystemMemMap')+';\n'+ '\n'.join(function(source,m) for m in markers)
    # The struct precedes the bodies but SysMem must exist before SystemMemInit.
    bodies=bodies.replace('};\nvoid SystemMemInit','};\nstatic SystemMemMap SysMem;\nvoid SystemMemInit',1)
    (out/'source_world_actual_memory.inc').write_text(bodies+'\n')
    ots=(ROOT/'src/game/trans_ot.cpp').read_text();othead=(ROOT/'include/trans_ot.h').read_text()
    enum=re.search(r'enum OT_TYPE\s*\{.*?\};',othead,re.S).group(0)
    maximum=re.search(r'^#define OT_MAX .*$',othead,re.M).group(0)
    structures='\n'.join(function(othead,'struct '+name)+';' for name in ('OtData','OtPrim','OtWork'))
    (out/'source_world_actual_ot.inc').write_text(maximum+'\n'+structures+'\n'+enum+'\n')
    maxes=re.search(r'static int Ot_max_tbl\[OT_MAX\] = \{.*?\};',ots,re.S).group(0)
    init=maxes+'\n'+ '\n'.join(function(ots,m) for m in ('static inline void ISet','void InitOt()','void ClearOt()','void clearOtWork('))
    (out/'source_world_actual_init_ot.inc').write_text(init+'\n')
    sdk=(ROOT/'src/lib/OSAlloc.c').read_text()
    sdk='\n'.join(line for line in sdk.splitlines() if not line.startswith('#include'))
    prelude='#include <stdint.h>\n#include <stddef.h>\ntypedef uint32_t u32;typedef int32_t s32;typedef uint8_t u8;\n_Static_assert(sizeof(u32)==4,"source u32 remains32-bit");\n'
    prelude+='#define ASSERTMSGLINE(...) ((void)0)\n#define ASSERTLINE(...) ((void)0)\n#define OFFSET(a,b) ((u32)(a)&((b)-1))\nvoid OSReport(const char*,...);\n'
    (out/'source_world_actual_osalloc.c').write_text(prelude+sdk+'\nunsigned source_test_sdk_descriptor_size(void){return sizeof(HeapDesc); }\nunsigned source_test_sdk_cell_size_offset(void){return offsetof(Cell,size); }\nunsigned source_test_sdk_payload_offset(void){return HEADERSIZE; }\nunsigned long source_test_sdk_state(unsigned slot){switch(slot){case 0:return (unsigned long)HeapArray;case 1:return NumHeaps;case 2:return (unsigned long)ArenaStart;case 3:return (unsigned long)ArenaEnd;default:return __OSCurrHeap;}}\n')
    argv=[os.environ.get('CC','gcc'),'-std=gnu11',*FLAGS,'-w','-c',str(out/'source_world_actual_osalloc.c'),'-o',str(out/'osalloc.o')]
    run=subprocess.run(argv,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/'sdk-compiler-command.json').write_text(json.dumps(argv,indent=2)+'\n')
    (out/'sdk-compiler-output.txt').write_text(run.stdout)
    if run.returncode:print(run.stdout)
    run.check_returncode()
    inputs=[ROOT/'src/lib/OSAlloc.c',ROOT/'src/game/main_mem.cpp',ROOT/'src/game/trans_ot.cpp',
            ROOT/'include/main_mem.h',ROOT/'include/trans_ot.h',Path(__file__),
            Path(__file__).with_name('fixtures')/'source_world_allocator.inc',
            Path(__file__).with_name('fixtures')/'source_world_retained.cpp',
            INC/'source_world_retained.inc',INC/'ps2_source_world.h']
    pins={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (out/'allocator-production-inputs.json').write_text(json.dumps(pins,indent=2)+'\n')
def link_flags(out):return [str(Path(out)/'osalloc.o')]+['-Wl,--wrap='+name for name in WRAPS]
if __name__=='__main__':
    saved=os.environ.get('RE4DC_TEST_ARTIFACT_DIR')
    if saved:Path(saved).mkdir(parents=True,exist_ok=False)
    with contextlib.nullcontext(saved) if saved else tempfile.TemporaryDirectory(prefix='re4-retained-') as path:
        out=Path(path);generate(out);exe=out/'test'
        argv=[os.environ.get('CXX','g++'),'-std=c++17',*FLAGS,'-Wall','-Wextra','-fpermissive',
              '-Wno-misleading-indentation','-I',str(INC),'-I',str(out),
              str(Path(__file__).with_name('fixtures')/'source_world_retained.cpp'),*link_flags(out),'-o',str(exe)]
        (out/'compiler-command.json').write_text(json.dumps(argv,indent=2)+'\n')
        run=subprocess.run(argv,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/'compiler-output.txt').write_text(run.stdout)
        if run.returncode:print(run.stdout)
        run.check_returncode()
        run=subprocess.run([str(exe)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/'run-output.txt').write_text(run.stdout);print(run.stdout,end='');run.check_returncode()
