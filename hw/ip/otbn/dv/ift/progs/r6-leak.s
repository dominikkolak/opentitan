.section .text.start
main:
  jal             x1, load_shares
example:
  bn.sel          w5, w5, w4, FG0.C
  ecall
