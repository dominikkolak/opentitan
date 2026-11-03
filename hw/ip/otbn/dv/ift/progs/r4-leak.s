.section .text.start
main:
  jal             x1, load_shares
example:
  bn.xor          w9, w9, w9
  bn.rshi         w1, w1, w9 >> 254
  bn.xor          w4, w1, w0
  ecall
