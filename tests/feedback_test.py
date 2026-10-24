"""家人反馈的改动：撤销撤回错误次数、长按数字键记笔记、笔记模式标识、重新开始本关。"""
import asyncio, json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
P = json.load(open(ROOT + "/gen/puzzles.json"))
fails = []
def check(c, m):
    if not c: fails.append(m)
SEL = "i => cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 393, "height": 852}, has_touch=True)
        pg = await ctx.new_page()
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(HTML); await pg.evaluate("localStorage.clear()"); await pg.reload()
        await pg.evaluate("startLevel(1); hideTip()")
        sol, puz = P[0]["s"], P[0]["p"]
        e = [i for i in range(81) if puz[i] == "0"]
        # 1) 填错 → 错误 1；撤销 → 错误 0，格子空
        wd = int(sol[e[0]]) % 9 + 1
        await pg.evaluate(f"({SEL})({e[0]}); pad.children[{wd - 1}].click()")
        check(await pg.evaluate("G.mistakes") == 1, "wrong entry should count")
        await pg.click("#tUndo")
        check(await pg.evaluate("G.mistakes") == 0 and await pg.evaluate(f"G.val[{e[0]}]") == 0, "undo should take the mistake back")
        check(await pg.text_content("#gErr") == "错误 0", "error label not updated after undo")
        # 撤销正确的一步不会把之前的错误也抹掉
        await pg.evaluate(f"({SEL})({e[0]}); pad.children[{wd - 1}].click(); ({SEL})({e[1]}); pad.children[{int(sol[e[1]]) - 1}].click()")
        await pg.click("#tUndo")
        check(await pg.evaluate("G.mistakes") == 1, "undoing a correct move should keep earlier mistake")
        await pg.click("#tUndo")
        check(await pg.evaluate("G.mistakes") == 0, "undoing the wrong move should remove it")
        # 2) 长按数字键：普通模式下记笔记，不算错误
        await pg.evaluate(f"({SEL})({e[2]})")
        key = pg.locator('#pad .key[data-d="7"]')
        box = await key.bounding_box()
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.wait_for_timeout(600); await pg.mouse.up()
        await pg.wait_for_timeout(50)
        st = await pg.evaluate(f"[G.val[{e[2]}], G.notes[{e[2]}], G.noteMode, G.mistakes]")
        check(st == [0, 1 << 6, False, 0], f"long press in normal mode should add a note only: {st}")
        # 短按仍然是正式填入
        await pg.click('#pad .key[data-d="%s"]' % sol[e[2]])
        check(await pg.evaluate(f"G.val[{e[2]}]") == int(sol[e[2]]), "short tap should still place the number")
        # 笔记模式下长按：正式填入
        await pg.click("#tNote")
        check(await pg.text_content("#tNoteLbl") == "笔记 开" and await pg.evaluate("pad.classList.contains('notes-mode')"), "note mode label/style")
        await pg.evaluate(f"({SEL})({e[3]})")
        key = pg.locator('#pad .key[data-d="%s"]' % sol[e[3]]); box = await key.bounding_box()
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.wait_for_timeout(600); await pg.mouse.up(); await pg.wait_for_timeout(50)
        check(await pg.evaluate(f"G.val[{e[3]}]") == int(sol[e[3]]) and await pg.evaluate("G.noteMode") is True, "long press in note mode should place the number and stay in note mode")
        await pg.click("#tNote")
        check(await pg.text_content("#tNoteLbl") == "笔记", "note label off")
        # 3) 重新开始：先确认；取消不变；确认后全部清零
        await pg.evaluate("G.started = true; G.time = 77; G.hints = 2; save()")
        await pg.click("#openSettings2")
        check(not await pg.evaluate("$('restartBtn').hidden"), "restart button should show in game")
        await pg.click("#restartBtn"); await pg.click("#cfNo")
        check(await pg.evaluate("G.time") in (77, 78) and await pg.evaluate("G.hints") == 2, "cancel restart changed the game")   # 计时器可能刚好走了一秒
        await pg.click("#openSettings2"); await pg.click("#restartBtn"); await pg.click("#cfYes")
        st = await pg.evaluate("[G.val.join(''), G.time, G.hints, G.mistakes, G.history.length, G.n]")
        check(st == [puz, 0, 0, 0, 0, 1], f"restart did not reset: {st[1:]}")
        await pg.reload()
        check(await pg.evaluate("G && G.val.join('')") == puz, "restart state not persisted / resumed")
        # 首页的设置里不显示“重新开始”
        await pg.evaluate("goHome(); $('openSettings').click()")
        check(await pg.evaluate("$('restartBtn').hidden"), "restart button should be hidden on home")
        await pg.evaluate("closeSheet('setSheet')")
        # 整题练习也能重新开始
        await pg.evaluate("startPractice(2, 0); G.started = true; G.time = 30")
        await pg.evaluate(f"({SEL})(G.val.indexOf(0)); pad.children[0].click()")
        await pg.click("#openSettings2"); await pg.click("#restartBtn"); await pg.click("#cfYes")
        check(await pg.evaluate("G.practice && G.time === 0 && G.val.join('') === G.practice.P.p"), "practice restart")
        check(not errs, f"page errors {errs[:2]}")
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
