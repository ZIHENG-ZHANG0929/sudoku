"""大字模式的排版：各种屏幕尺寸下，每个页面都不横向溢出，游戏和练习页一屏放得下，弹窗按钮都够得着。"""
import asyncio, json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
_os.makedirs(ROOT + "/shots", exist_ok=True)
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
SIZES = [(320, 480), (360, 560), (360, 640), (375, 667), (393, 700), (393, 852), (412, 915), (768, 1000)]
fails = []
def check(c, m):
    if not c: fails.append(m)
MEASURE = """(mode) => {
  const de = document.documentElement, r = { sw: de.scrollWidth, sh: de.scrollHeight };
  const bot = id => { const e = document.getElementById(id); return e ? Math.round(e.getBoundingClientRect().bottom) : 0; };
  const vis = sel => [...document.querySelectorAll(sel)].map(e => e.getBoundingClientRect()).filter(b => b.width);
  if (mode === 'game') { r.need = Math.max(...vis('#pad .key').map(b => b.bottom)); r.board = Math.round(board.getBoundingClientRect().width); }
  if (mode === 'hint') { r.need = bot('hpNext'); r.boardBottom = Math.round(board.getBoundingClientRect().bottom); r.panelTop = Math.round(document.querySelector('#hpanel .hpanel-in').getBoundingClientRect().top); }
  if (mode === 'drill') r.need = Math.max(...vis('#tpad .key').map(b => b.bottom), bot('tBtnB'));
  if (mode === 'teach') r.need = bot('tBtnB');
  if (mode === 'settings' || mode === 'win') { const sh = document.querySelector('.sheet-bg.on .sheet'); r.scrollable = sh.scrollHeight - sh.clientHeight; r.top = Math.round(sh.getBoundingClientRect().top); }
  // 文字被截断：任何按钮里文字比按钮宽
  r.clipped = [...document.querySelectorAll('.screen.on button, .sheet-bg.on button, .hpanel.on button')].filter(b => b.offsetWidth && b.scrollWidth > b.clientWidth + 1).map(b => b.id || b.className).slice(0, 3);
  return r;
}"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w, h in SIZES:
            for mode in ("home", "game", "hint", "settings", "win", "tech", "teach", "drill"):
                pg = await b.new_page(viewport={"width": w, "height": h})
                errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
                await pg.goto(HTML + "#fs=1.30"); await pg.evaluate("localStorage.clear()"); await pg.reload()
                if not await pg.evaluate("document.documentElement.classList.contains('large')"):
                    check(False, "large mode not auto-enabled from font scale"); await pg.close(); continue
                await pg.evaluate("progress.stars = {}; for (let k = 1; k < 50; k++) progress.stars[k] = 3; progress.best[3] = 754; store.set('progress', progress); renderHome()")
                if mode == "game": await pg.evaluate("startLevel(50); hideTip()")
                if mode == "hint": await pg.evaluate("startLevel(50); hideTip(); $('tHint').click(); $('hpNext').click()")
                if mode == "settings": await pg.evaluate("startLevel(50); hideTip(); $('openSettings2').click()")
                if mode == "win":
                    await pg.evaluate("startLevel(1); hideTip(); for (let i = 0; i < 81; i++) if (!G.val[i]) { sel = i; G.noteMode = false; input(+PUZZLES[0].s[i]); }")
                    await pg.wait_for_timeout(450)
                if mode == "tech": await pg.evaluate("openTech()")
                if mode == "teach": await pg.evaluate("openTeach(4)")
                if mode == "drill": await pg.evaluate("openDrill(6, 0)")
                await pg.wait_for_timeout(250)
                r = await pg.evaluate(MEASURE, mode)
                tag = f"{w}x{h} {mode}"
                check(r["sw"] <= w, f"{tag}: horizontal overflow {r['sw']}")
                if mode in ("game", "drill", "teach"): check(r["sh"] <= h and r["need"] <= h, f"{tag}: does not fit one screen {r}")
                if mode == "hint": check(r["need"] <= h, f"{tag}: hint button off screen {r}")
                if mode in ("settings", "win"): check(r["top"] >= 0, f"{tag}: sheet top cut off {r}")
                check(not r["clipped"], f"{tag}: clipped text in {r['clipped']}")
                check(not errs, f"{tag}: errors {errs[:1]}")
                if (w, h) in ((360, 640),): await pg.screenshot(path=f"{ROOT}/shots/BIG_{mode}.png")
                await pg.close()
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
