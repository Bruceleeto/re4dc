#!/bin/bash
# clean.sh [--trim]  (WSL; lane stage-ext4, 2026-10-14): housekeeping for stage_ext4/stage_scenario.py.
#   - removes ext4 stage dirs ($RE4DC_STAGE_ROOT/scen/*) older than STAGE_MAX_MIN minutes (default 120): leftovers of
#     a killed staging or of RE4DC_STAGE_KEEP=1;
#   - prunes cache keys not used for CAS_MAX_DAYS days (default 7) and every object no key points at;
#   - --trim runs fstrim on / . The distro's / is mounted with `discard` and its ext4.vhdx is sparse, so deleted
#     blocks normally go back to C: on their own; fstrim is the catch-up when C: free looks too low after cleanup.
set -euo pipefail
R=${RE4DC_STAGE_ROOT:-/root/stage}
[ -d "$R" ] || { echo "no $R"; exit 0; }
n=0
for d in "$R"/scen/*/; do
  [ -d "$d" ] || continue
  if [ -n "$(find "$d" -maxdepth 0 -mmin +${STAGE_MAX_MIN:-120})" ]; then rm -rf "$d"; n=$((n+1)); fi
done
echo "stage dirs removed: $n"
if [ -d "$R/cas/keys" ]; then
  find "$R/cas/keys" -type f -mtime +${CAS_MAX_DAYS:-7} -delete
  find "$R/cas/tmp" -type f -mmin +120 -delete 2>/dev/null || true
  live=$(mktemp); cat "$R"/cas/keys/*/* 2>/dev/null | sort -u > "$live"
  k=0
  for o in "$R"/cas/obj/*/*; do
    [ -f "$o" ] || continue
    b=$(basename "$o")   # <sha256>-<mode>
    grep -qx "${b%-*}" "$live" || { rm -f "$o"; k=$((k+1)); }
  done
  rm -f "$live"
  echo "cache objects removed: $k; cache now $(du -sh "$R/cas" | cut -f1)"
fi
[ "${1:-}" != --trim ] || fstrim -v /
