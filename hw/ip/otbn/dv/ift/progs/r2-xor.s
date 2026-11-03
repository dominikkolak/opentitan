.section .text.start
main:
  jal             x1, load_shares
example:
  bn.xor          w4, w1, w0
  ecall
