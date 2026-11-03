.globl arithmetic_to_boolean_mod
.globl arithmetic_to_boolean

.text

arithmetic_to_boolean:

  bn.rshi   w19, w19, w31 >> 1
  bn.wsrr   w1, URND
  bn.wsrr   w2, URND
  bn.rshi   w2, w31, w2 >> 255
  bn.rshi   w19, w31, w19 >> 255
  bn.rshi   w12, w12, w31 >> 1
  bn.rshi   w12, w31, w12 >> 255

  bn.add    w3, w1, w1
  bn.addc   w4, w2, w2
  bn.rshi   w4, w4, w31 >> 1
  bn.rshi   w4, w31, w4 >> 255

  bn.xor    w20, w1, w18
  bn.xor    w21, w2, w19
  bn.xor    w31, w31, w31

  bn.and    w5, w1, w20
  bn.and    w6, w2, w21

  bn.xor    w20, w3, w11
  bn.xor    w21, w4, w12
  bn.xor    w31, w31, w31

  bn.xor    w1, w1, w20
  bn.xor    w2, w2, w21

  bn.and    w1, w1, w18
  bn.and    w2, w2, w19
  bn.xor    w31, w31, w31

  bn.xor    w5, w5, w1
  bn.xor    w6, w6, w2

  bn.and    w1, w3, w11
  bn.and    w2, w4, w12
  bn.xor    w31, w31, w31

  bn.xor    w5, w5, w1
  bn.xor    w6, w6, w2

  loopi     256, 14

    bn.and     w1, w3, w18
    bn.and     w2, w4, w19
    bn.xor     w31, w31, w31

    bn.xor     w1, w1, w5
    bn.xor     w2, w2, w6

    bn.and     w3, w3, w11
    bn.and     w4, w4, w12
    bn.xor     w31, w31, w31

    bn.xor     w1, w1, w3
    bn.xor     w2, w2, w4

    bn.add    w3, w1, w1
    bn.addc   w4, w2, w2
    bn.rshi   w4, w4, w31 >> 1
    bn.rshi   w4, w31, w4 >> 255

  bn.xor    w20, w20, w3
  bn.xor    w21, w21, w4
  bn.xor    w31, w31, w31

  ret

arithmetic_to_boolean_mod:

  bn.mov    w24, w19
  bn.mov    w18, w19
  bn.mov    w12, w31
  bn.mov    w19, w31
  bn.mov    w25, w11

  jal       x1, arithmetic_to_boolean

  bn.mov    w26, w20
  bn.mov    w27, w21

  bn.mov    w18, w24
  bn.mov    w19, w31
  bn.mov    w11, w25
  bn.mov    w12, w31

  bn.wsrr   w29, MOD

  bn.addi   w12, w12, 0x2
  bn.sub    w11, w11, w29
  bn.subb   w12, w12, w31
  bn.sub    w22, w22, w22

  jal       x1, arithmetic_to_boolean

  bn.mov    w19, w24

  bn.mov    w31, w31
  bn.mov    w25, w20

  bn.cmp    w21, w31

  bn.sel    w20, w25, w26, FG0.Z
  bn.sel    w31, w31, w31, FG0.Z

  ret
