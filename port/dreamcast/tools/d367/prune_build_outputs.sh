#!/bin/bash
# prune_build_outputs.sh [--apply] [--idle-hours H] [--no-windows | --windows-only] [--top NAME]... [--list] [--quiet]
# (WSL) Disk hygiene rule (user, 2026-10-15; CLAUDE.md): delete REBUILDABLE build outputs only -- objects/deps/ELFs
# in build objdirs (out-*, obj*, build*), staged disc images and intermediate zips -- in /root/probe units idle
# for more than 6 h, and disc images older than 6 h in the evidence roots C:/D:\Flycast-Evidence\re4-dreamcast.
# Default is a dry run (prints what would go, per top-level dir, plus the largest protected units).
# --apply deletes and writes /root/probe/_prune-manifests/<timestamp>.tsv (path, bytes, mtime, nlink, reason).
# Keeps: source, .git, logs/traces/captures/results (only the extensions above are ever deleted), the active lanes,
# release / candidate / benchmark / SD folders, hwmodel-bin and data/ dirs, flycast.exe, and every disc or objdir
# referenced by the testing skills, tools/d367, the warp/harness scripts or recent workspace docs (BASE disc trap).
# Worktrees with uncommitted or unpushed work are backed up (diff, stash list, bundle) to
# /root/probe/_prune-manifests/backups/ before any of their objdirs is pruned; their source is never touched.
# Pin anything else: a path prefix or a token per line in /root/probe/_prune-manifests/keep.txt, or PRUNE_PROTECT.
# Note: deleting inside WSL frees ext4 space (the vhdx stops growing); C: itself only grows back after the
# user's admin Compact-WSL.ps1. Evidence-root discs free C:/D: directly. Never run wsl --shutdown from here.
# Automatic use: prune_if_low.sh (staging calls it when C: or D: is below 40 GB).
here=$(cd "$(dirname "$0")" && pwd)
M=/root/probe/_prune-manifests
mkdir -p $M
# One --apply per side at a time (the WSL and evidence-root passes touch disjoint files).
locks="wsl win"
for x in "$@"; do
  [ "$x" = --windows-only ] && locks=win
  [ "$x" = --no-windows ] && locks=wsl
done
for x in "$@"; do
  if [ "$x" = --apply ]; then
    exec 8>$M/.prune-wsl.lock 9>$M/.prune-win.lock
    for l in $locks; do
      fd=8; [ $l = win ] && fd=9
      flock -n $fd || { echo "prune_build_outputs: another --apply ($l) is running ($M/.prune-$l.lock); skipping"; exit 0; }
    done
  fi
done
nice -n 10 ionice -c3 python3 "$here/prune_build_outputs.py" "$@"
