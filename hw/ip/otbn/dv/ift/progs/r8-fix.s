.section .text.start
main:
  jal             x1, load_shares
example:
  bn.xor          w9, w9, w9
  bn.mulqacc.wo   w6, w4.0, w0.0, 0, FG0
  bn.wsrw         ACC, w9
  bn.mulqacc.wo   w9, w9.0, w9.0, 0, FG0
  bn.mulqacc.wo   w7, w5.0, w1.0, 0, FG0
  ecall
