.section .text.start
main:
  jal             x1, load_shares
example:
  bn.mov          w1, w0
  ecall
