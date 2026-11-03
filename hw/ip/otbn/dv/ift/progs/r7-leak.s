.section .text.start
main:
  jal             x1, load_shares
example:
  bn.sel          w4, w1, w0, FG0.C
  ecall
