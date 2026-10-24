"""关卡小块上的最快用时：通关后显示、重玩只保留更快的、关掉“显示计时”后隐藏。"""
import asyncio, json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
P = json.load(open(ROOT + "/gen/puzzles.json"))
fails = []
def check(c, m):
    if not c: fails.append(m)
SOLVE = """(sol) => { for (let i = 0; i < 81; i++) { if (G.val[i] === +sol[i]) continue;
    cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); pad.children[+sol[i]-1].click(); } }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 393, "height": 852})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(HTML); await pg.evaluate("localStorage.clear()"); await pg.reload()
        tile = lambda n: pg.evaluate(f"document.querySelector('.lv[data-n=\"{n}\"] .bt').textContent")
        check(await tile(1) == "" and await tile(2) == "", "uncleared tiles should show no time")
        # 通关第 1 关，用时 83 秒 → 显示 1:23
        await pg.evaluate("startLevel(1); G.started = true; G.time = 83"); await pg.evaluate(SOLVE, P[0]["s"])
        await pg.wait_for_timeout(450); await pg.evaluate("closeSheet('winSheet'); goHome()")
        check(await tile(1) == "1:23", f"tile after win: {await tile(1)!r}")
        # 重玩更慢：保留 1:23；重玩更快：更新
        await pg.evaluate("startLevel(1); G.started = true; G.time = 200"); await pg.evaluate(SOLVE, P[0]["s"])
        await pg.wait_for_timeout(450); await pg.evaluate("closeSheet('winSheet'); goHome()")
        check(await tile(1) == "1:23", f"slower replay changed tile: {await tile(1)!r}")
        await pg.evaluate("startLevel(1); G.started = true; G.time = 59"); await pg.evaluate(SOLVE, P[0]["s"])
        await pg.wait_for_timeout(450); await pg.evaluate("closeSheet('winSheet'); goHome()")
        check(await tile(1) == "0:59", f"faster replay: {await tile(1)!r}")
        # 关掉“显示计时”：小块上也不显示；打开后恢复
        await pg.evaluate("$('openSettings').click(); document.querySelector('.switch[data-key=showTimer]').click()")
        check(await tile(1) == "", "time still shown with timer display off")
        await pg.evaluate("document.querySelector('.switch[data-key=showTimer]').click(); $('setClose').click()")
        check(await tile(1) == "0:59", "time not restored after turning timer display back on")
        # 刷新后仍在；长时间格式
        await pg.evaluate("progress.best[1] = 3725; store.set('progress', progress)"); await pg.reload()
        check(await tile(1) == "62:05", f"long time format: {await tile(1)!r}")
        # 小块没有被撑大：仍是正方形，一行 5 个
        sq = await pg.evaluate("() => { const r = document.querySelector('.lv').getBoundingClientRect(); return Math.abs(r.width - r.height) <= 1 && document.querySelectorAll('.levels')[0].children.length === 20; }")
        check(sq, "tile no longer square")
        check(not errs, f"page errors {errs[:2]}")
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
