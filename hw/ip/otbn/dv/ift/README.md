# ift-dynamic-taint-analysis

This tool is....................

# example

```
python3 ift.py elfs/p256_a2b.elf
python3 ift.py elfs/p256_a2b.elf --trace
python3 ift.py elfs/r5-masked.elf --trace-all
python3 ift.py elfs/masked.elf --mask-xor
python3 ift.py elfs/p256_a2b.elf -a ann/p256_a2b_trusted.ann
python3 ift.py any.elf -s w11-w12=x.0 -s w18-w19=x.1
./build.sh
```

exit code: 0 clean, 1 open findings, 2 program faulted (ERR_BITS set)

## annotations

```
testcase sw/otbn/crypto/tests/p256_arithmetic_to_boolean_test.hjson
share w11-w12 x.0
share w18-w19 x.1
share x5 s
boolean s
share KEY_S0_L k.0
ignore arithmetic_to_boolean trusted gadget
out arithmetic_to_boolean w20-w21 x.0
waive symbol+0x10 reason
```

`out`: on return of the routine the loc is a plain share again

TODO: finish readme when core is ready ready!

## performence

p256_ecdsa around 400s to run
rsa_512 takes around 90s to run

time measured on base ift without extnesions and on a Intel i5-1240P