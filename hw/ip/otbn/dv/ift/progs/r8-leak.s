.section .text.start
main:
  jal             x1, load_shares
example:
  bn.mulqacc.wo   w6, w4.0, w0.0, 0, FG0
  bn.mulqacc.wo   w7, w5.0, w1.0, 0, FG0
  ecall
