.text
.globl load_shares
load_shares:
  la              x2, share0
  bn.lid          x0, 0(x2)
  la              x2, share1
  li              x3, 1
  bn.lid          x3, 0(x2)
  ret

.data

.balign 32
.globl share0
share0:
  .word 0x1a466884
  .word 0xe255accb
  .word 0x39292d22
  .word 0xe5121482
  .word 0x99dd251d
  .word 0x9f199504
  .word 0x8e7aa6e9
  .word 0x6bad6be2
.globl share1
share1:
  .word 0x0438cc9d
  .word 0xb39c10bb
  .word 0xb98df278
  .word 0x16993b7e
  .word 0x1adbf526
  .word 0x3ab75293
  .word 0x52525979
  .word 0x9859f9ab
