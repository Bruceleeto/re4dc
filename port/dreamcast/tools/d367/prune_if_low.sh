#!/bin/bash
# prune_if_low.sh [low_gb]   (WSL) -- the disk hygiene hook: staging steps call it before they check free space.
# When C: or D: has less than low_gb (default PRUNE_LOW_GB=40) free:
#   1. prunes old disc images in the evidence roots (--apply --windows-only: frees C:/D: directly), at most once every
#      PRUNE_WIN_EVERY_MIN (30) minutes. It takes ~1-2 min (PowerShell scan), so it runs in the background unless C:
#      is below PRUNE_SYNC_GB (20), where the caller's 16 GiB floor check is close: then it runs before returning;
#   2. starts the WSL pass (--apply --no-windows: objdirs + staged discs in idle /root/probe units) in the
#      background, at most once every PRUNE_WSL_EVERY_MIN (120) minutes; it frees ext4 space only (vhdx growth).
# PRUNE_AUTO=0 disables the hook. Never fails the caller. Logs: /root/probe/_prune-manifests/auto-*.log.
here=$(cd "$(dirname "$0")" && pwd)
LOW=${1:-${PRUNE_LOW_GB:-40}}
M=/root/probe/_prune-manifests
mkdir -p $M 2>/dev/null || exit 0
gb() { df -P -k "$1" 2>/dev/null | awk 'NR==2{printf "%d", $4/1048576}'; }
c=$(gb /mnt/c); d=$(gb /mnt/d)
[ -n "$c" ] || exit 0
[ "$c" -lt "$LOW" ] || { [ -n "$d" ] && [ "$d" -lt "$LOW" ]; } || exit 0
if [ "${PRUNE_AUTO:-1}" = 0 ]; then
  echo "prune_if_low: C: ${c} GB, D: ${d} GB free (< ${LOW} GB); PRUNE_AUTO=0, not pruning"; exit 0
fi
ts=$(date +%Y%m%d-%H%M%S)
if [ -z "$(find $M/.last-win-apply -mmin -${PRUNE_WIN_EVERY_MIN:-30} 2>/dev/null)" ]; then
  touch $M/.last-win-apply
  if [ "$c" -lt "${PRUNE_SYNC_GB:-20}" ]; then
    echo "prune_if_low: C: ${c} GB, D: ${d} GB free: pruning old evidence-root discs now (disk hygiene rule)"
    bash "$here/prune_build_outputs.sh" --apply --windows-only --quiet > $M/auto-win-$ts.log 2>&1
    grep -E '^(TOTAL|manifest|prune_build_outputs:)' $M/auto-win-$ts.log
    echo "prune_if_low: now C: $(gb /mnt/c) GB, D: $(gb /mnt/d) GB free"
  else
    nohup setsid bash "$here/prune_build_outputs.sh" --apply --windows-only --quiet > $M/auto-win-$ts.log 2>&1 < /dev/null &
    echo "prune_if_low: C: ${c} GB, D: ${d} GB free (< ${LOW} GB): evidence-disc prune started ($M/auto-win-$ts.log)"
  fi
fi
if [ -z "$(find $M/.last-wsl-apply -mmin -${PRUNE_WSL_EVERY_MIN:-120} 2>/dev/null)" ]; then
  touch $M/.last-wsl-apply
  nohup setsid bash "$here/prune_build_outputs.sh" --apply --no-windows --quiet > $M/auto-wsl-$ts.log 2>&1 < /dev/null &
  echo "prune_if_low: WSL build-output prune started in the background ($M/auto-wsl-$ts.log)"
fi
exit 0
