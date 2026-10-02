# Play and record builds on SteamOS (Steam Deck, Desktop Mode)

Instructions for an agent (or the user) setting up a SteamOS machine to play the port's
builds in Flycast and record gameplay. Everything is user-level: no `sudo`, no changes to the
read-only system image, the user's own Flycast settings untouched. Written 2026-09-29, not yet
run on a Deck: report anything that differs. CachyOS / Arch: `CACHYOS_PLAY.md`.

## What gets installed

| Piece | Where | Why |
|---|---|---|
| Play build | `~/Games/RE4DC/<tag>/<name>-SteamOS/` (`disc/` + `play.sh` + README) | From a public `play-*` prerelease on `lamb2k/re4dc` (asset `*-SteamOS.tar.gz`, sha256 in the release notes) |
| Flycast | Flathub `org.flycast.Flycast` (`--user`) | The emulator. `play.sh` passes the play settings with `-config` (transient) |
| GPU Screen Recorder | Flathub `com.dec05eba.gpu_screen_recorder` (`--user`) | Hardware-encoded 60 fps recording, so Flycast keeps the CPU |
| OBS Studio (optional) | Flathub `com.obsproject.Studio` | Only with `--obs`: commentary, scenes |
| `gh` | `~/.local/bin/gh` if missing | Downloads the release; the script prompts for sign-in if `gh` is not authenticated |
| Steam shortcut | via `steamos-add-to-steam` | So the build also runs from Game Mode (Steam's own Game Recording works there) |

## Steps

1. Get the scripts from the repo. Either a clone (`gh repo clone lamb2k/re4dc`, branch
   `dreamcast-port`) or just the three files in `port/dreamcast/tools/steamos/`.
2. Run `bash port/dreamcast/tools/steamos/setup-play.sh`. Options: `--tag play-...` (default: the
   newest `play-*` release), `--dir DIR` (default `~/Games/RE4DC`), `--obs`, `--no-steam`.
   - `gh auth login` is interactive (browser / device code): the user signs in; an agent must not
     type the user's password or create tokens for them.
   - A sha256 mismatch deletes the download and stops. Do not work around it.
3. Play: run `play.sh` in the extracted build (in a window from the title), or start it from Steam.
4. Record (Desktop Mode): `~/Games/RE4DC/record.sh [out.mp4]`. The first run shows the desktop's
   screen-share picker: pick the Flycast window or the screen; later runs reuse it. Ctrl+C stops and
   saves to `~/Videos/RE4DC/`. In Game Mode use Steam > Settings > Game Recording instead.

## Controls (built-in controller, Flycast defaults, port A)

A action / fire, B run / cancel, Y inventory, R2 aim, L2 knife, left stick move, START pause /
options. Frame pacing: hold R2 (Dreamcast R) and press START to cycle Smooth -> Fast -> Off (the
r21h build defaults to Fast). Remap in Flycast Settings > Controls if needed.

## Checks for the agent

- `flatpak list --user --app` shows `org.flycast.Flycast` and `com.dec05eba.gpu_screen_recorder`.
- `disc/disc.cue` and `disc/disc.bin` exist in the build folder; `disc/elf.sha256` names the ELF.
- A 10 s `record.sh` test produces a playable MP4 (delete it afterwards).
- Do not upload recordings, discs or logs anywhere unless the user asks: the disc holds game data.

## Making a new SteamOS package (on the build machine)

Package layout: `<name>-SteamOS/{play.sh,README.txt,disc/{disc.bin,disc.cue,elf.sha256}}`, `play.sh`
from `tools/steamos/play.sh` (mode 755), archived with `tar -czf` (keeps the exec bit). Upload with
`gh release create play-<build>-<date> ... -R lamb2k/re4dc --target <build commit> --prerelease`, and put
each asset's sha256 in the notes on the line naming the asset (setup-play.sh verifies it from there).
