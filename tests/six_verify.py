"""用独立的回溯解题器核对 6×6 题库：每道题恰好一个解，答案符合 6×6 规则（宫是 2 行 × 3 列），提示数逐段减少。"""
import json
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
P = json.load(open(ROOT + "/gen/puzzles6.json"))
N, BR, BC = 6, 2, 3
def peers(i):
    r, c = divmod(i, N); b = (r // BR, c // BC)
    return [j for j in range(N * N) if j != i and (j // N == r or j % N == c or (j // N // BR, j % N // BC) == b)]
PE = [peers(i) for i in range(36)]
def solutions(g, limit=2):
    g = list(g); out = []
    def rec():
        try: i = g.index(0)
        except ValueError: out.append(list(g)); return len(out) >= limit
        for d in range(1, 7):
            if all(g[q] != d for q in PE[i]):
                g[i] = d
                if rec(): return True
        g[i] = 0; return False
    rec(); return out
bad = []
for k, x in enumerate(P):
    p = [int(c) for c in x["p"]]; s = [int(c) for c in x["s"]]
    sols = solutions(p)
    if len(sols) != 1: bad.append(f"level {k+1}: {len(sols)} solutions")
    elif sols[0] != s: bad.append(f"level {k+1}: stored solution wrong")
    for i in range(36):
        if any(s[q] == s[i] for q in PE[i]): bad.append(f"level {k+1}: solution breaks rules"); break
        if p[i] and p[i] != s[i]: bad.append(f"level {k+1}: given mismatch"); break
giv = [sum(1 for c in x["p"] if c != "0") for x in P]
if any(giv[i] < giv[i + 1] for i in range(len(giv) - 1)): bad.append(f"givens not non-increasing: {giv}")
print("6x6 levels", len(P), "distinct", len(set(x["p"] for x in P)), "givens", giv[0], "->", giv[-1])
print("FAILS:", bad[:5] if bad else "none")
