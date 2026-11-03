#!/bin/bash

# build elfs from progs and crypto tests
# Note: TOOLCHAIN_PATH=/home/dom/tools/riscv bash build.sh

set -e
cd "$(dirname "$0")/../../../../.."
IFT=hw/ip/otbn/dv/ift
C=sw/otbn/crypto
TMP=$(mktemp -d)
trap 'rm -rf $TMP' EXIT
mkdir -p $IFT/elfs

build() {
  name=$1
  shift
  objs=()
  for src in "$@"; do
    obj=$TMP/$name-$(basename $src .s).o
    python3 hw/ip/otbn/util/otbn_as.py -o $obj $src
    objs+=($obj)
  done
  python3 hw/ip/otbn/util/otbn_ld.py -o $IFT/elfs/$name.elf "${objs[@]}"
  echo "built $IFT/elfs/$name.elf"
}

# synth styleguide examples + harness!
for src in $IFT/progs/*.s; do
  name=$(basename $src .s)
  case $name in
    harness|p256_a2b_bug) ;;
    *) build $name $src $IFT/progs/harness.s ;;
  esac
done

# deps: sw/otbn/crypto/tests/
P256_A2B_DEPS="$C/p256_b2a.s $C/p256_base.s $C/p256_isoncurve.s $C/p256_isoncurve_proj.s $C/p256_shared_key.s"
build p256_a2b $C/tests/p256_arithmetic_to_boolean_test.s $C/p256_a2b.s $P256_A2B_DEPS
build p256_a2b_mod $C/tests/p256_arithmetic_to_boolean_mod_test.s $C/p256_a2b.s $P256_A2B_DEPS

# buggy copy not real a2b
build p256_a2b_bug $C/tests/p256_arithmetic_to_boolean_test.s $IFT/progs/p256_a2b_bug.s $P256_A2B_DEPS

build p384_b2a $C/tests/p384_boolean_to_arithmetic_test.s $C/p384_b2a.s

build p256_ecdsa_sign $C/tests/p256_ecdsa_sign_test.s $C/p256_b2a.s $C/p256_base.s $C/p256_isoncurve.s $C/p256_sign.s
build rsa_512_dec $C/tests/rsa_512_dec_test.s $C/modexp.s $C/montmul.s $C/run_rsa_mem.s
