.section .text.start
main:
  jal             x1, load_shares
example:
  beq             x5, x0, done
  addi            x2, x0, 0
done:
  addi            x3, x0, 0
  ecall
