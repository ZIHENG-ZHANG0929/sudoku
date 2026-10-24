"""兼容性：模拟没有 PointerEvent、不支持 aspect-ratio、版本过旧三种情况。"""
import asyncio, json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
_os.makedirs(ROOT + "/shots", exist_ok=True)
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
P = json.load(open(ROOT + "/gen/puzzles.json"))
fails = []
def check(c, m):
    if not c: fails.append(m)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        # 1) 没有 PointerEvent：用触摸选格子，并能通关
        ctx = await b.new_context(viewport={"width": 360, "height": 640}, has_touch=True, is_mobile=True)
        await ctx.add_init_script("delete window.PointerEvent; window.PointerEvent = undefined;")
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(HTML)
        await pg.evaluate("localStorage.clear()"); await pg.reload()
        await pg.tap("#continueBtn")
        sol = P[0]["s"]; puz = P[0]["p"]
        for i in [k for k in range(81) if puz[k] == "0"]:
            box = await (await pg.query_selector(f".cell:nth-child({i+1})")).bounding_box()
            await pg.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            await pg.tap(f'.key[data-d="{sol[i]}"]')
        check(await pg.evaluate("G && G.done"), "no-PointerEvent: could not finish level by touch")
        check(not errs, f"no-PointerEvent errors {errs[:2]}")
        await ctx.close()
        # 2) 不支持 aspect-ratio：强制使用兜底样式，棋盘、格子、关卡按钮仍是正方形
        for w, h in ((360, 560), (393, 852)):
            pg = await b.new_page(viewport={"width": w, "height": h})
            await pg.add_init_script("const o = CSS.supports.bind(CSS); CSS.supports = (a, v) => (a === 'aspect-ratio' ? false : o(a, v));")
            await pg.goto(HTML)
            await pg.add_style_tag(content=".board, .lv { aspect-ratio: auto !important; }")
            r = await pg.evaluate("""() => { const ar = document.documentElement.classList.contains('no-ar');
                const lv = document.querySelector('.lv').getBoundingClientRect();
                startLevel(1); const bd = board.getBoundingClientRect(), c = cells[40].getBoundingClientRect();
                return [ar, Math.round(bd.width), Math.round(bd.height), Math.round(c.width), Math.round(c.height), Math.round(lv.width), Math.round(lv.height),
                        document.documentElement.scrollHeight, innerHeight]; }""")
            ar, bw, bh, cw, ch, lw, lh, sh, ih = r
            check(ar and abs(bw - bh) <= 1 and abs(cw - ch) <= 1 and abs(lw - lh) <= 2 and sh <= ih, f"no-aspect-ratio {w}x{h}: {r}")
            await pg.close()
        # 3) 太旧：显示更新提示，而不是一片空白或错乱
        pg = await b.new_page(viewport={"width": 360, "height": 640})
        await pg.add_init_script("CSS.supports = () => false;")
        await pg.goto(HTML)
        txt = await pg.evaluate("(document.querySelector('.old') || {}).textContent || ''")
        check("Android System WebView" in txt, "old-browser message missing")
        await pg.screenshot(path=ROOT + "/shots/old.png")
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
