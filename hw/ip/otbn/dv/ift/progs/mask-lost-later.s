.section .text.start
main:
  jal             x1, load_shares
example:
  bn.wsrr         w2, URND
  bn.xor          w3, w0, w2
  bn.xor          w9, w9, w9
  bn.xor          w4, w3, w1
  bn.xor          w9, w9, w9
  bn.xor          w5, w4, w2
  ecall
