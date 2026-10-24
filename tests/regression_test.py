import asyncio, json, random
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright
import sys
URL = "file://" + __import__("os").path.abspath(sys.argv[1])
P = json.load(open(ROOT + "/gen/puzzles.json"))
fails = []
def check(cond, msg):
    if not cond: fails.append(msg)

INVARIANT = """() => {
  if (!G) return null;
  const bad = [];
  for (let i = 0; i < 81; i++) {
    if (G.given[i] && G.val[i] !== G.given[i]) bad.push('given changed ' + i);
    if (!(G.val[i] >= 0 && G.val[i] <= 9)) bad.push('val ' + i);
    if (!(G.notes[i] >= 0 && G.notes[i] <= 511)) bad.push('notes ' + i);
    if (G.val[i] && G.notes[i] && G.val[i]) {} 
  }
  if (G.hints > 3 || G.hints < 0) bad.push('hints');
  if (document.querySelector('.cell .v').textContent === undefined) bad.push('dom');
  return bad;
}"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 393, "height": 852})
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(URL)

        # ---- T1：从第 1 关一路通关到 100 关（用真实点击事件） ----
        for n in range(1, 101):
            await pg.evaluate("document.getElementById('continueBtn').click()")
            cur = await pg.evaluate("G && G.n")
            check(cur == n, f"T1 continue opened {cur} expected {n}")
            await pg.evaluate("""(sol) => {
              for (let i = 0; i < 81; i++) {
                if (G.val[i]) continue;
                cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));
                pad.children[+sol[i] - 1].click();
              }
            }""", P[n - 1]["s"])
            st = await pg.evaluate("[G.done, progress.stars[%d], localStorage.getItem('sudoku.game.%d'), localStorage.getItem('sudoku.current')]" % (n, n))
            check(st[0] is True and st[1] == 3 and st[2] is None and st[3] is None, f"T1 level {n} state {st}")
            await pg.wait_for_timeout(5)
            await pg.evaluate("closeSheet('winSheet'); goHome()")
        txt = await pg.text_content("#continueText")
        check(txt == "已全部通关", f"T1 final label {txt}")
        check(await pg.evaluate("document.querySelectorAll('.lv.locked').length") == 0, "T1 locked remain")

        # ---- T2：随机乱点 ----
        random.seed(1)
        await pg.evaluate("localStorage.clear()")
        await pg.reload(); await pg.wait_for_load_state()
        for n in (1, 30, 60, 85, 100):
            await pg.evaluate(f"progress.stars = {{}}; for (let k=1;k<{n};k++) progress.stars[k]=1; startLevel({n})")
            for step in range(600):
                a = random.random()
                if a < 0.35:
                    await pg.evaluate(f"cells[{random.randrange(81)}].dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true}}))")
                elif a < 0.75:
                    await pg.evaluate(f"pad.children[{random.randrange(9)}].click()")
                elif a < 0.82: await pg.evaluate("$('tNote').click()")
                elif a < 0.88: await pg.evaluate("$('tErase').click()")
                elif a < 0.95: await pg.evaluate("$('tUndo').click()")
                elif a < 0.97: await pg.evaluate("$('tHint').click()")
                else:
                    k = random.choice(["showErrors", "autoClean", "highlightSame", "showTimer"])
                    await pg.evaluate(f"document.querySelector('.switch[data-key={k}]').click()")
                bad = await pg.evaluate(INVARIANT)
                if bad:
                    check(False, f"T2 level {n} step {step}: {bad[:3]}"); break
                if await pg.evaluate("G.done"):
                    break
            # 存档与内存一致
            saved = await pg.evaluate(f"JSON.parse(localStorage.getItem('sudoku.game.{n}'))")
            if saved:
                same = await pg.evaluate("s => JSON.stringify(s.val)===JSON.stringify(G.val) && JSON.stringify(s.notes)===JSON.stringify(G.notes)", saved)
                check(same, f"T2 level {n} save mismatch")

        # ---- T3：对局中刷新页面（模拟被系统回收），应回到对局且盘面一致 ----
        await pg.evaluate("localStorage.clear(); progress={stars:{},best:{}}; store.set('progress',progress); startLevel(1)")
        await pg.evaluate("""() => { const i = G.val.indexOf(0); cells[i].dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); $('tNote').click(); pad.children[4].click(); pad.children[6].click(); }""")
        before = await pg.evaluate("JSON.stringify([G.val, G.notes])")
        await pg.reload(); await pg.wait_for_load_state()
        after = await pg.evaluate("G && JSON.stringify([G.val, G.notes])")
        check(before == after and await pg.evaluate("$('game').classList.contains('on')"), "T3 resume after reload")
        await pg.evaluate("handleBack()")
        await pg.reload(); await pg.wait_for_load_state()
        check(await pg.evaluate("$('home').classList.contains('on')"), "T3 home after back+reload")

        # ---- T4：切后台计时暂停 ----
        await pg.evaluate("startLevel(1); cells[0].dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); G.time = 10; appPause()")
        await pg.wait_for_timeout(2300)
        t1 = await pg.evaluate("G.time")
        await pg.evaluate("appResume()")
        await pg.wait_for_timeout(2300)
        t2 = await pg.evaluate("G.time")
        check(t1 == 10 and t2 >= 11, f"T4 pause timer {t1} {t2}")

        # ---- T5：旧存档和题目对不上时不使用 ----
        await pg.evaluate("goHome(); localStorage.setItem('sudoku.game.1', JSON.stringify({p:'x', val:Array(81).fill(5), notes:Array(81).fill(0), mistakes:9, hints:3, time:99})); renderHome()")
        lbl = await pg.text_content("#continueText")
        await pg.evaluate("startLevel(1)")
        check(lbl == "开始第 1 关" and await pg.evaluate("G.mistakes === 0 && G.val.join('') === PUZZLES[0].p"), f"T5 stale save {lbl}")

        # ---- T6：返回键逻辑 ----
        await pg.evaluate("$('openSettings2').click()")
        r1 = await pg.evaluate("handleBack()"); s1 = await pg.evaluate("!!document.querySelector('.sheet-bg.on')")
        r2 = await pg.evaluate("handleBack()"); r3 = await pg.evaluate("handleBack()")
        check(r1 and not s1 and r2 and r3 is False, f"T6 back {r1} {s1} {r2} {r3}")

        print("page errors:", errs)
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())

async def extra():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 393, "height": 852})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(URL)
        SOLVE = """(sol) => { for (let i = 0; i < 81; i++) { if (G.val[i] === +sol[i]) continue;
            cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); pad.children[+sol[i]-1].click(); } }"""
        # 评星：0/1/2/3 次提示，外加错误和超长用时不影响
        for hints, want in ((0, 3), (1, 2), (2, 1), (3, 1)):
            await pg.evaluate("localStorage.clear(); progress={stars:{},best:{}}; startLevel(1); G.time = 99999")
            for _ in range(hints): await pg.evaluate("sel=-1; $('tHint').click(); for (let k = 0; k < 80 && $('hpanel').classList.contains('on'); k++) $('hpNext').click();")
            # 故意填错一次
            await pg.evaluate("""(sol) => { const i = G.val.indexOf(0); cells[i].dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); pad.children[(+sol[i]) % 9].click(); }""", P[0]["s"])
            await pg.evaluate(SOLVE, P[0]["s"])
            got = await pg.evaluate("[progress.stars[1], G.mistakes, G.hints]")
            check(got[0] == want and got[1] >= 1 and got[2] == hints, f"stars hints={hints} got {got}")
            await pg.wait_for_timeout(450)
            await pg.evaluate("closeSheet('winSheet'); goHome()")
        # 重玩只保留更好的星级
        await pg.evaluate("progress.stars={1:1}; startLevel(1)")
        await pg.evaluate(SOLVE, P[0]["s"])
        check(await pg.evaluate("progress.stars[1]") == 3, "replay upgrade")
        await pg.wait_for_timeout(450); await pg.evaluate("closeSheet('winSheet'); goHome(); startLevel(1); hideTip(); $('tHint').click(); for (let k = 0; k < 80 && $('hpanel').classList.contains('on'); k++) $('hpNext').click();")
        await pg.evaluate(SOLVE, P[0]["s"])
        check(await pg.evaluate("progress.stars[1]") == 3, "replay keeps best")
        # 通关后立刻按返回：弹窗不应出现在首页
        await pg.wait_for_timeout(450); await pg.evaluate("closeSheet('winSheet'); goHome(); startLevel(2)")
        await pg.evaluate(SOLVE, P[1]["s"])
        await pg.evaluate("handleBack()")
        await pg.wait_for_timeout(500)
        check(not await pg.evaluate("$('winSheet').classList.contains('on')"), "win sheet on home after back")
        # 1.0 版存档（没有 p 字段）应能继续
        await pg.evaluate("""localStorage.clear(); progress={stars:{},best:{}}; store.set('progress',progress);
            const v = PUZZLES[0].p.split('').map(Number); const i = v.indexOf(0); v[i] = +PUZZLES[0].s[i];
            localStorage.setItem('sudoku.game.1', JSON.stringify({val:v, notes:Array(81).fill(0), mistakes:2, hints:1, time:77})); renderHome(); startLevel(1)""")
        check(await pg.evaluate("G.mistakes===2 && G.time===77 && G.hints===1"), "v1 save kept")
        print("extra page errors:", errs)
        await b.close()

asyncio.run(extra())
print("FAILS:", fails if fails else "none")
