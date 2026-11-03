# Tracks word as exact XOR, example of what a extension that uses sockets

# TODO: verify math
# NOTE: double check before push!

# Tracks values as XORs of atoms: S:s:i (secret word), U:s (mask), rN (random).
# Clears hit iff no XOR of its parts reveals a secret word (privacy, not NI).
# Assumes 2-share Boolean masking, XOR only ops.

# Linear 2-share case of https://eprint.iacr.org/2016/211.pdf, Thm 3.1 / Lemma 3.4.
# relies on https://eprint.iacr.org/2019/1165.pdf, Sec. 2.2, Condition 9, p.8?
class MaskXor:

    # S:s:i (word i of secret s)
    # U:s (share mask)
    # rN (fresh randomness)
    # None = unknown

    def __init__(self, run):
        self.form = {}
        self.prev = {}
        self.staged = {}
        self.fresh = 0
        # hit counts for the summary
        self.cleared = 0
        self.unmasked = 0
        self.unknown = 0
        self.skipped = 0
        self.boolean = run.ann['boolean']
        # keep counting words if share split over lines
        seen = {}
        for spec, who in run.ann['shares']:
            s, _, j = who.partition('.')
            locs = run.locations(spec)
            first = seen.get(who, 0)
            seen[who] = first + len(locs)
            for i in range(len(locs)):
                if s not in self.boolean or j == '':
                    self.form[locs[i]] = None
                # share 1 is mask, share 0 is secret XOR mask
                elif j == '1':
                    self.form[locs[i]] = {f'U:{s}'}
                else:
                    self.form[locs[i]] = {f'S:{s}:{first + i}', f'U:{s}'}

    def transfer(self, deps, tag):
        if tag == 'const':
            return set()
        if tag == 'fresh':
            self.fresh += 1
            return {f'r{self.fresh}'}
        if tag != 'copy' and tag != 'xor':
            return None
        out = set()
        for d in deps:
            f = self.form.get(d, set())
            if f is None:
                return None
            out = out ^ f
        return out

    def judge(self, step, hits):
        self.staged = {}
        for loc, deps, tag in step.effects.writes:
            self.staged[loc] = self.transfer(deps, tag)

        for hit in hits:
            if hit.secret not in self.boolean:
                self.skipped += 1
                continue
            rows = []
            for loc, when in hit.parts:
                if when == 'new':
                    rows.append(self.staged[loc])
                elif when.startswith('last'):
                    rows.append(self.prev.get((loc, when)))
                else:
                    rows.append(self.form.get(loc, set()))
            # None: a part went through a non xor op
            if None in rows:
                self.unknown += 1
                continue
            if not masked(rows, hit.secret):
                self.unmasked += 1
                continue
            self.cleared += 1
            masks = set()
            for row in rows:
                for v in row:
                    if v[0] == 'r' or v[0] == 'U':
                        masks.add(v)
            masks = sorted(masks)
            reason = 'mask-xor: masked by ' + ' '.join(masks[:3])
            if len(masks) > 3:
                reason += ' ...'
            hit.cleared = reason

    def commit(self, step):
        e = step.effects
        self.prev = {}
        for loc in e.reads + e.used() + e.selector:
            self.prev[(loc, 'last_pre')] = self.form.get(loc, set())
        for loc in self.staged:
            self.prev[(loc, 'last_new')] = self.staged[loc]
        self.form.update(self.staged)

    def summary(self, run):
        judged = self.cleared + self.unmasked + self.unknown
        out = f'mask-xor: cleared {self.cleared}/{judged} hits'
        if judged:
            out += f' ({self.unmasked} unmasked, {self.unknown} non xor op)'
        if self.skipped:
            out += f', {self.skipped} skipped'
        status = [f.status(run.waived) for f in run.findings.values()]
        out += (f', root causes: {status.count("CLEARED")} cleared, '
                f'{status.count("MASK LOST")} mask lost, of {len(status)}')
        return out

    # unknown again
    def forget(self, locs):
        for loc in locs:
            self.form[loc] = None

# GF(2) reduction
def reduce(basis, c):
    while c != 0 and c.bit_length() in basis:
        c = c ^ basis[c.bit_length()]
    return c

# true if no XOR cancells all r/u but keeps a s
# no S col outside span of r/U
def masked(rows, s):
    columns = {}
    for i in range(len(rows)):
        for v in rows[i]:
            columns[v] = columns.get(v, 0) | (1 << i)

    basis = {}
    for v in columns:
        if v[0] == 'r' or v[0] == 'U':
            c = reduce(basis, columns[v])
            if c != 0:
                basis[c.bit_length()] = c

    for v in columns:
        if v.startswith(f'S:{s}:'):
            if reduce(basis, columns[v]) != 0:
                return False
    return True
