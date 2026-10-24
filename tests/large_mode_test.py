"""大字模式的开关逻辑：系统字体调大时第一次自动打开；用户手动关掉后不会再被自动打开；大字模式下长按不记笔记。"""
import asyncio, json, sys
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
fails = []
def check(c, m):
    if not c: fails.append(m)
SEL = "i => cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 393, "height": 852}, has_touch=True)
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        large = lambda: pg.evaluate("document.documentElement.classList.contains('large')")
        # 1) 系统字体正常：默认不开
        await pg.goto(HTML + "#fs=1.00"); await pg.evaluate("localStorage.clear()"); await pg.reload()
        check(not await large(), "should be off at normal font scale")
        # 2) 系统字体调大：第一次打开自动开启，并记住
        await pg.evaluate("localStorage.clear()"); await pg.goto(HTML + "#fs=1.30"); await pg.reload()
        check(await large() and await pg.evaluate("JSON.parse(localStorage.getItem('sudoku.settings')).large") is True, "should auto-enable at font scale 1.3")
        # 3) 用户手动关掉后，即使系统字体仍然很大也不会再自动打开
        await pg.evaluate("$('openSettings').click(); document.querySelector('.switch[data-key=large]').click(); closeSheet('setSheet')")
        check(not await large(), "toggle off did not apply immediately")
        await pg.reload()
        check(not await large(), "manual off should be remembered even with large system font")
        # 4) 手动打开：系统字体正常也保持打开
        await pg.goto(HTML + "#fs=1.00")
        await pg.evaluate("$('openSettings').click(); document.querySelector('.switch[data-key=large]').click(); closeSheet('setSheet')")
        await pg.reload()
        check(await large(), "manual on should be remembered")
        # 5) 大字模式下长按数字键不会记笔记，仍是正常填数
        await pg.evaluate("startLevel(1); hideTip()")
        i = await pg.evaluate("G.val.indexOf(0)"); d = await pg.evaluate(f"+PUZZLES[0].s[{i}]")
        await pg.evaluate(f"({SEL})({i})")
        box = await pg.locator(f'#pad .key[data-d="{d}"]').bounding_box()
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.wait_for_timeout(800); await pg.mouse.up(); await pg.wait_for_timeout(50)
        check(await pg.evaluate(f"G.val[{i}]") == d and await pg.evaluate(f"G.notes[{i}]") == 0, "long press in large mode should place the number normally")
        # 6) 游戏中切换大字模式：棋盘立即重新排版，状态不丢
        before = await pg.evaluate("G.val.join('')")
        await pg.evaluate("$('openSettings2').click(); document.querySelector('.switch[data-key=large]').click(); closeSheet('setSheet')")
        check(not await large() and await pg.evaluate("G.val.join('')") == before, "toggling in game lost state")
        # 7) 损坏的设置不影响
        await pg.evaluate("localStorage.setItem('sudoku.settings', '{\"large\": \"yes\"}')"); await pg.goto(HTML + "#fs=abc"); await pg.reload()
        check(not await large() and await pg.evaluate("document.querySelectorAll('.lv').length") == 100, "corrupt settings / font scale")
        check(not errs, f"page errors {errs[:2]}")
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
