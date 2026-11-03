.section .text.start
main:
  jal             x1, load_shares
example:
  bn.xor          w4, w0, w0
  bn.xor          w5, w1, w1
  ecall
