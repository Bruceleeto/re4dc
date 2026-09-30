#!/usr/bin/env bash
# Lane autosave (D367_WORKSTREAMS.md; user OK 2026-09-30). Root crontab runs it every 15 minutes:
#   */15 * * * * /root/probe/d367-resume-20260928/step1/port/dreamcast/tools/d367/autosave.sh
# For each lane tree /root/work/lanes/<lane> with uncommitted work, it snapshots the working state (tracked changes +
# untracked, non-ignored files up to 5 MB) through a temporary index and force-pushes it to origin
# refs/heads/autosave/<lane> (parent = the lane's HEAD). The working tree, the index and lane/<lane> are never touched.
# Restore after a lost session:  git -C /root/work/lanes/<lane> fetch origin autosave/<lane>
#                                 git -C /root/work/lanes/<lane> diff HEAD FETCH_HEAD      # review
#                                 git -C /root/work/lanes/<lane> checkout FETCH_HEAD -- <paths>
set -u
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
D=/root/probe/lanes
LOG=$D/autosave.log
mkdir -p $D
exec 9>$D/.autosave.lock
flock -n 9 || exit 0
for t in /root/work/lanes/*/; do
  t=${t%/}; L=$(basename "$t")
  [ -e "$t/.git" ] || continue
  cd "$t" || continue
  [ -z "$(git status --porcelain --untracked-files=normal)" ] && continue
  idx=$(mktemp -p $D .idx-$L.XXXXXX)
  cp "$(git rev-parse --git-path index)" "$idx"
  GIT_INDEX_FILE=$idx git add -A 2>/dev/null
  big=$(git ls-files --others --exclude-standard -z | xargs -0 -r find 2>/dev/null -maxdepth 0 -type f -size +5M)
  [ -n "$big" ] && echo "$big" | while read -r f; do GIT_INDEX_FILE=$idx git rm -q --cached -- "$f"; done
  tree=$(GIT_INDEX_FILE=$idx git write-tree); rm -f "$idx"
  last=$D/.autosave-$L.tree
  [ -f "$last" ] && [ "$(cat "$last")" = "$tree" ] && continue
  c=$(git commit-tree "$tree" -p HEAD -m "autosave $L $(date '+%F %T') (working state over $(git rev-parse --short HEAD))")
  if git push -q -f origin "$c:refs/heads/autosave/$L" 2>>"$LOG"; then
    echo "$tree" > "$last"
    echo "$(date '+%F %T') $L autosaved $(git rev-parse --short "$c") over $(git rev-parse --short HEAD)$([ -n "$big" ] && echo " (skipped >5MB: $(echo "$big" | wc -l))")" >> "$LOG"
  else
    echo "$(date '+%F %T') $L push FAILED" >> "$LOG"
  fi
done
tail -n 500 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
