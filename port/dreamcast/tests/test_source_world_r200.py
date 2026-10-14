#!/usr/bin/env python3
"""Compile actual source-world readers with adversarial synthetic services."""
from pathlib import Path
import os
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[3]
INC=ROOT/'port/dreamcast/game/platform/include'
if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='re4-source-world-') as out:
        exe=Path(out)/'test'
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O2','-Wall','-Wextra',
            '-Wno-misleading-indentation','-I',str(INC),
            str(Path(__file__).with_name('fixtures')/'source_world_r200.cpp'),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
