# every location: 1x 32-bit word

ACC = [f'acc.{k}' for k in range(8)]
MOD = [f'mod.{k}' for k in range(8)]
WSRS = {0: MOD, 3: ACC}  # WSR 1 and 2 are RND and URND

ARITH = ['bn.add', 'bn.addc', 'bn.addi', 'bn.sub', 'bn.subb', 'bn.subi', 'bn.cmp', 'bn.cmpb']
GPR_ALU = ['add', 'sub', 'and', 'or', 'xor', 'sll', 'srl', 'sra',
           'addi', 'andi', 'ori', 'xori', 'slli', 'srli', 'srai']
VEC_MOD = ['bn.addvm', 'bn.subvm', 'bn.mulvm', 'bn.mulvml']

def wdr(i):
    return [f'w{i}.{k}' for k in range(8)]

def gpr(i):
    if i == 0:
        return []
    return [f'x{i}']

def flags(group, which='CMLZ'):
    return [f'fg{group}.{f}' for f in which]

def dmem(addr, n=1):
    return [f'dmem.{addr + 4 * k:#x}' for k in range(n)]

def register_of(loc):
    if loc[0] in 'wam':
        return loc.split('.')[0]
    return loc

def words_of(reg):
    if reg[0] == 'w':
        return wdr(int(reg[1:]))
    if reg == 'acc':
        return ACC
    if reg == 'mod':
        return MOD
    return [reg]

def csr_locs(c): # TODO: test
    if c == 0x7c0 or c == 0x7c1: # 0x7c0/0x7c1: FG0/FG1, 
        return flags(c - 0x7c0)
    if c == 0x7c8: # 0x7c8: both
        return flags(0) + flags(1)
    if 0x7d0 <= c <= 0x7d7: # 0x7d0-0x7d7: MOD word
        return [MOD[c - 0x7d0]]
    return []

class Effects:
    def __init__(self):
        self.reads = []
        self.uses = []
        self.writes = []
        self.selector = []
        self.sel_dst_is_src = False

    def read(self, locs):
        for loc in locs:
            if loc not in self.reads:
                self.reads.append(loc)
        return locs

    # tags = copy, xor, fn, const, fresh
    def write(self, locs, deps, tag='fn'):
        for loc in locs:
            self.writes.append((loc, list(deps), tag))

    def copy(self, dst, src):
        self.read(src)
        for i in range(len(dst)):
            self.write([dst[i]], [src[i]], 'copy')

    def increment(self, o, names):
        for n in names:
            if o[n + '_inc']:
                self.write(gpr(o[n]), gpr(o[n]))

    def used(self):
        out = []
        for group in self.uses:
            out = out + group
        return out

def effects(insn, x): # worlds shities decoder :)
    m = insn.insn.mnemonic
    o = insn.op_vals
    e = Effects()

    if m in GPR_ALU:
        src = e.read(gpr(o['grs1']) + gpr(o.get('grs2', 0)))
        if m in ['xor', 'sub'] and o['grs1'] == o['grs2']:
            e.write(gpr(o['grd']), [], 'const')
        else:
            e.write(gpr(o['grd']), src, 'xor' if m in ['xor', 'xori'] else 'fn')

    elif m in ['lui', 'jal']:
        e.write(gpr(o['grd']), [], 'const')

    elif m == 'jalr':
        e.uses.append(gpr(o['grs1']))
        e.write(gpr(o['grd']), [], 'const')

    elif m in ['beq', 'bne']:
        e.uses.append(gpr(o['grs1']) + gpr(o['grs2']))

    elif m == 'loop':
        e.uses.append(gpr(o['grs']))

    elif m == 'lw':
        e.uses.append(gpr(o['grs1']))
        e.copy(gpr(o['grd']), dmem((x[o['grs1']] + o['offset']) & 0xffffffff))

    elif m == 'sw':
        e.uses.append(gpr(o['grs1']))
        e.copy(dmem((x[o['grs1']] + o['offset']) & 0xffffffff), gpr(o['grs2']))

    elif m in ['bn.lid', 'bn.sid']:
        idx = 'grd' if m == 'bn.lid' else 'grs2'
        e.uses.append(gpr(o['grs1']))
        e.uses.append(gpr(o[idx]))
        mem = dmem((x[o['grs1']] + o['offset']) & 0xffffffff, 8)
        reg = wdr(x[o[idx]] & 31)
        if m == 'bn.lid':
            e.copy(reg, mem)
        else:
            e.copy(mem, reg)
        e.increment(o, ['grs1', idx])

    elif m == 'bn.movr':
        e.uses.append(gpr(o['grd']))
        e.uses.append(gpr(o['grs']))
        e.copy(wdr(x[o['grd']] & 31), wdr(x[o['grs']] & 31))
        e.increment(o, ['grd', 'grs'])

    elif m == 'bn.mov':
        e.copy(wdr(o['wrd']), wdr(o['wrs']))

    elif m in ['csrrs', 'csrrw']:
        if o['csr'] in [0xfc0, 0xfc1]:  # RND, URND
            e.write(gpr(o['grd']), [], 'fresh')
        else:
            old = e.read(csr_locs(o['csr']))
            e.write(gpr(o['grd']), old, 'copy' if len(old) == 1 else 'fn')
            if m == 'csrrw':
                e.write(old, e.read(gpr(o['grs1'])))
            elif o['grs1']:
                e.write(old, old + e.read(gpr(o['grs1'])))

    elif m == 'bn.wsrr':
        if o['wsr'] in [1, 2]:
            e.write(wdr(o['wrd']), [], 'fresh')
        elif o['wsr'] in WSRS:
            e.copy(wdr(o['wrd']), WSRS[o['wsr']])
        else:
            e.write(wdr(o['wrd']), [], 'const')

    elif m == 'bn.wsrw':
        if o['wsr'] in WSRS:
            e.copy(WSRS[o['wsr']], wdr(o['wrs']))

    elif m in ['bn.and', 'bn.or', 'bn.xor', 'bn.not']:
        if m == 'bn.not':
            a = []
            b = wdr(o['wrs'])
        else:
            a = wdr(o['wrs1'])
            b = wdr(o['wrs2'])
        e.read(a + b)
        aligned = o['shift_bits'] == 0
        dst = wdr(o['wrd'])
        flag_locs = flags(o['flag_group'], 'MLZ')
        if m == 'bn.xor' and aligned and o['wrs1'] == o['wrs2']:
            e.write(dst + flag_locs, [], 'const')
        else:
            tag = 'xor' if aligned and m in ['bn.xor', 'bn.not'] else 'fn'
            for k in range(8):
                if aligned:
                    e.write([dst[k]], a[k:k + 1] + b[k:k + 1], tag)
                else:
                    e.write([dst[k]], a[k:k + 1] + b, tag)
            e.write(flag_locs, a + b)

    elif m in ARITH:
        if 'wrs2' in o:
            src = wdr(o['wrs1']) + wdr(o['wrs2'])
        else:
            src = wdr(o['wrs'])
        if m in ['bn.addc', 'bn.subb', 'bn.cmpb']:
            src = src + flags(o['flag_group'], 'C')
        e.read(src)
        dst = flags(o['flag_group'])
        if 'wrd' in o:
            dst = wdr(o['wrd']) + dst
        if m in ['bn.sub', 'bn.cmp'] and o['wrs1'] == o['wrs2'] and o['shift_bits'] == 0:
            e.write(dst, [], 'const')
        else:
            e.write(dst, src)

    elif m in ['bn.addm', 'bn.subm']:
        e.write(wdr(o['wrd']), e.read(wdr(o['wrs1']) + wdr(o['wrs2']) + MOD))

    elif m == 'bn.rshi':
        both = wdr(o['wrs2']) + wdr(o['wrs1'])
        dst = wdr(o['wrd'])
        tag = 'copy' if o['imm'] % 32 == 0 else 'fn'
        for k in range(8):
            # k comes from what lo..lo+31 touches
            lo = 32 * k + o['imm']
            e.write([dst[k]], e.read(both[lo // 32:(lo + 31) // 32 + 1]), tag)

    elif m == 'bn.sel':
        e.selector = flags(o['flag_group'], 'CMLZ'[o['flag']])
        e.sel_dst_is_src = o['wrd'] in [o['wrs1'], o['wrs2']]
        a = e.read(wdr(o['wrs1']))
        b = e.read(wdr(o['wrs2']))
        dst = wdr(o['wrd'])
        for k in range(8):
            e.write([dst[k]], [a[k], b[k]])

    elif m.startswith('bn.mulqacc'):
        q1 = 2 * o['wrs1_qwsel']
        q2 = 2 * o['wrs2_qwsel']
        src = wdr(o['wrs1'])[q1:q1 + 2] + wdr(o['wrs2'])[q2:q2 + 2]
        if not o['zero_acc']:
            src = src + ACC
        e.read(src)
        e.write(ACC, src)
        if m == 'bn.mulqacc.wo':
            e.write(wdr(o['wrd']) + flags(o['flag_group'], 'MLZ'), src)
        elif m == 'bn.mulqacc.so':
            h = 4 * o['wrd_hwsel']
            e.write(wdr(o['wrd'])[h:h + 4] + flags(o['flag_group'], 'ZM' if h else 'ZL'), src)

    else:
        src = []
        for name in o:
            if name.startswith('wrs'):
                src = src + wdr(o[name])
        if m in VEC_MOD:
            src = src + MOD
        for name in o:
            if name.startswith('grs'):
                src = src + gpr(o[name])
        e.read(src)
        if 'wrd' in o:
            e.write(wdr(o['wrd']), e.reads)

    return e
