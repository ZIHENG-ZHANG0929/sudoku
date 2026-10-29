"""6×6 大格模式：首页切换、两套进度分开、回到对局、通关流程、键盘、清除进度、各尺寸排版。"""
import asyncio, json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
P6 = json.load(open(ROOT + "/gen/puzzles6.json"))
P9 = json.load(open(ROOT + "/gen/puzzles.json"))
fails = []
def check(c, m):
    if not c: fails.append(m)
SOLVE = """(sol) => { for (let i = 0; i < cells.length; i++) if (G.val[i] !== +sol[i]) {
  cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true})); pad.children[+sol[i] - 1].click(); } }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 393, "height": 852})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(HTML); await pg.evaluate("localStorage.clear()"); await pg.reload()
        # 1) 默认 9×9；切到 6×6 后关卡列表 50 关，记住选择
        check(await pg.evaluate("document.querySelectorAll('.lv').length") == 100, "default should be 9x9 with 100 levels")
        await pg.click('#modeSw button[data-m="6"]')
        check(await pg.evaluate("document.querySelectorAll('.lv').length") == 50 and await pg.text_content("#homeSub") == "50 关，从易到难", "6x6 list")
        await pg.reload()
        check(await pg.evaluate("HM") == 6 and await pg.evaluate("document.querySelector('#modeSw button.on').dataset.m") == "6", "mode choice not remembered")
        # 2) 6×6 第 1 关：36 格、6 个键、标题
        await pg.click("#continueBtn")
        st = await pg.evaluate("[cells.length, pad.children.length, $('gTitle').textContent, board.classList.contains('g6')]")
        check(st == [36, 6, "6×6 · 第 1 关", True], f"6x6 board setup {st}")
        # 键盘 7、8、9 不起作用
        i = await pg.evaluate("G.val.indexOf(0)")
        await pg.evaluate(f"cells[{i}].dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true}}))")
        for k in "789": await pg.keyboard.press(k)
        check(await pg.evaluate(f"G.val[{i}]") == 0 and await pg.evaluate("G.mistakes") == 0, "keys 7-9 should do nothing in 6x6")
        # 3) 刷新后回到 6×6 对局
        await pg.keyboard.press(P6[0]["s"][i])
        await pg.reload()
        check(await pg.evaluate("G && G.m === 6 && G.n === 1") and await pg.evaluate(f"G.val[{i}]") == int(P6[0]["s"][i]), "6x6 game not resumed after reload")
        # 4) 用讲解型提示（确认后一路讲到填入）
        before = await pg.evaluate("G.val.join('')")
        await pg.evaluate("$('tHint').click(); for (let k = 0; k < 80 && $('hpanel').classList.contains('on'); k++) $('hpNext').click();")
        after = await pg.evaluate("G.val.join('')")
        diff = [k for k in range(36) if before[k] != after[k]]
        check(len(diff) == 1 and after[diff[0]] == P6[0]["s"][diff[0]] and await pg.evaluate("G.hints") == 1, f"6x6 hint {diff}")
        # 5) 通关：进度记在 6×6，9×9 不受影响；下一关
        await pg.evaluate(SOLVE, P6[0]["s"]); await pg.wait_for_timeout(450)
        check(await pg.text_content("#winTitle") == "6×6 · 第 1 关完成", "6x6 win title")
        check(await pg.evaluate("JSON.parse(localStorage.getItem('sudoku.progress6')).stars[1]") == 2, "6x6 progress not saved (1 hint = 2 stars)")
        check(await pg.evaluate("localStorage.getItem('sudoku.progress')") is None and await pg.evaluate("Object.keys(PROG[9].stars).length") == 0, "9x9 progress touched")
        await pg.wait_for_timeout(700)   # 通关面板刚弹出的 700ms 内不响应点击（防连点）
        await pg.click("#winNext")
        check(await pg.evaluate("G.n === 2 && G.m === 6"), "next 6x6 level")
        await pg.evaluate("handleBack()")
        check(await pg.evaluate("document.querySelector('.lv[data-n=\"1\"] .bt').textContent") != "", "6x6 tile best time")
        # 6) 切回 9×9：进度、继续按钮各自独立
        await pg.click('#modeSw button[data-m="9"]')
        check(await pg.text_content("#continueText") == "开始第 1 关" and await pg.evaluate("document.querySelectorAll('.lv').length") == 100, "9x9 home after switch")
        await pg.click("#continueBtn")
        check(await pg.evaluate("[cells.length, pad.children.length, G.m]") == [81, 9, 9], "9x9 board after switching back")
        await pg.evaluate("hideTip(); handleBack()")
        # 7) 最后一关：标题、没有“下一关”
        await pg.click('#modeSw button[data-m="6"]')
        await pg.evaluate("for (let k = 1; k < 50; k++) PROG[6].stars[k] = 3; store.set('progress6', PROG[6]); renderHome(); startLevel(50)")
        await pg.evaluate(SOLVE, P6[49]["s"]); await pg.wait_for_timeout(450)
        check(await pg.text_content("#winTitle") == "6×6 · 全部 50 关完成" and await pg.evaluate("$('winNext').style.display") == "none", "last 6x6 level win sheet")
        await pg.evaluate("closeSheet('winSheet'); goHome()")
        check(await pg.text_content("#continueText") == "已全部通关", "6x6 all cleared label")
        # 8) 清除进度：两套都清
        await pg.evaluate("PROG[9].stars[1] = 3; store.set('progress', PROG[9]); $('openSettings').click(); $('resetBtn').click(); $('cfYes').click()")
        check(await pg.evaluate("Object.keys(PROG[6].stars).length + Object.keys(PROG[9].stars).length") == 0, "reset should clear both modes")
        check(await pg.evaluate("Object.keys(progress.stars).length") == 0 and await pg.evaluate("progress === PROG[HM]"), "progress pointer after reset")
        # 9) 损坏的 6×6 存档
        await pg.evaluate("localStorage.setItem('sudoku.game6.1', JSON.stringify({val: Array(81).fill(1), notes: [], mistakes: 0, hints: 0, time: 0})); localStorage.setItem('sudoku.current6', '1')")
        await pg.reload()
        check(await pg.evaluate("G && G.val.join('') === PUZZLES6[0].p"), "corrupt 6x6 save should be ignored")
        check(not errs, f"page errors {errs[:2]}")

        # 10) 排版：普通和大字模式，6×6 首页和游戏都一屏放得下、不横向溢出
        for w, h in [(320, 480), (360, 560), (360, 640), (393, 700), (393, 852), (412, 915), (768, 1000)]:
            for fs in ("", "#fs=1.30"):
                q = await b.new_page(viewport={"width": w, "height": h})
                await q.goto(HTML + fs); await q.evaluate("localStorage.clear(); localStorage.setItem('sudoku.homeMode', '6')"); await q.reload()
                hm = await q.evaluate("document.documentElement.scrollWidth")
                await q.evaluate("startLevel(1)")
                r = await q.evaluate("""() => { const k = [...pad.children].map(x => x.getBoundingClientRect()).filter(x => x.width);
                  return [document.documentElement.scrollWidth, document.documentElement.scrollHeight, Math.max(...k.map(x => x.bottom)), Math.round(board.getBoundingClientRect().width)]; }""")
                tag = f"{w}x{h}{' large' if fs else ''}"
                check(hm <= w and r[0] <= w, f"{tag}: horizontal overflow")
                check(r[1] <= h and r[2] <= h, f"{tag}: 6x6 game does not fit {r}")
                await q.close()
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
