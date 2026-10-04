#!/bin/bash
# pl08_pack_test.sh <package> <ACTOR_PL08_DIR> <leon4k bundle dir> <out dir>  (ACTOR_PL08_PACK host gates)
# Builds pl08_pack_test.cpp with the target's game/actor_pl08_pack_check.inc and runs: the identity of the package
# against the compiled frozen arrays, the lifetime scenarios, and every malformed variant (pl08_pack.py variants) with
# its expected refusal. Exits 1 on any mismatch. The out dir holds converted meshes: keep it private.
set -euo pipefail
PKG=$1; P8=$2; L4=$3; OUT=$4
HERE=$(cd "$(dirname "$0")" && pwd); GAME=$HERE/../../game
mkdir -p "$OUT"
g++ -std=gnu++20 -O1 -Wall -Wextra -fsanitize=address,undefined -fno-sanitize-recover=all -I"$GAME" -I"$P8" -I"$L4" \
    "$HERE/pl08_pack_test.cpp" -o "$OUT/pl08_pack_test"
"$OUT/pl08_pack_test" identity "$PKG"
"$OUT/pl08_pack_test" life "$PKG" | tail -1
python3 "$HERE/pl08_pack.py" variants "$PKG" "$OUT/variants" > /dev/null
declare -A WANT=([ok]=none [short]=size [long]=size [magic]=header [version]=header [count]=header [header-crc]=hash
  [payload-bit]=hash [payload-bit-fixed]=hash [reserved]=header [role-swap]=table [count-field]=table [offset-moved]=table
  [offset-misaligned]=table [offset-oob]=table [table-reserved]=table [empty]=size [weight-bone-fixed]=hash)
bad=0
for f in "$OUT"/variants/*.re4cp; do
  n=$(basename "$f" .re4cp); got=$("$OUT/pl08_pack_test" validate "$f" | awk '{print $2}')
  if [ "$got" = "${WANT[$n]:-?}" ]; then echo "variant $n: $got ok"; else echo "variant $n: got $got want ${WANT[$n]:-?} MISMATCH"; bad=1; fi
done
[ $bad = 0 ] && echo "PL08 PACK HOST GATES PASS" || { echo "PL08 PACK HOST GATES FAIL"; exit 1; }
