#!/bin/bash
# Decision #132 (Brian's OK, 9 Nov): the Copernicus DEM GLO-30 tiles under
# our 17 regions, from the public AWS Open Data bucket (no account): 40
# tiles, ~1.6 GB, into cache/cop30/ (a new, empty folder: downloaded files
# are data only). Licence: Copernicus DEM, free with attribution
# ("(c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018
# provided under COPERNICUS by the European Union and ESA").
#   sbatch -A engr-class-any -p linuxlab-project -c 1 --mem 2G -t 1:00:00 \
#          -o logs/cop30_download_%j.out cluster/cop30_download.sh
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
BASE=https://copernicus-dem-30m.s3.amazonaws.com
n=0; bad=0
while read -r t keys; do
  case "$t" in "#"*|"") continue ;; esac
  f=cache/cop30/$t.tif
  if [ -s "$f" ]; then n=$((n+1)); continue; fi
  if curl -sS --fail --retry 3 -A "travel-speed-research-script" \
       -o "$f.part" "$BASE/$t/$t.tif"; then
    mv "$f.part" "$f"; n=$((n+1))
  else
    rm -f "$f.part"; bad=$((bad+1)); echo "FAILED $t ($keys)"
  fi
  sleep 1
done < cluster/cop30_tiles.txt
echo "$(date '+%F %T') tiles: $n ok, $bad failed; $(du -sh cache/cop30 | cut -f1)"
