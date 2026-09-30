#!/usr/bin/env bash
# Work-loss check (D367_WORKSTREAMS.md): nothing may live only in a working tree or an unversioned folder.
#   bash port/dreamcast/tools/d367/work-check.sh          # all lanes + the landing tree + the private store
# Reports, per tree: uncommitted files, commits not pushed to origin, and the lane branch vs origin/dreamcast-port.
# Exit 1 if any lane has uncommitted or unpushed work, or the private store has unrecorded changes.
set -u
REPO=/root/work/re4-dreamcast
LANES=/root/work/lanes
STORE="/mnt/c/Game Dev/Emulators/re4-assets-private"
bad=0
git -C "$REPO" fetch -q origin 2>/dev/null || echo "WARN: fetch failed (offline?)"
tip=$(git -C "$REPO" rev-parse origin/dreamcast-port)
printf '%-44s %-26s %6s %8s %8s\n' tree branch dirty unpushed notland
check() {
  local t=$1 br up dirty unpushed notland
  [ -d "$t" ] || return
  br=$(git -C "$t" symbolic-ref -q --short HEAD || echo "(detached)")
  dirty=$(git -C "$t" status --porcelain --untracked-files=normal | grep -v '^?? .*\(obj\|build\|out\)/' | wc -l)
  if [ "$br" = "(detached)" ]; then
    unpushed=$(git -C "$t" rev-list --count HEAD --not --remotes=origin)
  else
    up=$(git -C "$t" rev-parse -q --verify "origin/$br" || true)
    if [ -z "$up" ]; then unpushed="nobr"; else unpushed=$(git -C "$t" rev-list --count "origin/$br..HEAD"); fi
  fi
  notland=$(git -C "$t" rev-list --count "$tip..HEAD")
  printf '%-44s %-26s %6s %8s %8s\n' "${t#/root/}" "$br" "$dirty" "$unpushed" "$notland"
  { [ "$dirty" != 0 ] || [ "$unpushed" != 0 ]; } && bad=1
}
check /root/probe/d367-resume-20260928/step1
for t in "$LANES"/*/; do check "${t%/}"; done
echo "== lane branches on origin (commits not in dreamcast-port)"
git -C "$REPO" for-each-ref --format='%(refname:short)' 'refs/remotes/origin/lane/*' | while read r; do
  printf '   %-30s %4s not landed, last %s\n' "$r" "$(git -C "$REPO" rev-list --count "$tip..$r")" \
    "$(git -C "$REPO" log -1 --format='%cr: %s' "$r" | cut -c1-70)"
done
echo "== private store ($STORE)"
if [ -d "$STORE/.git" ]; then
  n=$(git -C "$STORE" status --porcelain | wc -l); echo "   git: $n uncommitted"; [ "$n" != 0 ] && bad=1
else
  echo "   git: not initialised"; bad=1
fi
if [ -f "$STORE/manifest.py" ]; then
  (cd "$STORE" && python3 manifest.py --check | grep -v '^   ' | tr '\n' ' '); echo
  (cd "$STORE" && python3 manifest.py --check >/dev/null) || bad=1
fi
echo "== free space"; df -h /mnt/c /mnt/d / 2>/dev/null | awk 'NR>1{print "   "$6" "$4" free"}'
[ $bad = 0 ] && echo "WORK-CHECK CLEAN" || echo "WORK-CHECK: unsaved work above (commit + push, or run manifest.py and commit the store)"
exit $bad
