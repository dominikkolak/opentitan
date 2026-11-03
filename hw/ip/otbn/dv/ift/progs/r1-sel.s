.section .text.start
main:
  jal             x1, load_shares
example:
  bn.sel          w1, w0, w0, FG0.C
  ecall
