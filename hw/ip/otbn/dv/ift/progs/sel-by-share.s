.section .text.start
main:
  jal             x1, load_shares
example:
  bn.xor          w6, w6, w6
  bn.addi         w5, w6, 1
  bn.addi         w3, w0, 0
  bn.sel          w4, w5, w6, FG0.L
  ecall
