"""数独题库生成器：生成 100 道唯一解题目，并按所需解题技巧分级、排序。

难度分段（关卡号）：
  1–20   入门  只需唯一候选数/宫内排除，提示数多
  21–45  简单  需要行列排除法，提示数较少
  46–70  中等  需要区块（pointing/claiming）或数对
  71–90  困难  需要三数组、X-Wing
  91–100 专家  需要 XY-Wing、XYZ-Wing、剑鱼、四数组
所有题目都能被下面的逻辑求解器不靠猜测解完。
"""
import json
import random
import sys
from itertools import combinations
from multiprocessing import Pool

ALL = 0x1FF
ROWS = [[r * 9 + c for c in range(9)] for r in range(9)]
COLS = [[r * 9 + c for r in range(9)] for c in range(9)]
BOXES = [[(br * 3 + r) * 9 + bc * 3 + c for r in range(3) for c in range(3)]
         for br in range(3) for bc in range(3)]
UNITS = ROWS + COLS + BOXES
PEERS = []
for i in range(81):
    r, c = divmod(i, 9)
    b = (r // 3) * 3 + c // 3
    PEERS.append(sorted(set(ROWS[r] + COLS[c] + BOXES[b]) - {i}))
ROW_OF = [i // 9 for i in range(81)]
COL_OF = [i % 9 for i in range(81)]
BOX_OF = [(i // 27) * 3 + (i % 9) // 3 for i in range(81)]
POPC = [bin(x).count("1") for x in range(512)]
BIT = [1 << d for d in range(9)]


def digits(mask):
    return [d for d in range(9) if mask & (1 << d)]


# ---------------- 回溯求解（数解的个数） ----------------
def count_solutions(grid, limit=2):
    g = list(grid)
    rows = [0] * 9; cols = [0] * 9; boxes = [0] * 9
    for i, v in enumerate(g):
        if v:
            m = 1 << (v - 1)
            rows[ROW_OF[i]] |= m; cols[COL_OF[i]] |= m; boxes[BOX_OF[i]] |= m
    empties = [i for i in range(81) if not g[i]]
    count = 0

    def rec():
        nonlocal count
        best = -1; best_mask = 0; best_n = 10
        for i in empties:
            if g[i]:
                continue
            m = ALL & ~(rows[ROW_OF[i]] | cols[COL_OF[i]] | boxes[BOX_OF[i]])
            n = POPC[m]
            if n < best_n:
                best, best_mask, best_n = i, m, n
                if n <= 1:
                    break
        if best == -1:
            count += 1
            return count >= limit
        if best_n == 0:
            return False
        r, c, b = ROW_OF[best], COL_OF[best], BOX_OF[best]
        m = best_mask
        while m:
            bit = m & -m
            m ^= bit
            g[best] = bit.bit_length()
            rows[r] |= bit; cols[c] |= bit; boxes[b] |= bit
            if rec():
                return True
            rows[r] ^= bit; cols[c] ^= bit; boxes[b] ^= bit
            g[best] = 0
        return False

    rec()
    return count


def random_full_grid(rng):
    g = [0] * 81
    rows = [0] * 9; cols = [0] * 9; boxes = [0] * 9

    def rec(i):
        if i == 81:
            return True
        r, c, b = ROW_OF[i], COL_OF[i], BOX_OF[i]
        ds = digits(ALL & ~(rows[r] | cols[c] | boxes[b]))
        rng.shuffle(ds)
        for d in ds:
            bit = 1 << d
            g[i] = d + 1
            rows[r] |= bit; cols[c] |= bit; boxes[b] |= bit
            if rec(i + 1):
                return True
            rows[r] ^= bit; cols[c] ^= bit; boxes[b] ^= bit
        g[i] = 0
        return False

    rec(0)
    return g


# ---------------- 逻辑求解器 ----------------
# 技巧 -> (等级, 分值)
TECH = {
    "naked_single": (1, 1), "hidden_single_box": (1, 1),
    "hidden_single_line": (2, 2),
    "pointing": (3, 6), "claiming": (3, 6), "naked_pair": (3, 8), "hidden_pair": (3, 10),
    "naked_triple": (4, 15), "hidden_triple": (4, 18), "x_wing": (4, 20),
    "xy_wing": (5, 30), "xyz_wing": (5, 35), "swordfish": (5, 35),
    "naked_quad": (5, 30), "hidden_quad": (5, 35),
}


class Solver:
    def __init__(self, grid):
        self.g = list(grid)
        self.cand = [0] * 81
        for i in range(81):
            if not self.g[i]:
                m = ALL
                for p in PEERS[i]:
                    if self.g[p]:
                        m &= ~BIT[self.g[p] - 1]
                self.cand[i] = m
        self.used = {}

    def place(self, i, d):
        self.g[i] = d + 1
        self.cand[i] = 0
        for p in PEERS[i]:
            self.cand[p] &= ~BIT[d]

    def elim(self, cells, mask):
        changed = False
        for i in cells:
            if not self.g[i] and self.cand[i] & mask:
                self.cand[i] &= ~mask
                changed = True
        return changed

    def mark(self, t):
        self.used[t] = self.used.get(t, 0) + 1
        return True

    # --- singles ---
    def naked_single(self):
        for i in range(81):
            if not self.g[i] and POPC[self.cand[i]] == 1:
                self.place(i, self.cand[i].bit_length() - 1)
                return self.mark("naked_single")
        return False

    def _hidden_single(self, units, name):
        for u in units:
            for d in range(9):
                spots = [i for i in u if not self.g[i] and self.cand[i] & BIT[d]]
                if len(spots) == 1:
                    self.place(spots[0], d)
                    return self.mark(name)
        return False

    def hidden_single_box(self):
        return self._hidden_single(BOXES, "hidden_single_box")

    def hidden_single_line(self):
        return self._hidden_single(ROWS + COLS, "hidden_single_line")

    # --- locked candidates ---
    def pointing(self):
        for b, box in enumerate(BOXES):
            for d in range(9):
                spots = [i for i in box if not self.g[i] and self.cand[i] & BIT[d]]
                if len(spots) < 2:
                    continue
                rs = {ROW_OF[i] for i in spots}
                cs = {COL_OF[i] for i in spots}
                if len(rs) == 1:
                    others = [i for i in ROWS[rs.pop()] if BOX_OF[i] != b]
                    if self.elim(others, BIT[d]):
                        return self.mark("pointing")
                if len(cs) == 1:
                    others = [i for i in COLS[cs.pop()] if BOX_OF[i] != b]
                    if self.elim(others, BIT[d]):
                        return self.mark("pointing")
        return False

    def claiming(self):
        for line in ROWS + COLS:
            for d in range(9):
                spots = [i for i in line if not self.g[i] and self.cand[i] & BIT[d]]
                if len(spots) < 2:
                    continue
                bs = {BOX_OF[i] for i in spots}
                if len(bs) == 1:
                    others = [i for i in BOXES[bs.pop()] if i not in line]
                    if self.elim(others, BIT[d]):
                        return self.mark("claiming")
        return False

    # --- naked / hidden subsets ---
    def _naked(self, n, name):
        for u in UNITS:
            empt = [i for i in u if not self.g[i]]
            pool = [i for i in empt if 2 <= POPC[self.cand[i]] <= n]
            for combo in combinations(pool, n):
                m = 0
                for i in combo:
                    m |= self.cand[i]
                if POPC[m] == n:
                    others = [i for i in empt if i not in combo]
                    if self.elim(others, m):
                        return self.mark(name)
        return False

    def _hidden(self, n, name):
        for u in UNITS:
            empt = [i for i in u if not self.g[i]]
            dpos = {}
            for d in range(9):
                spots = [i for i in empt if self.cand[i] & BIT[d]]
                if 2 <= len(spots) <= n:
                    dpos[d] = spots
            for combo in combinations(dpos.keys(), n):
                cells = set()
                for d in combo:
                    cells.update(dpos[d])
                if len(cells) == n:
                    keep = 0
                    for d in combo:
                        keep |= BIT[d]
                    changed = False
                    for i in cells:
                        if self.cand[i] & ~keep:
                            self.cand[i] &= keep
                            changed = True
                    if changed:
                        return self.mark(name)
        return False

    def naked_pair(self): return self._naked(2, "naked_pair")
    def hidden_pair(self): return self._hidden(2, "hidden_pair")
    def naked_triple(self): return self._naked(3, "naked_triple")
    def hidden_triple(self): return self._hidden(3, "hidden_triple")
    def naked_quad(self): return self._naked(4, "naked_quad")
    def hidden_quad(self): return self._hidden(4, "hidden_quad")

    # --- fish ---
    def _fish(self, n, name):
        for d in range(9):
            for base, cover, base_of, cover_of in ((ROWS, COLS, ROW_OF, COL_OF),
                                                   (COLS, ROWS, COL_OF, ROW_OF)):
                lines = {}
                for li, line in enumerate(base):
                    pos = {cover_of[i] for i in line if not self.g[i] and self.cand[i] & BIT[d]}
                    if 2 <= len(pos) <= n:
                        lines[li] = pos
                for combo in combinations(lines.keys(), n):
                    cov = set()
                    for li in combo:
                        cov |= lines[li]
                    if len(cov) == n:
                        targets = [i for ci in cov for i in cover[ci] if base_of[i] not in combo]
                        if self.elim(targets, BIT[d]):
                            return self.mark(name)
        return False

    def x_wing(self): return self._fish(2, "x_wing")
    def swordfish(self): return self._fish(3, "swordfish")

    # --- wings ---
    def xy_wing(self):
        bivals = [i for i in range(81) if not self.g[i] and POPC[self.cand[i]] == 2]
        biset = set(bivals)
        for p in bivals:
            pm = self.cand[p]
            wings = [q for q in PEERS[p] if q in biset and POPC[pm & self.cand[q]] == 1]
            for a, b in combinations(wings, 2):
                am, bm = self.cand[a], self.cand[b]
                if (am & pm) == (bm & pm):
                    continue
                z = am & ~pm
                if POPC[z] != 1 or (bm & ~pm) != z:
                    continue
                common = set(PEERS[a]) & set(PEERS[b])
                common.discard(p)
                if self.elim(common, z):
                    return self.mark("xy_wing")
        return False

    def xyz_wing(self):
        for p in range(81):
            if self.g[p] or POPC[self.cand[p]] != 3:
                continue
            pm = self.cand[p]
            wings = [q for q in PEERS[p] if not self.g[q] and POPC[self.cand[q]] == 2
                     and (self.cand[q] & ~pm) == 0]
            for a, b in combinations(wings, 2):
                am, bm = self.cand[a], self.cand[b]
                if am == bm or (am | bm) != pm:
                    continue
                z = am & bm
                if POPC[z] != 1:
                    continue
                common = set(PEERS[a]) & set(PEERS[b]) & set(PEERS[p])
                if self.elim(common, z):
                    return self.mark("xyz_wing")
        return False

    ORDER = ["naked_single", "hidden_single_box", "hidden_single_line",
             "pointing", "claiming", "naked_pair", "hidden_pair",
             "naked_triple", "hidden_triple", "x_wing",
             "xy_wing", "xyz_wing", "swordfish", "naked_quad", "hidden_quad"]

    def solve(self, max_level=5):
        steps = [getattr(self, t) for t in self.ORDER if TECH[t][0] <= max_level]
        while 0 in self.g:
            for s in steps:
                if s():
                    break
            else:
                return False
        return True


def rate(grid, max_level=5):
    s = Solver(grid)
    ok = s.solve(max_level)
    if not ok:
        return None
    level = max(TECH[t][0] for t in s.used)
    score = sum(TECH[t][1] * n for t, n in s.used.items())
    return level, score, s.used


def singles_level(grid):
    """入门题：只用唯一候选数 + 宫内排除能解出返回 1；需要行列排除返回 2。"""
    s = Solver(grid)
    if s.solve(1):
        return 1
    s = Solver(grid)
    if s.solve(2):
        return 2
    return None


# ---------------- 挖洞 ----------------
def make_puzzle(seed, min_givens=17, symmetric=True):
    rng = random.Random(seed)
    sol = random_full_grid(rng)
    g = list(sol)
    cells = list(range(81))
    rng.shuffle(cells)
    seen = set()
    for i in cells:
        if i in seen:
            continue
        pair = {i, 80 - i} if symmetric else {i}
        seen |= pair
        if sum(1 for v in g if v) - len([p for p in pair if g[p]]) < min_givens:
            continue
        saved = {p: g[p] for p in pair}
        for p in pair:
            g[p] = 0
        if count_solutions(g) != 1:
            for p, v in saved.items():
                g[p] = v
    return g, sol


def worker(seed):
    # 不同的提示数下限，让入门/简单题不会挖得太空
    rng = random.Random(seed * 7 + 1)
    kind = seed % 10
    if kind < 2:
        target = rng.randint(40, 45)
    elif kind < 4:
        target = rng.randint(31, 36)
    else:
        target = 17
    g, sol = make_puzzle(seed, min_givens=target, symmetric=(kind < 4 or seed % 3 != 0))
    givens = sum(1 for v in g if v)
    r = rate(g)
    if r is None:
        return None
    level, score, used = r
    if level <= 2:
        level = singles_level(g)
    return {"seed": seed, "puzzle": "".join(map(str, g)), "solution": "".join(map(str, sol)),
            "givens": givens, "level": level, "score": score, "used": used}


def main():
    want = {1: 20, 2: 25, 3: 25, 4: 20, 5: 10}
    buckets = {k: [] for k in want}
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    batch = 200
    seed = start
    with Pool() as pool:
        while any(len(buckets[k]) < want[k] * 2 for k in want):
            res = pool.map(worker, range(seed, seed + batch))
            seed += batch
            for r in res:
                if not r:
                    continue
                lv = r["level"]
                # 入门题要提示数多，简单题提示数不能太多
                if lv == 1 and r["givens"] < 38:
                    continue
                if lv == 2 and not (28 <= r["givens"] <= 36):
                    continue
                if lv >= 3 and r["givens"] > 30:
                    continue
                if len(buckets[lv]) < want[lv] * 2:
                    buckets[lv].append(r)
            print("seed", seed, {k: len(v) for k, v in buckets.items()}, flush=True)

    levels = []
    for lv in sorted(want):
        pool_ = buckets[lv]
        # 从候选中均匀挑选，然后在段内按难度分（入门/简单按提示数降序）排序
        if lv <= 2:
            pool_.sort(key=lambda r: (-r["givens"], r["score"]))
        else:
            pool_.sort(key=lambda r: r["score"])
        n = want[lv]
        step = len(pool_) / n
        picked = [pool_[int(k * step)] for k in range(n)]
        levels.extend(picked)

    out = [{"p": r["puzzle"], "s": r["solution"], "tier": r["level"]} for r in levels]
    with open("puzzles.json", "w") as f:
        json.dump(out, f)
    with open("puzzles_report.json", "w") as f:
        json.dump([{"level": k + 1, "tier": r["level"], "givens": r["givens"],
                    "score": r["score"], "used": r["used"]} for k, r in enumerate(levels)],
                  f, ensure_ascii=False, indent=1)
    print("done", len(out))


if __name__ == "__main__":
    main()
