#!/usr/bin/env python3
"""Actual source-reader/native-prep control-flow tests; fake platform/cache only.

This does not establish VRAM fit, PVR fences or renderer/runtime acceptance.
The SH compilation and knob-off comparison remain separate target checks.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
INCLUDE = ROOT / "port/dreamcast/game/platform/include"


def function(text, signature):
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


class ActualFxCorePrep(unittest.TestCase):
    def test_actual_source_and_native_code(self):
        with tempfile.TemporaryDirectory(prefix="fx-core-prep-") as directory:
            tmp = Path(directory)
            extracted = [function((ROOT / "src/game/esp_sub.cpp").read_text(),
                                  "static int EspSpriteEligible(cEsp* esp)")]
            for unit in ["esp0a", "esp0e"]:
                text = (ROOT / f"src/game/{unit}.cpp").read_text()
                start = text.index("// FX_CORE_SOURCE_READER_BEGIN")
                end = text.index("// FX_CORE_SOURCE_READER_END", start)
                extracted.append(text[start:end])
            (tmp / "actual_source_helpers.inc").write_text("\n".join(extracted))
            executable = tmp / "fixture"
            subprocess.run(["c++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=undefined", "-fno-sanitize-recover=all",
                            "-I", str(INCLUDE), "-I", str(tmp),
                            str(Path(__file__).parent / "fixtures/fx_core_source_prep.cpp"),
                            "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    unittest.main()
