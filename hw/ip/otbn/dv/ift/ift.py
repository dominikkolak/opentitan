#!/usr/bin/env python3

#TODO: align print output!

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '../../../../..'))
OTBN = os.path.join(REPO, 'hw/ip/otbn')
sys.path.insert(0, os.path.join(OTBN, 'dv/otbnsim'))
sys.path.insert(0, os.path.join(OTBN, 'util'))

from elftools.elf.elffile import ELFFile
from otbn_as import find_insn_schemes
from shared.insn_yaml import load_insns_yaml
from shared.testcase import OtbnTestCase
from sim.load_elf import load_elf
from sim.standalonesim import StandaloneSim, _TEST_URND_SEED
from sim.state import FsmState

from effects import effects, wdr, dmem, register_of, words_of
from mask_xor import MaskXor

# TODO: run fomrat check

# fixed RND values for now
# TODO: check if this is a issue
REP = 2 ** 192 + 2 ** 128 + 2 ** 64 + 1
RND_STREAM = [0xAAAAAAAA_99999999 * REP, 0xCCCCCCCC_BBBBBBBB * REP]
# pseudo instructions and theird parts
PSEUDO = {'la': ['lui', 'addi'], 'li': ['lui', 'addi'], 'ret': ['jalr'], 'j': ['jal'], 'nop': ['addi'],
          'unimp': ['csrrw']}
STATUS_ORDER = ['OPEN', 'MASK LOST', 'WAIVED', 'IGNORED', 'CLEARED']

def union(sets): # or frozenset again?
    out = set()
    for s in sets:
        out = out | s
    return out

# add to label where secret is first unmasked, later uses point back to this pc (stops flood!)
def marker(pc, s):
    return f'@{pc}:{s}'

# TODO: come up with final anotations style
def load_ann(path, extra_shares): # just a temporery annotation schema
    ann = {'testcase': None, 'shares': [], 'boolean': [], 'ignore': {}, 'waive': {}}
    lines = []
    if path:
        lines = open(path).read().splitlines()
    for share in extra_shares:
        lines.append('share ' + share.replace('=', ' '))
    for line in lines:
        words = line.strip().split(None, 2)
        if len(words) == 0:
            continue
        key = words[0]
        if key == 'testcase':
            ann['testcase'] = words[1]
        elif key == 'share':
            ann['shares'].append((words[1], words[2]))
        elif key == 'boolean':
            ann['boolean'].append(words[1])
        elif key == 'ignore' or key == 'waive':
            ann[key][words[1]] = words[2] if len(words) > 2 else ''
        else:
            sys.exit(f'{path}: unknown line: {line}')
    return ann

class Hit:
    def __init__(self, rule, secret, root, later):
        self.rule = rule
        self.secret = secret
        self.root = root
        self.later = later
        # (loc, when) pairs that were combined, mask_xor checks these!!!
        self.parts = []
        self.cleared = None
        self.ignored = False

class Finding:
    def __init__(self, pc, secret):
        self.pc = pc
        self.secret = secret
        self.rules = set()
        self.later_sites = set()
        self.reasons = set()
        self.open_root = 0
        self.open_later = 0
        self.open_not_ignored = 0

    def add(self, hit, pc):
        if hit.later:
            self.later_sites.add(pc)
        else:
            self.rules.add(hit.rule)
        if hit.cleared:
            self.reasons.add(hit.cleared)
            return
        if hit.later:
            self.open_later += 1
        else:
            self.open_root += 1
        if not hit.ignored:
            self.open_not_ignored += 1

    # MASK LOST: this happnes when the root was proven masked by like a judge, but then a later use is not safe
    def status(self, waived):
        if self.pc in waived:
            return 'WAIVED'
        if self.open_root == 0 and self.open_later == 0:
            return 'CLEARED'
        if self.open_not_ignored == 0:
            return 'IGNORED'
        if self.open_root == 0:
            return 'MASK LOST'
        return 'OPEN'

class Step:
    def __init__(self, pc, effects, new, hits):
        self.pc = pc
        self.effects = effects
        self.new = new
        self.hits = hits

class Run:
    
    # TODO: manual step

    def __init__(self, elf, ann, mask_xor=False):
        self.elf = elf
        self.ann = ann
        self.sim = StandaloneSim()
        load_elf(self.sim, elf)
        self.routines = text_symbols(elf)
        self.lines = source_lines(elf, self.sim.program)
        self.start_sim()

        self.labels = {}
        self.prev = {}
        self.findings = {}
        self.secret_of = {}
        for spec, who in ann['shares']:
            # no share index means the secret in clear, so it carries both shares
            if '.' in who:
                atoms = [who]
            else:
                atoms = [who + '.0', who + '.1']
            for atom in atoms:
                self.secret_of[atom] = atom.split('.')[0]
            for loc in self.locations(spec):
                self.labels[loc] = set(atoms)

        self.ignored = []
        for name in ann['ignore']:
            start = self.addr(name)
            self.ignored.append((start, self.routine_end(start)))
        self.waived = {}
        for name in ann['waive']:
            self.waived[self.addr(name)] = ann['waive'][name]

        self.x = list(self.sim.state.gprs.peek_unsigned_values())
        self.retired = 0
        self.mask_xor = None
        if mask_xor:
            self.mask_xor = MaskXor(self)

    # same setup as the standalone OTBN sim
    # TODO: pull into own runner component
    def start_sim(self):
        sim = self.sim
        st = sim.state
        entry = 0
        st.wsrs.set_sideload_keys(int('deadbeef' * 16, 16), int('baadf00d' * 16, 16))
        if self.ann['testcase']:
            text = open(os.path.join(REPO, self.ann['testcase'])).read()
            tc = OtbnTestCase.from_hjson(text, sim.symbols)
            sim.load_dmem_vars(tc.input.dmem)
            sim.load_regs_vars(tc.input.regs)
            entry = tc.entrypoint or 0
        st.ext_regs.commit()
        sim.start(False)
        st.pc = entry
        st.complete_init_sec_wipe()
        st.wfi_enabled = True
        st.wfi_auto_resume = True
        st.urnd_ctrl_enabled = True
        st.gprs.commit()
        st.wdrs.commit()
        self.rnd_count = 0
        self.urnd_count = 0

    def run(self, trace=False):
        while True:
            step = self.step()
            if step is None:
                return self
            if trace:
                self.trace(step)

    # run until 1 inst retires, None when program ends
    def step(self):
        st = self.sim.state
        while True:
            if st.ext_regs.read('RND_REQ', True):
                st.wsrs.RND.set_unsigned(RND_STREAM[self.rnd_count % len(RND_STREAM)], False, False)
                self.rnd_count += 1
            if st.wsrs.URND.requesting:
                st.wsrs.URND.set_seed(_TEST_URND_SEED[self.urnd_count % len(_TEST_URND_SEED)])
                self.urnd_count += 1
                st.wsrs.URND.reseed_done = True
            fsm = st.get_fsm_state()
            pc = st.pc
            insn, _ = self.sim.step(False)
            if fsm != FsmState.EXEC:
                if st.get_fsm_state() in [FsmState.IDLE, FsmState.LOCKED]:
                    return None
                continue
            if insn is not None:
                return self.retire(pc, insn)

    def retire(self, pc, insn):
        e = effects(insn, self.x)

        # written word get union of the labels it was computed from
        new = {}
        for loc, deps, tag in e.writes:
            if tag == 'const' or tag == 'fresh':
                new[loc] = set()
            else:
                new[loc] = union([self.label(d) for d in deps])
        for loc in new:
            for s in self.revealed(new[loc]):
                if not self.markers(new[loc], s):
                    new[loc] = new[loc] | {marker(pc, s)}
        new.pop('x0', None)

        hits = self.check(pc, insn.insn.mnemonic, e, new)
        step = Step(pc, e, new, hits)
        if self.mask_xor:
            self.mask_xor.judge(step, hits)
        for hit in hits:
            if hit.root not in self.findings:
                self.findings[hit.root] = Finding(hit.root[0], hit.root[1])
            self.findings[hit.root].add(hit, pc)

        # what instruction touched, needed for Rule 3 on the next
        self.prev = {}
        for loc in e.reads + e.used() + e.selector:
            self.prev[(loc, 'last_pre')] = self.label(loc)
        for loc in new:
            self.prev[(loc, 'last_new')] = new[loc]
        self.labels.update(new)
        if self.mask_xor:
            self.mask_xor.commit(step)

        self.x = list(self.sim.state.gprs.peek_unsigned_values())
        self.retired += 1
        return step

    def label(self, loc):
        return self.labels.get(loc, set())

    # secrets shares that all appear in label
    def revealed(self, label):
        count = {}
        for atom in label:
            if atom in self.secret_of:
                s = self.secret_of[atom]
                count[s] = count.get(s, 0) + 1
        out = set()
        for s in count:
            if count[s] >= 2:
                out.add(s)
        return out

    def markers(self, label, s): # flood
        out = set()
        for atom in label:
            if atom.startswith('@') and atom.endswith(':' + s):
                out.add(atom)
        return out

    # when: pre before this inst, new after it, last_* from the prev inst
    def get(self, part):
        loc, when = part
        if when == 'new':
            return self.now_new[loc]
        if when.startswith('last'):
            return self.prev[part]
        return self.label(loc)

    def add_hit(self, rule, s, root, later, parts):
        key = (rule, s, root)
        if key not in self.now_hits:
            self.now_hits[key] = Hit(rule, s, root, later)
        hit = self.now_hits[key]
        for p in parts:
            if p not in hit.parts:
                hit.parts.append(p)
        hit.ignored = self.now_ignored

    # shares meet in one comp: this is a new root cause here,
    # or maybe a later site of an earlier root if the label already carries its marker at this point?
    def check_value(self, rule, parts):
        labels = [self.get(p) for p in parts]
        for s in self.revealed(union(labels)):
            own = marker(self.now_pc, s)
            carried = set()
            for label in labels:
                if s in self.revealed(label):
                    carried = carried | self.markers(label, s)
            if len(carried) == 0 or own in carried:
                self.add_hit(rule, s, (self.now_pc, s), False, parts)
            for m in carried:
                if m != own:
                    root_pc = int(m[1:].split(':')[0])
                    self.add_hit(rule, s, (root_pc, s), True, parts)

    # 1 share replace the other in the same place, which leaks through the transition
    # TODO: try with some immutable ds again
    def check_transition(self, rule, before, after):
        a = union([self.get(p) for p in before])
        b = union([self.get(p) for p in after])
        for s in self.revealed(a | b):
            if s not in self.revealed(a) and s not in self.revealed(b):
                self.add_hit(rule, s, (self.now_pc, s), False, before + after)

    def check(self, pc, m, e, new):
        self.now_pc = pc
        self.now_new = new
        self.now_hits = {}
        self.now_ignored = False
        for lo, hi in self.ignored:
            if lo <= pc < hi:
                self.now_ignored = True

        # op of one inst
        rule = 'R2'
        if m == 'bn.sel':
            rule = 'R7'
        if m.startswith('bn.mulqacc'):
            rule = 'R8'
        self.check_value(rule, [(loc, 'pre') for loc in e.reads])

        # reg after write
        regs = []
        for loc in new:
            if not loc.startswith('fg') and register_of(loc) not in regs:
                regs.append(register_of(loc))
        for reg in regs:
            parts = []
            for loc in words_of(reg):
                if loc in new:
                    parts.append((loc, 'new'))
                else:
                    parts.append((loc, 'pre'))
            self.check_value('R4', parts)

        # overwrite a reg or flag
        for loc in new:
            if loc.startswith('fg'):
                self.check_transition('R9', [(loc, 'pre')], [(loc, 'new')])
            else:
                self.check_transition('R1', [(loc, 'pre')], [(loc, 'new')])

        # 2 inst in row
        now = []
        for loc in e.reads + e.used() + e.selector:
            now.append((loc, 'pre'))
        for loc in new:
            now.append((loc, 'new'))
        self.check_transition('R3', list(self.prev), now)

        # addresses, branches and loop counts should not depend on secret!
        for group in e.uses:
            self.check_value('CT', [(loc, 'pre') for loc in group])
        # bn.sel on a secret flag that overwrites 1 of its sources
        if e.sel_dst_is_src:
            self.check_value('R6', [(loc, 'pre') for loc in e.selector])

        return list(self.now_hits.values())

    def addr(self, name):
        sym, _, offset = name.partition('+')
        for a, n in self.routines:
            if n == sym:
                return a + int(offset or '0', 16)
        sys.exit(f'unknown symbol: {sym}')

    def routine_end(self, start):
        end = 4 * len(self.sim.program)
        for a, _ in self.routines:
            if start < a < end:
                end = a
        return end

    def site(self, pc):
        best = (0, '?')
        for a, n in self.routines:
            if a <= pc and a >= best[0]:
                best = (a, n)
        return f'{best[1]}+{pc - best[0]:#x}'

    def source(self, pc):
        if pc not in self.lines:
            return '?:?'
        file, line = self.lines[pc]
        return f'{os.path.basename(file)}:{line}'

    def disasm(self, pc):
        return ' '.join(self.sim.program[pc // 4].disassemble(pc).split())

    def locations(self, spec):
        if spec.startswith('dmem:'):
            _, sym, size = spec.split(':')
            return dmem(self.sim.symbols[sym], int(size) // 4)
        lo, _, hi = spec.partition('-')
        if is_wdr(lo) and is_wdr(hi):
            out = []
            for i in range(int(lo[1:]), int(hi[1:]) + 1):
                out = out + wdr(i)
            return out
        if is_wdr(spec):
            return wdr(int(spec[1:]))
        return [spec]

    # BUG: output turncated sometimes
    def trace(self, step):
        regs = {}
        for loc in step.new:
            reg = loc if loc.startswith('dmem') else loc.split('.')[0]
            if reg not in regs:
                regs[reg] = set()
            for atom in step.new[loc]:
                if not atom.startswith('@'):
                    regs[reg].add(atom)
        written = []
        for reg in regs:
            if regs[reg]:
                written.append(reg + '=' + ','.join(sorted(regs[reg])))
        rules = set()
        for hit in step.hits:
            rules.add(hit.rule + '(ok)' if hit.cleared else hit.rule)
        if written or rules:
            parts = [hex(step.pc), self.source(step.pc), self.disasm(step.pc)] + written + sorted(rules)
            print(' '.join(parts))

    def sort_key(self, finding):
        return (STATUS_ORDER.index(finding.status(self.waived)), finding.pc)

    def report(self):
        print(f'{os.path.basename(self.elf)}: {self.retired} instructions, {len(self.findings)} findings')
        found = sorted(self.findings.values(), key=self.sort_key)
        rows = [['status', 'secret', 'site', 'source', 'instruction', 'rules', 'later', 'reason']]
        for f in found:
            reason = self.waived.get(f.pc, '')
            if not reason and f.reasons:
                reason = min(f.reasons)
            rows.append([f.status(self.waived), f.secret, self.site(f.pc), self.source(f.pc),
                         self.disasm(f.pc), ' '.join(sorted(f.rules)) or '-', str(len(f.later_sites)), reason])
        if found:
            for r in rows:
                print(' | '.join(c or '-' for c in r))
        for kind in ['ignore', 'waive']:
            for name in self.ann[kind]:
                print(f'{kind} {name}: {self.ann[kind][name]}')

def text_symbols(path):
    out = set()
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        text_sections = []
        for i, section in enumerate(elf.iter_sections()):
            if section['sh_flags'] & 4:
                text_sections.append(i)
        for sym in elf.get_section_by_name('.symtab').iter_symbols():
            if sym['st_shndx'] in text_sections and sym.name and sym.name[0] not in '_$.':
                out.add((sym['st_value'], sym.name))
    return sorted(out)

def is_wdr(text):
    return text.startswith('w') and text[1:].isdigit()

# TODO: use regex for matching stuff instead
def remove_comments(code):
    while '/*' in code:
        start = code.index('/*')
        end = code.find('*/', start)
        if end == -1:
            break
        code = code[:start] + code[end + 2:]
    return code.split('#')[0]


# mnemonic of an assembly line, skipping a label like "loop:"
def first_word(code):
    code = remove_comments(code).strip()
    n = 0
    while n < len(code) and (code[n].isalnum() or code[n] in '_.$'):
        n += 1
    if n > 0 and code[n:n + 1] == ':':
        code = code[n + 1:].strip()
    out = ''
    for ch in code:
        if not (ch.isalnum() or ch in '_.'):
            break
        out += ch
    return out.lower()


def source_lines(path, program):
    rows = {}
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        if not elf.has_dwarf_info():
            return {}
        dwarf = elf.get_dwarf_info()
        for cu in dwarf.iter_CUs():
            lp = dwarf.line_program_for_CU(cu)
            dirs = [REPO]
            for d in lp['include_directory']:
                dirs.append(os.path.join(REPO, d.decode()))
            for entry in lp.get_entries():
                st = entry.state
                if st is None or st.end_sequence:
                    continue
                fe = lp['file_entry'][st.file - 1]
                file = os.path.join(dirs[fe.dir_index], fe.name.decode())
                if st.address not in rows:
                    rows[st.address] = []
                rows[st.address].append((file, st.line))

    # some instructions assembler puts the line row on the next instruction?
    # only keep line if its text really is this instruction!
    exact = set(find_insn_schemes(load_insns_yaml().mnemonic_to_insn))
    texts = {}
    out = {}
    for i in range(len(program)):
        insn = program[i]
        m = insn.insn.mnemonic
        if insn.insn.rv32i or m in exact:
            candidates = rows.get(4 * i, [])[-1:]
        else:
            candidates = rows.get(4 * i + 4, [])[:1]
        if not candidates:
            continue
        file, line = candidates[0]
        if file not in texts:
            texts[file] = []
            if os.path.exists(file):
                texts[file] = open(file).read().splitlines()
        code = ''
        if line <= len(texts[file]):
            code = texts[file][line - 1]

        word = first_word(code)
        if word == m or word.startswith(m + '.') or m in PSEUDO.get(word, []):
            out[4 * i] = (file, line)
    return out

def main():
    # TODO: add better help msgs
    p = argparse.ArgumentParser(description='IFT OTBN')
    p.add_argument('elf')
    p.add_argument('-a', dest='ann', help='default: ann/<elf name>.ann')
    p.add_argument('-s', dest='share', action='append', default=[], metavar='LOC=WHO')
    p.add_argument('--mask-xor', action='store_true')
    p.add_argument('--trace', action='store_true')
    args = p.parse_args()

    ann_path = args.ann
    if ann_path is None:
        name = os.path.splitext(os.path.basename(args.elf))[0]
        ann_path = os.path.join(HERE, 'ann', name + '.ann')
        if not os.path.exists(ann_path):
            ann_path = None
    ann = load_ann(ann_path, args.share)
    if not ann['shares']:
        print('warning: no shares annotated, nothing secret', file=sys.stderr)

    run = Run(args.elf, ann, mask_xor=args.mask_xor)
    run.run(trace=args.trace)
    run.report()
    for f in run.findings.values():
        if f.status(run.waived) in ['OPEN', 'MASK LOST']:
            sys.exit(1)


if __name__ == '__main__':
    main()
