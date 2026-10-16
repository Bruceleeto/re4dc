# Third-party notices

The project's own tools and documents are [CC0](LICENSE). The Dreamcast program also contains code from these
projects, each under its own licence. Their licence texts stay with the code, unchanged.

| Project | What the port uses | Licence | Where in this repository |
| --- | --- | --- | --- |
| [KallistiOS](https://github.com/KallistiOS/KallistiOS) (commit 804b3195, plus the port's patches) | the Dreamcast system library the program is linked with | KOS licence (new BSD style) | `port/dreamcast/patches/LICENSE.KOS`, `port/dreamcast/toolchain.lock` |
| [pl_mpeg](https://github.com/phoboslab/pl_mpeg) (commit c871f2be) | MPEG-1 video decoding for the cutscene movies | MIT | licence at the top of `port/dreamcast/game/third_party/pl_mpeg.h`; pin in `PL_MPEG_PIN.md` beside it |
| [SH4ZAM](https://github.com/gyrovorbis/sh4zam) (v0.9.0, commit 0fd3a1e1) by Falco Girgis and SH4ZAM contributors; thanks to Bruceleeto for the first measurements | SH-4 matrix and trigonometry routines used by the renderer (GAME_SH4ZAM_RENDER_ONLY) | MIT | `port/dreamcast/game/third_party/sh4zam/LICENSE` |
