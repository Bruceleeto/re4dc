"""Packet-boundary regression cases plus fail-closed MCHECK_PT log checks."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
CHECK = ROOT / 'port/dreamcast/tools/d367/mcheck/pt_check.py'
spec = importlib.util.spec_from_file_location('pt_check', CHECK)
pt_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt_check)


@unittest.skipUnless(shutil.which('g++'), 'host compiler required')
class PacketDecoder(unittest.TestCase):
    def test_packet_formats_boundaries_and_invalid_state(self):
        code = r"""
#include "ta_pt_audit.h"
#include <array>
#include <cassert>
#include <cstring>
#include <vector>
using re4dc_pt_audit::Decoder;
using re4dc_pt_audit::Stats;
using Block=std::array<std::uint32_t,8>;
constexpr std::uint32_t Blend=0x94000000;
Block packet(std::uint32_t w0,std::uint32_t w2=Blend) {
    Block q{};q[0]=w0;q[2]=w2;return q;
}
void open(Decoder& d,unsigned list) {
    const std::uint32_t marker=0xf00d0000u|list;d.feed(list,&marker,4);
}
void feed(Decoder& d,unsigned list,const Block& q,std::uintptr_t caller=0) {
    const auto before=q;d.feed(list,q.data(),32,caller);assert(q==before);
}
void clean(const Stats& s,unsigned headers) {
    assert(s.headers==headers && !s.bad && !s.invalid && !s.incomplete && !s.reason);
    assert(!s.w0 && !s.w2 && !s.caller);
}
int main() {
    // The two W4 bit patterns looked like bad PT sprite headers to a blind
    // 32-byte scan. They are arbitrary payload in a sprite's second half.
    const Block tails[]={packet(0xbcaee925,0x4420e53a),packet(0xbc98d000,0x441e5134)};
    for (const auto& tail:tails) {
        Decoder d;open(d,4);feed(d,4,packet(0xa4000008));
        feed(d,4,packet(0xf0000000));feed(d,4,tail);
        feed(d,4,packet(0x84000008));feed(d,4,packet(0xf0000000));
        clean(d.finish_scene(),2);
    }
    // Independent fixed packet-size cases from Flycast's type table: packed,
    // floating, intensity and previous-face intensity, one or two volumes.
    struct Format { unsigned control;bool header64,vertex64; };
    const Format formats[]={
        {0x00,0,0},{0x08,0,0},{0x10,0,0},{0x18,0,1},
        {0x20,0,0},{0x28,0,0},{0x2c,1,0},{0x30,0,0},{0x38,0,0},{0x3c,0,0},
        {0x40,0,0},{0x48,0,1},{0x60,1,0},{0x68,1,1},{0x6c,1,1},{0x70,0,0},{0x78,0,1}
    };
    for (const auto& f:formats) for (unsigned uv16:{0u,1u}) {
        std::vector<Block> data{packet(0x84000000|f.control|uv16)};
        if(f.header64)data.push_back(tails[0]);
        data.push_back(packet(0xf0000000));
        if(f.vertex64)data.push_back(tails[1]);
        data.push_back(packet(0x84000000));
        // Same bytes supplied as one stream call or separate 32-byte calls.
        const auto before=data;Decoder whole,split;open(whole,4);open(split,4);
        whole.feed(4,data.data(),unsigned(data.size()*sizeof(Block)));
        for(const auto& q:data)feed(split,4,q);
        clean(whole.finish_scene(),2);clean(split.finish_scene(),2);assert(data==before);
    }
    // OP/TR sprites and both modifier lists also have 64-byte vertices.
    // Their header-looking tails must not add phantom PT coverage.
    {
        Decoder d;
        for(unsigned list:{0u,1u,2u,3u}) {
            open(d,list);const unsigned type=(list==1||list==3)?4:5;
            feed(d,list,packet((type<<29)|(list<<24)|8));
            feed(d,list,packet(0xf0000000));feed(d,list,tails[list&1]);
        }
        open(d,4);feed(d,4,packet(0x84000000));clean(d.finish_scene(),1);
    }
    // Real bad headers remain failures, with the first true caller/words.
    {
        Decoder d;open(d,4);feed(d,4,packet(0x84000008,0x20000000),0x1234);
        feed(d,4,packet(0xa4000008,0),0x5678);const auto s=d.finish_scene();
        assert(s.headers==2 && s.bad==2 && !s.invalid && !s.incomplete);
        assert(s.w0==0x84000008 && s.w2==0x20000000 && s.caller==0x1234);
        open(d,4);feed(d,4,packet(0x84000000));clean(d.finish_scene(),1);
    }
    // Truncated 64-byte headers and vertices cannot produce a clean scene.
    for(bool header_tail:{false,true}) {
        Decoder d;open(d,4);feed(d,4,packet(header_tail?0x8400002c:0xa4000008));
        if(!header_tail)feed(d,4,packet(0xf0000000));
        const auto s=d.finish_scene();assert(s.incomplete==1 && s.reason && !s.bad);
        // Scene reset must clear the old half, or the next header is lost.
        open(d,4);feed(d,4,packet(0x84000000));clean(d.finish_scene(),1);
    }
    // KOS list closure is a boundary: PT's first header cannot fill OP's tail.
    {
        Decoder d;open(d,0);feed(d,0,packet(0xa0000008));feed(d,0,packet(0xf0000000));
        open(d,4);feed(d,4,packet(0x84000000));const auto s=d.finish_scene();
        assert(s.headers==1 && s.incomplete==1 && !s.bad);
    }
    // 32-byte controls do not consume or reset the current vertex format.
    {
        Decoder d;open(d,4);feed(d,4,packet(0x84000018));
        feed(d,4,packet(0x20000000));feed(d,4,packet(0x40000000));
        feed(d,4,packet(0xf0000000));feed(d,4,tails[0]);clean(d.finish_scene(),1);
    }
    // Malformed/framing cases must stay failed even if good PT data follows.
    for(unsigned mode=0;mode<11;++mode) {
        Decoder d;open(d,4);auto q=packet(0x84000000);
        switch(mode) {
        case 0:d.feed(4,q.data(),31);break;
        case 1:d.feed(4,nullptr,32);break;
        case 2:d.feed(5,q.data(),32);break;
        case 3:d.feed(4,q.data(),4);break; // only exact hash marker may be short
        case 4:feed(d,4,packet(0x60000000));break;
        case 5:feed(d,4,packet(0xc0000000));break;
        case 6:feed(d,4,packet(0xf0000000));break; // orphan
        case 7:feed(d,4,packet(0x84000058));break; // invalid two-volume float
        case 8:feed(d,4,packet(0x82000000));break; // header/active list mismatch
        case 9:open(d,4);break;                 // repeated physical list
        case 10:feed(d,2,packet(0x82000000));break; // missing switch marker
        }
        feed(d,4,q);assert(d.finish_scene().invalid>0);
    }
    {
        Decoder d;open(d,1);feed(d,1,packet(0xa1000000));assert(d.finish_scene().invalid);
        open(d,4);feed(d,4,packet(0x84000000));feed(d,4,packet(0));
        feed(d,4,packet(0xf0000000));assert(d.finish_scene().invalid);
    }
    // Observer must also tolerate unaligned byte storage without modifying it.
    {
        std::array<unsigned char,33> bytes{};const auto q=packet(0x84000000);
        std::memcpy(bytes.data()+1,q.data(),32);const auto before=bytes;
        Decoder d;open(d,4);d.feed(4,bytes.data()+1,32);clean(d.finish_scene(),1);assert(bytes==before);
    }
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'test.cpp').write_text(code)
            result = subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                                     '-fsanitize=address,undefined', '-I' + str(ROOT / 'port/dreamcast/game/platform/include'),
                                     str(tmp / 'test.cpp'), '-o', str(tmp / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(tmp / 'test')], check=True)


class LogChecker(unittest.TestCase):
    @staticmethod
    def row(**fields):
        d = dict(frame=30, present=1, headers=10, bad=0, invalid=0, incomplete=0, why=0,
                 w0='00000000', w2='00000000', ra='0x0')
        d.update(fields)
        return ('pt_audit: v=2 frame={frame} present={present} pt_hdr={headers} bad={bad} '
                'invalid={invalid} incomplete={incomplete} why={why} w0={w0} w2={w2} ra={ra}\n').format(**d)

    def check(self, text, expected, *args):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'log.txt'
            path.write_bytes(text.encode('ascii'))
            output = io.StringIO()
            with redirect_stdout(output):
                result = pt_check.main([str(path), *args])
            self.assertEqual(result, expected, output.getvalue())
            return output.getvalue()

    def test_clean_v2_per_room_coverage(self):
        self.check('warp: room enter 100\n' + self.row() + 'room lifecycle: phase=enter room=101\n' + self.row(),
                   0, '--rooms', '100,101', '--min-headers', '10')

    def test_real_bad_header(self):
        self.check(self.row(bad=1, w0='84000008', w2='20000000', ra='0x1234'), 1)

    def test_invalid_scene_with_no_pt_headers(self):
        self.check(self.row() + self.row(headers=0, invalid=1, why=5), 1)

    def test_truncated_packet_state(self):
        self.check(self.row(incomplete=1, why=8), 1)

    def test_legacy_bad_rows_stay_failed(self):
        self.check('pt_audit: frame=965 present=1 pt_hdr=77 bad=1 w0=bcaee925 w2=4420e53a ra=8c056cf8\n', 1)

    def test_legacy_clean_is_not_packet_coverage(self):
        self.check('pt_audit: frame=30 present=1 pt_hdr=77 bad=0 w0=00000000 w2=00000000 ra=0x0\n', 2)

    def test_mixed_schemas_are_rejected(self):
        self.check(self.row() + 'pt_audit: frame=30 present=1 pt_hdr=77 bad=0 w0=00000000 w2=00000000 ra=0x0\n', 1)

    def test_unknown_schema_is_rejected(self):
        self.check(self.row().replace('v=2', 'v=3'), 1)

    def test_malformed_record_cannot_hide_after_good_coverage(self):
        self.check(self.row() + self.row().replace('invalid=0 ', ''), 1)

    def test_truncated_final_record_is_rejected(self):
        self.check(self.row() + self.row().rstrip('\n'), 1)

    def test_interleaved_log_line_is_not_silently_skipped(self):
        self.check(self.row() + self.row().replace('frame=30', 'frame=aica: noise30'), 1)

    def test_inconsistent_counts_are_rejected(self):
        self.check(self.row(headers=1, bad=2), 1)
        self.check(self.row(invalid=1, why=0), 1)
        self.check(self.row(why=5), 1)

    def test_missing_required_room_and_empty_coverage(self):
        self.check('room enter 100\n' + self.row(), 1, '--rooms', '100,101')
        self.check(self.row(headers=0), 1)
        self.check('', 2)


if __name__ == '__main__':
    unittest.main()
