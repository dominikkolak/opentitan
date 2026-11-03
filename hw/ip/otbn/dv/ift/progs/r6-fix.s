.section .text.start
main:
  jal             x1, load_shares
example:
  bn.wsrr         w6, URND
  bn.sel          w6, w5, w4, FG0.C
  bn.wsrr         w5, URND
  bn.mov          w5, w6
  ecall
