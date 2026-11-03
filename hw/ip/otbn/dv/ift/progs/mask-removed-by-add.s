.section .text.start
main:
  jal             x1, load_shares
example:
  bn.wsrr         w2, URND
  bn.xor          w0, w2, w0
  bn.add          w0, w2, w0
  bn.xor          w9, w9, w9
  bn.xor          w4, w1, w0
  ecall
