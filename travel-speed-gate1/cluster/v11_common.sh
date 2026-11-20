# Shared by the T1 v1.1 refresh jobs (19 Nov 2026). Brian's cap (19 Nov):
# 13 GB of downloads in all; the OSM pages + GPX files used 8.45 GB, so the
# new lidar blocks + 1 m DEM cells may add at most 4.5 GB (we stop at 4.0).
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
ARCH=data/archive/v1_2026-10_downstream
MARK=logs/.v11_fetch_start
MAXNEW=4000000000
[ -e "$MARK" ] || touch "$MARK"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/refresh.log; }
step() {
  local name=$1; shift
  say "start $name"
  if "$@" >> logs/refresh_steps.log 2>&1; then say "done  $name"
  else say "FAILED $name"; exit 1; fi
}
newbytes() { find cache/ept cache/dem1m -newer "$MARK" -type f -printf "%s\n" 2>/dev/null \
               | awk '{s += $1} END {printf "%d", s}'; }
guard() {
  local b; b=$(newbytes)
  say "new downloads so far: $((b / 1000000)) MB (stop at $((MAXNEW / 1000000)) MB)"
  if [ "$b" -gt "$MAXNEW" ]; then
    say "STOP: new downloads passed the 13 GB cap; ask Brian"; exit 3
  fi
}
