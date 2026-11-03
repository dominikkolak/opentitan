.section .text.start
main:
  jal             x1, load_shares
example:
  bn.sub          w4, w4, w0
  bn.sub          w9, w9, w9
  bn.sub          w5, w5, w1
  ecall
