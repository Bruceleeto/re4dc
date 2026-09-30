# Play and record builds on CachyOS (or any Arch-based desktop)

Instructions for an agent (or the user) setting up a CachyOS machine to play the port's builds in
Flycast and record gameplay. Everything the scripts do is user-level: no `sudo`; system packages
they may need are printed for the user to install. The user's own Flycast settings stay untouched.
Written 2026-09-30 and tested in a Linux shell with a stand-in Flycast, not yet on a CachyOS
machine: report anything that differs. The SteamOS equivalent is `STEAMOS_PLAY.md`.

## What gets installed

| Piece | Where | Why |
|---|---|---|
| Play build | `~/Games/RE4DC/<tag>/<name>-CachyOS/` (`disc/` + `play.sh` + `record.sh` + README) | From a `play-*` release on the private repo `lamb2k/re4dc` (asset `*-CachyOS.tar.gz`, sha256 in the release notes) |
| Flycast | a native `flycast` (AUR `flycast`, chaotic-aur `flycast-git`) if installed, else Flathub `org.flycast.Flycast` (`--user`) | The emulator. `play.sh` passes the play settings with `-config` (transient) |
| GPU Screen Recorder | native `gpu-screen-recorder` if installed, else Flathub `com.dec05eba.gpu_screen_recorder` (`--user`) | Hardware-encoded 60 fps recording, so Flycast keeps the CPU |
| OBS Studio (optional) | native `obs` or Flathub `com.obsproject.Studio` | Only with `--obs` |
| `gh` | system `gh` (`sudo pacman -S github-cli`) or `~/.local/bin/gh` | Downloads the release from the private repo (`gh auth login` once, as the user) |
| Menu entry | `~/.local/share/applications/re4dc-<tag>.desktop` | Starts the build from the desktop menu |

## Steps

1. Optional, as the user: `paru -S flycast gpu-screen-recorder` (native), or `sudo pacman -S flatpak`
   (then the script installs the Flathub builds for the user). With neither, `setup-play.sh` still
   downloads the build and prints what is missing.
2. Get the scripts: a clone (`gh repo clone lamb2k/re4dc`, branch `dreamcast-port`) or just the files in
   `port/dreamcast/tools/cachyos/`.
3. Run `bash port/dreamcast/tools/cachyos/setup-play.sh`. Options: `--tag play-...` (default: the newest
   `play-*` release), `--dir DIR` (default `~/Games/RE4DC`), `--obs`, `--no-desktop`.
   - `gh auth login` is interactive (browser / device code): the user signs in; an agent must not type
     the user's password or create tokens for them.
   - A sha256 mismatch deletes the download and stops. Do not work around it.
   - Releases before r21k have no CachyOS asset; their `*-SteamOS.tar.gz` also runs here if Flatpak is
     installed (its `play.sh` is Flathub-only).
4. Play: `play.sh` in the extracted build (a window from the title; F11 fullscreen), or the menu entry.
   `RE4DC_FLYCAST=/path/to/flycast ./play.sh` picks a specific Flycast binary.
5. Record: `record.sh [out.mp4]` in the build folder. Wayland: the first run shows the desktop's
   screen-share picker (pick the Flycast window or the screen); X11 records the screen. Ctrl+C stops and
   saves to `~/Videos/RE4DC/`.

## Controls (gamepad on port A, Flycast defaults)

A action / fire, B run / cancel, Y inventory, R2 aim, L2 knife, left stick move, START pause / options.
Frame pacing: hold R2 (Dreamcast R) and press START to cycle Smooth -> Fast -> Off (Fast is the default).
Keyboard and DualSense mappings: Flycast Settings > Controls.

## Checks for the agent

- `command -v flycast` or `flatpak list --user --app | grep org.flycast.Flycast`.
- `disc/disc.cue` and `disc/disc.bin` exist in the build folder; `disc/elf.sha256` names the ELF.
- A 10 s `record.sh` test produces a playable MP4 (delete it afterwards).
- Do not upload recordings, discs or logs anywhere unless the user asks: the disc holds game data and the
  repo is private.

## Making a new CachyOS package (on the build machine)

`port/dreamcast/tools/cachyos/package.sh <disc-dir> RE4DC-<build> <out-dir> "<build description>"` makes
`RE4DC-<build>-CachyOS.tar.gz` (`play.sh`, `record.sh`, README, `disc/`) and prints its size and sha256.
Upload it with the Windows and SteamOS packages: `gh release create play-<build>-<date> ... -R lamb2k/re4dc
--target <commit> --prerelease`, and put each asset's sha256 in the notes on the line naming the asset
(`setup-play.sh` verifies it from there).
