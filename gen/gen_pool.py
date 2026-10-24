"""生成练习题素材：一批新的唯一解题目（和 100 关不重复）。"""
import json, random, sys
from multiprocessing import Pool
import generate as G

def work(seed):
    rng = random.Random(seed)
    k = seed % 10
    mg = rng.randint(36, 46) if k < 2 else (rng.randint(28, 34) if k < 3 else 17)
    g, sol = G.make_puzzle(seed, min_givens=mg, symmetric=(seed % 2 == 0))
    return {"p": "".join(map(str, g)), "s": "".join(map(str, sol))}

if __name__ == "__main__":
    n = int(sys.argv[1]); start = int(sys.argv[2]) if len(sys.argv) > 2 else 500000
    with Pool() as pool:
        out = pool.map(work, range(start, start + n), chunksize=50)
    levels = {x["p"] for x in json.load(open("puzzles.json"))}
    out = [x for x in out if x["p"] not in levels]
    try: old = json.load(open("pool.json"))
    except Exception: old = []
    seen = {x["p"] for x in old}
    out = old + [x for x in out if x["p"] not in seen]
    json.dump(out, open("pool.json", "w"))
    print(len(out))
