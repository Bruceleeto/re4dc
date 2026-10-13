#!/usr/bin/env python3
"""Compile and run the portable renderer and actual LCD owner against a fake Maple boundary."""
import os,shlex,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[2];game=root/'game';test=root/'tests/vmu'
compiler=shlex.split(os.environ.get('CXX','g++'))
with tempfile.TemporaryDirectory(prefix='re4-vmu-tests-') as folder:
 out=Path(folder)
 # The packed Leon growth frames (tools/pack_vmu_leon.py) must match re4_vmu_leon.h.
 packed=out/'leon_packed.inc'
 subprocess.run(['python3',str(root/'tools/pack_vmu_leon.py'),str(game/'vmu_assets/re4_vmu_leon.h'),str(packed)],check=True,stdout=subprocess.DEVNULL)
 assert packed.read_bytes()==(game/'vmu_assets/re4_vmu_leon_packed.inc').read_bytes(),'re4_vmu_leon_packed.inc is stale'
 common=compiler+['-std=c++11','-Wall','-Wextra','-Werror','-I'+str(game)]
 for name,extra in [('render_cli',[]),('queue_test',[]),('platform_test',[str(game/'platform/vmu_lcd.cpp'),'-I'+str(test/'stubs')])]:
  binary=out/name
  subprocess.run(common+[str(game/'vmu_render.cpp'),str(test/(name+'.cpp'))]+extra+['-o',str(binary)],check=True)
  if name=='render_cli':subprocess.run(['python3',str(test/'test_render.py'),str(binary)],check=True)
  else:subprocess.run([str(binary)],check=True)
