#!/usr/bin/env python3
"""Actual source query, core-identity table and native preparation helper.

Synthetic source descriptors and cache/load boundary; verifies identity, phase,
reserves, frame pinning and retry without changing source state. Does not prove
GPU allocation, upload, packets, pixels, timing or original RNG equivalence.
"""
from pathlib import Path
import os
import subprocess
import tempfile
from test_ps2_fx_common_phase import function
from test_ps2_fx_stage1_phase import harness as phase_harness
ROOT=Path(__file__).resolve().parents[1]


def harness():
    native=(ROOT/'port/dreamcast/game/platform/native_ui.cpp').read_text()
    begin=function(native, 'extern "C" void re4dc_ui_begin()')
    assert begin.count('stage1_prepare_image();') == 1
    assert begin.index('re4dc_prepare_model_assets();') < begin.index('stage1_prepare_image();') < begin.index('re4dc::profile::begin();')
    skip=function(native, 'extern "C" void re4dc_ui_begin_skip()')
    assert 'stage1_prepare_image' not in skip
    assert native.count('stage1_prepare_image();') == 1
    body=phase_harness().split('int main(){')[0]
    body=body.replace('extern "C" void re4dc_ui_begin(){phase_ready=true;phase_finished=false;phase_begin=++phase_step;}',
        'static void test_native_begin();static void test_native_skip();\nextern "C" void re4dc_ui_begin(){test_native_begin();}')
    body=body.replace('static void re4dc_ui_begin_skip(){phase_ready=false;phase_finished=false;phase_begin=++phase_step;}',
        'static void re4dc_ui_begin_skip(){test_native_skip();}')
    cpp=(ROOT/'port/dreamcast/room/texture_package.cpp').read_text()
    hpp=(ROOT/'port/dreamcast/room/texture_package.hpp').read_text()
    body+='\n#include <algorithm>\n#include <cstddef>\n'
    body+=hpp[hpp.index('class SourceIdentityTable {'):hpp.index('class Package {')]
    for marker in ('std::uint32_t crc_update(', 'std::uint32_t crc32(', 'unsigned word(', 'unsigned half(',
                   'bool SourceIdentityTable::adopt(', 'int SourceIdentityTable::lookup('):
        body+=function(cpp,marker)+'\n'
    body+=(ROOT/'tools/test_ps2_fx_stage1_prepare_fixture.inc').read_text().replace('"../port/', '"'+str(ROOT/'port')+'/')
    return body


def main():
    with tempfile.TemporaryDirectory(prefix='ps2-fx-stage1-prepare-') as tmp:
        source=Path(tmp)/'prepare.cpp';source.write_text(harness())
        for keep in (0,1):
            binary=Path(tmp)/f'prepare-keep{keep}'
            subprocess.run([os.environ.get('CXX','g++'),'-std=c++11','-O1','-g','-Wall','-Wextra','-Werror','-pedantic',
                '-Wno-narrowing','-Wno-unused-function','-Wno-unused-variable','-ffp-contract=off',
                '-fsanitize=address,undefined','-fno-omit-frame-pointer',f'-DRE4DC_TEX_KEEP={keep}',str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
    print('PASS actual native begin hook follows model preparation and precedes profile/draw; absent from skip begin')
if __name__=='__main__':main()
