"""tools/d367/warp.py: presets expand to the warp.txt lines dbgwarp_bridge.cpp parses."""
import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).resolve().parents[1] / "tools" / "d367" / "warp.py"
spec = importlib.util.spec_from_file_location("warp", TOOL)
warp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(warp)

KEYS = {"name", "room", "jp", "pos", "dir", "ang", "rsf", "scenario", "find", "unlock", "inv", "area", "act", "trg",
        "dead", "kill", "goto", "dump", "late", "items"}


class WarpPresets(unittest.TestCase):
    def test_every_line_is_a_known_key(self):
        for name, p in warp.PRESETS.items():
            if p.get("pos", 0) is None:
                continue
            for line in warp.lines_for(p, door=True, dump=True, name=name).splitlines():
                if line.startswith("#"):
                    continue
                self.assertIn(line.split()[0], KEYS, (name, line))

    def test_late_line_fixed_width(self):
        a = warp.lines_for(dict(warp.PRESETS["r100-s20"], late=(0x00,)), name="r100-s20")
        b = warp.lines_for(dict(warp.PRESETS["r100-s20"], late=(0x04, 1400, 0x100)), name="r100-s20")
        self.assertIn("late 0x00 1400 0x100", a.splitlines())
        self.assertIn("late 0x04 1400 0x100", b.splitlines())
        self.assertEqual(len(a), len(b))

    def test_s20_presets_kill_and_goto(self):
        lines = warp.lines_for(warp.PRESETS["r100-s20"], name="r100-s20").splitlines()
        self.assertIn("act 30 fwd 150", lines)       # the preset's own door act, always on
        self.assertIn("kill 0x12 400 0x100", lines)
        route = warp.lines_for(warp.PRESETS["r100-s20-route"], name="r100-s20-route").splitlines()
        self.assertIn("kill 0x12 700 0x100", route)
        self.assertEqual([l for l in route if l.startswith("goto ")],
                         ["goto 400 -86558 0 -1243", "goto 460 -83382 1100 -34851"])
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            warp.main(["r100-house-door", "--kill", "0x12:500:0x100"])
        self.assertIn("kill 0x12 500 0x100", out.getvalue().splitlines())

    def test_east_door_actions_and_after_state_variant(self):
        text = warp.lines_for(warp.PRESETS["r100-east-door"], door=True)
        self.assertIn("room 0x100", text)
        self.assertIn("act 60 a 4", text)
        after = warp.lines_for(warp.PRESETS["r100-east-door-after"])
        rsf = [l for l in after.splitlines() if l.startswith("rsf 0x100")][0].split()[2:]
        for bit in ("3", "4", "10", "13"):
            self.assertIn(bit, rsf)

    def test_house_door_keeps_s03_armed(self):
        text = warp.lines_for(warp.PRESETS["r100-house-door"])
        rsf = [l for l in text.splitlines() if l.startswith("rsf 0x100")][0].split()[2:]
        self.assertNotIn("3", rsf)
        self.assertNotIn("10", rsf)
        self.assertIn("13", rsf)

    def test_explicit(self):
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            warp.main(["--room", "0x101", "--pos", "1", "2", "3", "--rsf", "0x101:6,7", "--act", "a:10:4"])
        text = out.getvalue()
        self.assertIn("room 0x101", text)
        self.assertIn("rsf 0x101 6 7", text)
        self.assertIn("act 10 a 4", text)

    def test_bell_trigger(self):
        text = warp.lines_for(warp.PRESETS["r101-bell"], name="r101-bell")
        self.assertIn("trg 0 1200 0x101", text.splitlines())
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            warp.main(["r101-bell-fight", "--trg", "0:600"])
        self.assertIn("trg 0 600", out.getvalue().splitlines())


if __name__ == "__main__":
    unittest.main()
