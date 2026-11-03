# ift-dynamic-taint-analysis

This tool is....................

# example

```
python3 ift.py elfs/p256_a2b.elf
python3 ift.py elfs/p256_a2b.elf --trace
python3 ift.py elfs/masked.elf --mask-xor
python3 ift.py elfs/p256_a2b.elf -a ann/p256_a2b_trusted.ann
python3 ift.py any.elf -s w11-w12=x.0 -s w18-w19=x.1
./build.sh
```

## annotations

```
testcase sw/otbn/crypto/tests/p256_arithmetic_to_boolean_test.hjson
share w11-w12 x.0
share w18-w19 x.1
share x5 s
boolean s
ignore arithmetic_to_boolean trusted gadget
waive symbol+0x10 reason
```

TODO: finish readme when core is ready ready!
