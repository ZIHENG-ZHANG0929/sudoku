"""用最早那个独立的 Python 解题器核对教学数据：盘面合法、候选数没漏掉正确答案、整题唯一解。
输出每个练习盘面的答案，给 lessons_test.js 做排除是否正确的检查。"""
import json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
sys.path.insert(0, ROOT + "/gen")
import generate as G
L = json.load(open(ROOT + "/gen/lessons.json"))
bad = []; sols = {}
def dec(c): return [int(c[i*2:i*2+2], 36) for i in range(81)]
for k, les in enumerate(L):
    for name, D in [("demo", les["demo"])] + [(f"drill{j}", d) for j, d in enumerate(les["drills"])]:
        p = [int(x) for x in D["p"]]; v = [int(x) for x in D["v"]]; c = dec(D["c"])
        if G.count_solutions(p, 2) != 1: bad.append(f"{les['id']} {name}: puzzle not unique"); continue
        s = G.Solver(p); logic_ok = s.solve()
        # 也用回溯独立求一次解，两者必须一致
        g2 = list(p)
        def bt():
            try: i = g2.index(0)
            except ValueError: return True
            for d in range(1, 10):
                if all(g2[q] != d for q in G.PEERS[i]):
                    g2[i] = d
                    if bt(): return True
            g2[i] = 0; return False
        bt(); sol = g2
        if logic_ok and s.g != sol: bad.append(f"{les['id']} {name}: solvers disagree")
        for i in range(81):
            if p[i] and v[i] != p[i]: bad.append(f"{les['id']} {name}: given changed at {i}")
            if v[i] and v[i] != sol[i]: bad.append(f"{les['id']} {name}: wrong value at {i}")
            if not v[i]:
                if not (c[i] >> (sol[i] - 1)) & 1: bad.append(f"{les['id']} {name}: candidate lost solution at {i}")
                basic = 511
                for q in G.PEERS[i]:
                    if v[q]: basic &= ~(1 << (v[q] - 1))
                if c[i] & ~basic: bad.append(f"{les['id']} {name}: candidate not allowed at {i}")
            elif c[i]: bad.append(f"{les['id']} {name}: filled cell has candidates {i}")
        sols[f"{k}:{name}"] = "".join(map(str, sol))
    for j, F in enumerate(les["full"]):
        p = [int(x) for x in F["p"]]
        if G.count_solutions(p, 2) != 1: bad.append(f"{les['id']} full{j}: not unique")
        s = G.Solver(p); s.solve()
        if "".join(map(str, s.g)) != F["s"]: bad.append(f"{les['id']} full{j}: solution mismatch")
json.dump(sols, open(sys.argv[1], "w"))
print("states checked", len(sols), "full puzzles", sum(len(l["full"]) for l in L))
print("FAILS:", bad[:10] if bad else "none")
