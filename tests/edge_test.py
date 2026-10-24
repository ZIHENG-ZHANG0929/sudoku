"""边界情况：撤销上限、各种损坏的存档、页面加载时就带着坏数据。"""
import asyncio, json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
P = json.load(open(ROOT + "/gen/puzzles.json"))
fails = []
def check(c, m):
    if not c: fails.append(m)

BAD = [
    ("progress 不是 JSON", {"progress": "{oops"}),
    ("progress 是数组", {"progress": "[1,2,3]"}),
    ("progress 缺 best", {"progress": json.dumps({"stars": {"1": 3, "2": 2}})}),
    ("stars 里有怪值", {"progress": json.dumps({"stars": {"1": 3, "2": "x", "3": 9, "abc": 1, "150": 3}, "best": {"1": -5}})}),
    ("progress 是 null", {"progress": "null"}),
    ("settings 损坏", {"settings": json.dumps({"showErrors": "yes", "autoClean": None})}),
    ("game 存档 val 长度不对", {"progress": json.dumps({"stars": {}, "best": {}}), "game.1": json.dumps({"val": [1, 2], "notes": [], "mistakes": 0, "hints": 0, "time": 0}), "current": "1"}),
    ("game 存档改了题目数字", {"game.1": json.dumps({"val": [9] * 81, "notes": [0] * 81, "mistakes": 0, "hints": 0, "time": 0}), "current": "1"}),
    ("game 存档 hints 是字符串", {"game.1": json.dumps({"val": [int(c) for c in P[0]["p"]], "notes": [0] * 81, "mistakes": "a", "hints": "b", "time": None}), "current": "1"}),
    ("game 存档 notes 越界", {"game.1": json.dumps({"val": [int(c) for c in P[0]["p"]], "notes": [9999] * 81, "mistakes": 0, "hints": 0, "time": 0}), "current": "1"}),
    ("current 是怪值", {"current": json.dumps("abc")}),
    ("current 指向未解锁关卡", {"current": "57"}),
    ("current 是小数", {"current": "1.5"}),
]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 393, "height": 852})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(HTML)

        # ---- 撤销上限 300 步 ----
        await pg.evaluate("G=null; clearInterval(timer); localStorage.clear()"); await pg.reload()
        await pg.evaluate("startLevel(1); const i = G.val.indexOf(0); cells[i].dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); $('tNote').click()")
        await pg.evaluate("for (let k = 0; k < 350; k++) pad.children[k % 9].click()")
        h = await pg.evaluate("G.history.length")
        check(h == 300, f"history cap {h}")
        await pg.evaluate("for (let k = 0; k < 400; k++) $('tUndo').click()")
        # 撤销到底：应该回到第 50 步之后的状态（前 50 步已被丢弃）
        want = 0
        for k in range(50): want ^= 1 << (k % 9)
        got = await pg.evaluate("G.notes[G.val.indexOf(0)]")
        check(got == want and await pg.evaluate("$('tUndo').disabled"), f"undo floor notes {got} want {want}")

        # ---- 各种损坏数据下启动 ----
        for name, data in BAD:
            errs.clear()
            await pg.evaluate("G=null; clearInterval(timer); localStorage.clear()")
            await pg.evaluate("d => { for (const k in d) localStorage.setItem('sudoku.' + k, d[k]); }", data)
            await pg.reload(); await pg.wait_for_load_state()
            ok = await pg.evaluate("""() => {
              const scr = $('game').classList.contains('on') ? 'game' : 'home';
              const lv = document.querySelectorAll('.lv').length;
              let gOk = true;
              if (G) gOk = G.val.length === 81 && G.val.every((v, i) => v >= 0 && v <= 9 && (!G.given[i] || v === G.given[i]))
                   && G.notes.every(m => m >= 0 && m <= 511) && Number.isInteger(G.hints) && Number.isInteger(G.mistakes) && Number.isInteger(G.time);
              return [scr, lv, gOk, $('continueText').textContent];
            }""")
            check(not errs and ok[1] == 100 and ok[2], f"corrupt '{name}': errors={errs[:1]} state={ok}")
            # 能正常开始并玩一步
            await pg.evaluate("goHome(); $('continueBtn').click()")
            await pg.evaluate("const i = G.val.indexOf(0); cells[i].dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); pad.children[+PUZZLES[G.n-1].s[i]-1].click()")
            check(not errs, f"corrupt '{name}': play errors {errs[:1]}")
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
