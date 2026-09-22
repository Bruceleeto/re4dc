#!/usr/bin/env python3
"""Actual shared bounded aligned reader, with host filesystem error shims."""
import pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class AlignedStorage(unittest.TestCase):
 def test_real_aligned_reader_bounds_short_reads_and_reuse(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);(d/'kos').mkdir()
   (d/'kos/fs.h').write_text("#pragma once\n#include <sys/types.h>\nusing file_t=int;\n#define FILEHND_INVALID -1\nint fs_open(const char*,int);int fs_close(int);ssize_t fs_total(int);ssize_t fs_read(int,void*,size_t);\n")
   (d/'kos.h').write_text('#include <kos/fs.h>\n#include <fcntl.h>\n#include <cstdint>\nstd::uint64_t timer_us_gettime64();\n')
   (d/'test.cpp').write_text(r'''#include "room_storage.hpp"
#include <cassert>
#include <cstring>
#include <cstdint>
static int mode,calls;static size_t position;
int fs_open(const char*,int){return 1;}int fs_close(int){return 0;}ssize_t fs_total(int){return 65536;}
uint64_t timer_us_gettime64(){return 0;}
ssize_t fs_read(int,void* p,size_t n){++calls;assert(n<=65536);if(mode==1)return 0;if(mode==2)return -1;if(mode==3)return n+32;if(mode==4)return 17;
 size_t take=mode==5&&n>32?32:n;memset(p,0x5a,take);position+=take;return take;}
int main(){alignas(32) unsigned char b[65568];using re4dc::storage::read_aligned_chunk;
 for(int i=0;i<3;++i){calls=0;assert(read_aligned_chunk(1,b,65536));assert(calls==1&&b[65535]==0x5a);}
 calls=0;assert(!read_aligned_chunk(1,b+1,32));assert(!read_aligned_chunk(1,b,0));assert(!read_aligned_chunk(1,b,65568));assert(!read_aligned_chunk(1,b,33));assert(!calls);
 for(mode=1;mode<=4;++mode){assert(!read_aligned_chunk(1,b,64));}mode=5;calls=0;assert(read_aligned_chunk(1,b,128));assert(calls==4);
 mode=0;assert(read_aligned_chunk(1,b,64));}
''')
   subprocess.run(['g++','-std=c++17','-fsanitize=address,undefined','-I'+str(d),'-I'+str(ROOT/'room'),str(d/'test.cpp'),str(ROOT/'room/room_storage.cpp'),'-o',str(d/'test')],check=True)
   subprocess.run([str(d/'test')],check=True)

if __name__=='__main__':unittest.main()
