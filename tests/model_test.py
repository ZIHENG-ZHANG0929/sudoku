"""参照模型对账测试：用 Python 独立实现游戏规则，和网页里的真实游戏在随机操作下逐步比对。

比对内容：内存状态、存档内容、屏幕上画出来的每个格子/按键/徽标。
用法：python3 model_test.py <html 路径> <轮数> <每轮步数> [起始种子]
环境变量 MODE=6 时测 6×6 大格模式（默认 9×9）。
"""
import asyncio, json, random, sys, copy, os
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright

HTML = __import__("os").path.abspath(sys.argv[1])
RUNS = int(sys.argv[2]); STEPS = int(sys.argv[3]); SEED0 = int(sys.argv[4]) if len(sys.argv) > 4 else 0
MODE = int(os.environ.get("MODE", "9"))
N, BR, BC = (9, 3, 3) if MODE == 9 else (6, 2, 3)
NN = N * N
P = json.load(open(ROOT + "/gen/puzzles.json" if MODE == 9 else ROOT + "/gen/puzzles6.json"))
LEVELS = len(P)
KEYP, PROGK, CURK = ("game.", "progress", "current") if MODE == 9 else ("game6.", "progress6", "current6")
HINTS = 3
from collections import Counter
COUNT = Counter()
ROW = lambda i: i // N; COL = lambda i: i % N; BOX = lambda i: (ROW(i) // BR) * (N // BC) + COL(i) // BC
PEERS = [[j for j in range(NN) if j != i and (ROW(j) == ROW(i) or COL(j) == COL(i) or BOX(j) == BOX(i))] for i in range(NN)]


class Model:
    """按规则说明独立实现，不照抄网页代码。"""
    def __init__(self, stars):
        self.settings = dict(showErrors=True, autoClean=True, highlightSame=True, showTimer=True)
        self.stars = dict(stars); self.saves = {}; self.current = None; self.G = None; self.sel = -1
        self.hsigs = {}   # 每关存档里记着“已经付过次数的提示”对应的盘面

    def max_cleared(self): return max([0] + list(self.stars))
    def unlocked(self, n): return n <= self.max_cleared() + 1

    def start(self, n):
        g = dict(n=n, given=[int(c) for c in P[n - 1]["p"]], sol=[int(c) for c in P[n - 1]["s"]],
                 history=[], noteMode=False, done=False)
        s = self.saves.get(n)
        if s: g.update(val=list(s["val"]), notes=list(s["notes"]), mistakes=s["mistakes"], hints=s["hints"], noteMode=s.get("noteMode", False))
        else: g.update(val=list(g["given"]), notes=[0] * NN, mistakes=0, hints=0)
        hs, paid = self.hsigs.get(n, (None, ())) if s else (None, ())
        g["hsig"], g["paid"] = hs, set(paid)
        self.G = g; self.sel = -1; self.current = n

    def persist(self):
        g = self.G
        if g and not g["done"]:
            self.saves[g["n"]] = dict(val=list(g["val"]), notes=list(g["notes"]), mistakes=g["mistakes"], hints=g["hints"], noteMode=g["noteMode"])
            self.hsigs[g["n"]] = (g["hsig"], tuple(g["paid"]))

    def correct(self, i): g = self.G; return g["val"][i] != 0 and g["val"][i] == g["sol"][i]
    def wrong(self, i): g = self.G; return g["val"][i] != 0 and not g["given"][i] and g["val"][i] != g["sol"][i]

    def push(self):
        g = self.G
        g["history"].append((list(g["val"]), list(g["notes"]), self.sel, g["mistakes"]))
        if len(g["history"]) > 300: g["history"].pop(0)

    def clean(self, i, d):
        if self.settings["autoClean"]:
            for p in PEERS[i]: self.G["notes"][p] &= ~(1 << (d - 1))

    def finish(self, check=True):
        g = self.G
        self.persist()
        if check and g["val"] == g["sol"]:
            g["done"] = True; COUNT["win"] += 1; COUNT["win_h%d" % g["hints"]] += 1
            self.saves.pop(g["n"], None); self.current = None
            st = 3 if g["hints"] == 0 else 2 if g["hints"] == 1 else 1
            self.stars[g["n"]] = max(self.stars.get(g["n"], 0), st)
            self.sel = -1

    def active(self): return self.G is not None and not self.G["done"]

    def select(self, i):
        if self.active(): self.sel = i

    def key(self, d):
        if not self.active() or self.sel < 0: return
        g, i = self.G, self.sel
        if g["given"][i]: return
        if g["noteMode"]:
            if g["val"][i]: return
            self.push(); g["notes"][i] ^= 1 << (d - 1)
        else:
            if g["val"][i] == d: return
            if self.settings["showErrors"] and self.correct(i): return
            self.push(); g["val"][i] = d; g["notes"][i] = 0
            if not (self.settings["showErrors"] and d != g["sol"][i]): self.clean(i, d)   # 标红的错数字不清理别的笔记
            if d != g["sol"][i] and self.settings["showErrors"]: g["mistakes"] += 1
        self.finish()

    def toggle_note(self):
        if self.G:
            self.G["noteMode"] = not self.G["noteMode"]
            if not self.G["done"]: self.persist()   # 笔记模式也存档

    def erase(self):
        if not self.active() or self.sel < 0: return
        g, i = self.G, self.sel
        if g["given"][i]: return
        if self.settings["showErrors"] and self.correct(i): return
        if not g["val"][i] and not g["notes"][i]: return
        self.push()
        if g["val"][i]: g["val"][i] = 0
        else: g["notes"][i] = 0
        self.finish()

    def undo(self):
        if not self.active() or not self.G["history"]: return
        v, nt, s, mk = self.G["history"].pop()
        self.G["val"], self.G["notes"], self.sel, self.G["mistakes"] = v, nt, s, mk   # 撤销也撤回错误次数
        self.finish(check=False)

    def hint_at(self, changed, js_notes=None):
        """讲解型提示：网页一路点“下一步”直到填入。这里检查它填的格子是否合规，再同步到模型。"""
        if not self.active():
            return None if not changed else f"hint changed cells while inactive {changed}"
        g = self.G
        # 有填错的格子（选中的优先，否则按顺序第一个）：提示先改正它
        wc = self.sel if self.sel >= 0 and self.wrong(self.sel) else next((i for i in range(NN) if self.wrong(i)), -1)
        sig = tuple(g["val"])
        if not changed:
            if g["hints"] >= HINTS: return None   # 次数用完（同一盘面换了一格讲也算新的提示）
            return "hint changed nothing"
        if len(changed) != 1: return f"hint should fill exactly one cell, changed {changed}"
        i = changed[0]; d = g["sol"][i]
        if wc >= 0 and i != wc: return f"hint ignored the wrong cell {wc}, filled {i}"
        if self.correct(i): return f"hint filled an already-correct cell {i}"
        # 讲（或改正）的还是上次付过次数的那一格那个数：不再扣（包括刷新前）
        free = (i, d) in g["paid"] or (not g["paid"] and wc < 0 and g["hsig"] == sig)   # 这一局付过的目标都免费
        if g["hints"] >= HINTS and not free: return f"hint filled {changed} with no hints left"
        self.push()
        if wc < 0: g["hsig"] = sig
        g["paid"].add((i, d))
        g["val"][i] = d; g["notes"][i] = 0; g["hints"] += 0 if free else 1; self.clean(i, d); self.sel = i
        # “填入”时讲解里划掉的候选数也从笔记里划掉：网页的笔记只能比模型少，而且不能划掉答案
        if js_notes is not None and wc < 0:
            for j in range(NN):
                if js_notes[j] & ~g["notes"][j]: return f"hint added notes at {j}"
                if g["notes"][j] & ~js_notes[j] & (1 << (g["sol"][j] - 1)): return f"hint struck the answer from notes at {j}"
            g["notes"] = list(js_notes)
        self.finish()
        return None

    def toggle(self, k): self.settings[k] = not self.settings[k]

    def home(self):
        if self.G: self.persist()
        self.current = None; self.G = None; self.sel = -1

    def reload(self):
        self.G = None; self.sel = -1
        c = self.current
        if c and self.unlocked(c): self.start(c)


STATE_JS = """() => {
  const ls = k => { const v = localStorage.getItem('sudoku.' + k); return v == null ? null : JSON.parse(v); };
  const saves = {}; for (let n = 1; n <= __LEVELS__; n++) { const s = ls('__KEYP__' + n); if (s) saves[n] = {val: s.val, notes: s.notes, mistakes: s.mistakes, hints: s.hints, noteMode: s.noteMode === true}; }
  const out = { stars: (ls('__PROGK__') || {stars: {}}).stars, saves, current: ls('__CURK__'), settings: ls('settings'),
    screen: $('game').classList.contains('on') ? 'game' : 'home', G: null };
  if (G) {
    out.G = { n: G.n, val: G.val, notes: G.notes, mistakes: G.mistakes, hints: G.hints, noteMode: G.noteMode, done: G.done,
              hist: G.history.length, sel: sel };
    out.dom = {
      v: cells.map(c => c.querySelector('.v').textContent),
      notes: cells.map(c => c.querySelector('.notes').style.display === 'none' ? '-' : [...c.querySelectorAll('.notes span')].map(s => s.textContent).join('')),
      cls: cells.map(c => ['given','user','wrong','sel'].map(k => c.classList.contains(k) ? 1 : 0).join('')),
      keys: [...pad.children].map(k => (k.classList.contains('done') ? 'D' : '') + (k.classList.contains('used') ? 'U' : '') + k.querySelector('small').textContent),
      badge: $('hintBadge').textContent, undoDis: $('tUndo').disabled, noteOn: $('tNote').classList.contains('on'),
      err: $('gErr').textContent,
    };
  }
  return out;
}"""


STATE_JS = STATE_JS.replace("__LEVELS__", str(LEVELS)).replace("__KEYP__", KEYP).replace("__PROGK__", PROGK).replace("__CURK__", CURK)


def expected_dom(m):
    g, s = m.G, m.settings
    v = [str(x) if x else "" for x in g["val"]]
    notes = ["-" if g["val"][i] else "".join(str(k + 1) for k in range(N) if g["notes"][i] >> k & 1) for i in range(NN)]
    cls = ["".join(map(str, [1 if g["given"][i] else 0, 1 if (not g["given"][i] and g["val"][i]) else 0,
                              1 if (s["showErrors"] and m.wrong(i)) else 0, 1 if i == m.sel else 0])) for i in range(NN)]
    cnt = [0] * 10
    for i in range(NN):
        if g["val"][i] and (not s["showErrors"] or not m.wrong(i)): cnt[g["val"][i]] += 1
    hide = s["showErrors"] and not g["noteMode"]   # 数到了：标出错误开着且不在笔记模式时藏起来，否则只变淡
    keys = [(("D" if hide else "U") if N - cnt[d] <= 0 else "") + (str(N - cnt[d]) if N - cnt[d] > 0 else "") for d in range(1, N + 1)]
    return dict(v=v, notes=notes, cls=cls, keys=keys, badge=str(HINTS - g["hints"]), undoDis=len(g["history"]) == 0,
                noteOn=g["noteMode"], err=f"错误 {g['mistakes']}" if s["showErrors"] else "")


def compare(m, js, where):
    errs = []
    want_stars = {str(k): v for k, v in m.stars.items()}
    if js["stars"] != want_stars: errs.append(f"stars {js['stars']} != {want_stars}")
    want_saves = {str(k): v for k, v in m.saves.items()}
    # 游戏还会每 5 秒和关闭页面时自动存档：多出来的存档只要等于该关当前（或初始）状态就算对
    for k, v in js["saves"].items():
        if k in want_saves: continue
        n = int(k)
        fresh = dict(val=[int(c) for c in P[n - 1]["p"]], notes=[0] * NN, mistakes=0, hints=0, noteMode=False)
        cur = (dict(val=m.G["val"], notes=m.G["notes"], mistakes=m.G["mistakes"], hints=m.G["hints"], noteMode=m.G["noteMode"])
               if m.G and m.G["n"] == n and not m.G["done"] else None)
        if v == fresh or v == cur:
            want_saves[k] = v; m.saves[n] = copy.deepcopy(v)
    # 什么都没做的对局（盘面、笔记、错误、提示都是初始状态，且还没计时）不留存档：模型不记时间，所以缺这种存档也算对
    for k in list(want_saves):
        n = int(k)
        fresh = dict(val=[int(c) for c in P[n - 1]["p"]], notes=[0] * NN, mistakes=0, hints=0)
        if k not in js["saves"] and {a: b for a, b in want_saves[k].items() if a != "noteMode"} == fresh:   # 只开了笔记模式也不留存档
            del want_saves[k]; m.saves.pop(n, None)
    if js["saves"] != want_saves:
        diff = set(js["saves"]) ^ set(want_saves) or [k for k in want_saves if js["saves"].get(k) != want_saves[k]]
        errs.append(f"saves differ at levels {sorted(diff)[:5]}")
    if js["current"] != m.current: errs.append(f"current {js['current']} != {m.current}")
    if (js["G"] is None) != (m.G is None): errs.append(f"G presence js={js['G'] is not None} model={m.G is not None}")
    elif m.G:
        g, jg = m.G, js["G"]
        for k in ("n", "val", "notes", "mistakes", "hints", "noteMode", "done"):
            if jg[k] != g[k]: errs.append(f"G.{k} differs")
        if jg["hist"] != len(g["history"]): errs.append(f"history {jg['hist']} != {len(g['history'])}")
        if jg["sel"] != m.sel: errs.append(f"sel {jg['sel']} != {m.sel}")
        if js["screen"] != "game": errs.append("screen not game")
        ed = expected_dom(m)
        for k, v in ed.items():
            if js["dom"][k] != v:
                if isinstance(v, list):
                    idx = [i for i in range(len(v)) if js["dom"][k][i] != v[i]][:3]
                    errs.append(f"dom.{k} differs at {idx}: js={[js['dom'][k][i] for i in idx]} want={[v[i] for i in idx]}")
                else: errs.append(f"dom.{k} js={js['dom'][k]!r} want={v!r}")
    else:
        if js["screen"] != "home": errs.append("screen not home")
    return [f"{where}: {e}" for e in errs]


async def run(pg, seed):
    rnd = random.Random(seed)
    k = rnd.choice([0, 0, 5, 19, 44, 69, 89, 99, 100] if MODE == 9 else [0, 0, 5, 11, 24, 37, 45, 49, 50])
    stars = {n: rnd.choice([1, 2, 3]) for n in range(1, k + 1)}
    await pg.evaluate("s => { G = null; clearInterval(timer); localStorage.clear(); localStorage.setItem('sudoku.__PROGK__', JSON.stringify({stars: s, best: {}})); localStorage.setItem('sudoku.homeMode', '__MODE__'); }".replace("__PROGK__", PROGK).replace("__MODE__", str(MODE)),
                      {str(n): v for n, v in stars.items()})
    await pg.reload(); await pg.wait_for_load_state()
    m = Model(stars)
    log = []
    finisher = rnd.random() < 0.6   # 六成的轮次会积极解题，确保经常走到通关
    for step in range(STEPS):
        if m.G is None or m.G["done"]:
            if m.G is not None:
                act = rnd.choice([("home",), ("winnext",), ("winhome",)])
            else:
                ul = [n for n in range(1, LEVELS + 1) if m.unlocked(n)]
                act = ("start", rnd.choice(ul[-3:] + [rnd.choice(ul)]))
        else:
            g = m.G
            r = rnd.random()
            if finisher and rnd.random() < 0.55 and g["noteMode"] is False:
                todo = [i for i in range(NN) if not m.correct(i)]
                act = ("solve1", rnd.choice(todo))
            elif r < 0.28:
                empties = [i for i in range(NN) if not m.correct(i)]
                act = ("sel", rnd.choice(empties) if empties and rnd.random() < 0.8 else rnd.randrange(NN))
            elif r < 0.62:
                d = g["sol"][m.sel] if m.sel >= 0 and rnd.random() < 0.6 else rnd.randint(1, N)
                act = ("key", d)
            elif r < 0.69: act = ("note",)
            elif r < 0.75: act = ("erase",)
            elif r < 0.82: act = ("undo",)
            elif r < 0.84: act = ("hint",)
            elif r < 0.88: act = ("toggle", rnd.choice(["showErrors", "autoClean", "highlightSame", "showTimer"]))
            elif r < 0.90: act = ("reload",)
            elif r < 0.92: act = ("home",)
            elif r < 0.925: act = ("pause",)
            elif r < 0.93: act = ("reset",)
            elif r < 0.935: act = ("restart",)
            elif r < 0.95: act = ("arrow", rnd.choice(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]))
            else: act = ("kbd", str(rnd.randint(0, 9)))
        log.append(act); COUNT[act[0]] += 1
        a = act[0]
        # ---- 在真实页面上执行（走真实的点击/按键事件） ----
        if a == "solve1":
            i = act[1]; d = m.G["sol"][i]
            await pg.evaluate(f"cells[{i}].dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true}})); pad.children[{d - 1}].click()")
            m.select(i); m.key(d)
        elif a == "sel":
            await pg.evaluate(f"cells[{act[1]}].dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true}}))")
            m.select(act[1])
        elif a == "key":
            await pg.evaluate(f"pad.children[{act[1] - 1}].click()"); m.key(act[1])
        elif a == "kbd":
            await pg.keyboard.press(act[1])
            if act[1] == "0": m.erase()
            elif int(act[1]) <= N: m.key(int(act[1]))   # 6×6 里按 7、8、9 不起作用
        elif a == "arrow":
            await pg.keyboard.press(act[1])
            if m.active() or m.G:
                s = m.sel
                if s < 0: m.sel = 0
                else:
                    r_, c_ = divmod(s, N)
                    m.sel = {"ArrowUp": ((r_ + N - 1) % N) * N + c_, "ArrowDown": ((r_ + 1) % N) * N + c_,
                             "ArrowLeft": r_ * N + (c_ + N - 1) % N, "ArrowRight": r_ * N + (c_ + 1) % N}[act[1]]
        elif a == "note": await pg.evaluate("$('tNote').click()"); m.toggle_note()
        elif a == "erase": await pg.evaluate("$('tErase').click()"); m.erase()
        elif a == "undo": await pg.evaluate("$('tUndo').click()"); m.undo()
        elif a == "hint":
            before = await pg.evaluate("G ? G.val.slice() : null")
            await pg.evaluate("$('tHint').click(); for (let k = 0; k < 80 && $('hpanel').classList.contains('on'); k++) $('hpNext').click();")
            after_ = await pg.evaluate("G ? G.val.slice() : null")
            jn = await pg.evaluate("G ? G.notes.slice() : null")
            changed = [i for i in range(NN) if before and after_ and before[i] != after_[i]]
            herr = m.hint_at(changed, jn)
            if herr: return [f"seed {seed} step {step} hint: {herr}"], log[-12:]
        elif a == "toggle":
            await pg.evaluate(f"document.querySelector('.switch[data-key={act[1]}]').click()"); m.toggle(act[1])
        elif a == "reload":
            await pg.reload(); await pg.wait_for_load_state(); m.reload()
        elif a == "home":
            await pg.evaluate("handleBack()"); m.home()
        elif a == "start":
            await pg.evaluate(f"document.querySelector('.lv[data-n=\"{act[1]}\"]').click()"); m.start(act[1])
        elif a in ("winnext", "winhome"):
            await pg.wait_for_timeout(420)
            await pg.evaluate(f"$('{'winNext' if a == 'winnext' else 'winHome'}').click()")
            n = m.G["n"]
            if a == "winnext" and n < LEVELS: m.start(n + 1)
            else: m.home()
        elif a == "restart":
            await pg.evaluate("$('openSettings2').click(); $('restartBtn').click(); $('cfYes').click()")
            n = m.G["n"]; m.saves.pop(n, None); m.start(n)
        elif a == "reset":
            await pg.evaluate("$('openSettings2').click(); $('resetBtn').click(); $('cfYes').click()")
            m.stars = {}; m.saves = {}; m.current = None; m.G = None; m.sel = -1
        elif a == "pause":
            await pg.evaluate("appPause(); appResume()")
        await pg.evaluate("typeof hideTip === 'function' && hideTip()")   # 新难度段提醒不影响状态，直接收起
        js = await pg.evaluate(STATE_JS)
        errs = compare(m, js, f"seed {seed} step {step} {act}")
        if errs:
            return errs, log[-12:]
    return [], None


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 393, "height": 852})
        page_errs = []
        pg.on("pageerror", lambda e: page_errs.append(str(e)))
        await pg.goto("file://" + HTML)
        total_fail = 0; steps = 0; wins = 0
        for r in range(RUNS):
            errs, tail = await run(pg, SEED0 + r)
            steps += STEPS
            if errs:
                total_fail += 1
                print("MISMATCH", errs[:4]); print("  last actions:", tail)
                if total_fail >= 3: break
        print(dict(COUNT))
        print(f"runs={RUNS} steps/run={STEPS} mismatching runs={total_fail} page errors={page_errs[:3]}")
        await b.close()

asyncio.run(main())
