"""第 1 轮代码审查发现的问题（A–T）修好后的回归测试。"""
import asyncio, json, sys
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
P = json.load(open(ROOT + "/gen/puzzles.json"))
P6 = json.load(open(ROOT + "/gen/puzzles6.json"))
fails = []
def check(c, m):
    if not c: fails.append(m)
SEL = "i => cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))"

async def fresh(b, w=393, h=852, hash=""):
    ctx = await b.new_context(viewport={"width": w, "height": h}, has_touch=True)
    pg = await ctx.new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(HTML + hash); await pg.evaluate("localStorage.clear()"); await pg.reload()
    return ctx, pg, errs

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()

        # A：提示面板开着时清除全部进度，回到首页后面板全部关掉，不报错
        for mode in (9, 6):
            ctx, pg, errs = await fresh(b)
            await pg.evaluate(f"HM = {mode}; progress = PROG[HM]; renderHome(); startLevel(1); hideTip(); $('tHint').click()")
            check(await pg.evaluate("$('hpanel').classList.contains('on')"), f"A{mode}: confirm panel should be open")
            await pg.evaluate("$('openSettings2').click(); $('resetBtn').click(); $('cfYes').click()")
            await pg.wait_for_timeout(50)
            st = await pg.evaluate("[$('hpanel').classList.contains('on'), $('tipPanel').classList.contains('on'), $('home').classList.contains('on'), G, H, HC]")
            check(st == [False, False, True, None, None, None], f"A{mode}: panels left after reset: {st}")
            await pg.evaluate("$('hpNext').click(); $('hpPrev').click(); $('hpClose').click()")
            # 讲解面板（不是确认）开着时也一样
            await pg.evaluate("startLevel(1); hideTip(); $('tHint').click(); $('hpNext').click()")
            check(await pg.evaluate("!!(H && H.open)"), f"A{mode}: explain panel should be open")
            await pg.evaluate("$('openSettings2').click(); $('resetBtn').click(); $('cfYes').click()")
            check(not await pg.evaluate("$('hpanel').classList.contains('on')"), f"A{mode}: explain panel left after reset")
            await pg.evaluate("$('hpNext').click(); $('hpPrev').click()")
            check(not errs, f"A{mode}: page errors {errs}")
            await ctx.close()

        # B：首页设置里看不到“重新开始这一关”；游戏里能看到
        ctx, pg, errs = await fresh(b)
        await pg.click("#openSettings")
        check(not await pg.is_visible("#restartBtn"), "B: restart button visible on home settings")
        await pg.evaluate("closeSheet('setSheet'); startLevel(1); hideTip()")
        await pg.click("#openSettings2")
        check(await pg.is_visible("#restartBtn"), "B: restart button should be visible in game")
        await ctx.close()

        # D：棋盘行高固定为 N 等分（旧 WebView 不支持容器查询时也不会塌）
        ctx, pg, errs = await fresh(b)
        check(await pg.evaluate("board.style.gridTemplateRows") == "repeat(9, 1fr)", "D: 9x9 rows")
        await pg.evaluate("HM = 6; progress = PROG[HM]; startLevel(1); hideTip()")
        check(await pg.evaluate("board.style.gridTemplateRows") == "repeat(6, 1fr)", "D: 6x6 rows")
        check(await pg.evaluate("tboard.style.gridTemplateRows") == "repeat(9, 1fr)", "D: tboard rows")
        await ctx.close()

        # F：提示确认框弹出后用方向键换格子，确认框关掉；再点提示是按新格子重新判断
        ctx, pg, errs = await fresh(b)
        sol, puz = P[0]["s"], P[0]["p"]
        e = [i for i in range(81) if puz[i] == "0"]
        wd = int(sol[e[0]]) % 9 + 1
        await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[0]}); pad.children[{wd - 1}].click(); $('tHint').click()")
        check(await pg.evaluate("!!(HC && HC.wc === sel && sel >= 0)"), "F: wrong-cell confirm expected")
        await pg.keyboard.press("ArrowRight")
        check(await pg.evaluate("HC === null && !$('hpanel').classList.contains('on')"), "F: arrow key should close confirm")
        await ctx.close()

        # G：第 91 关提醒文字
        ctx, pg, errs = await fresh(b)
        t = await pg.evaluate("TIER_TIPS[91]")
        check("剑鱼" not in t and "XY-Wing" in t, f"G: tier tip text {t}")
        await ctx.close()

        # H：先改过别的设置（存下 large:false），再调大系统字体，大字模式仍会自动打开；手动关掉后不再自动打开
        ctx, pg, errs = await fresh(b)
        await pg.evaluate("localStorage.setItem('sudoku.settings', JSON.stringify({showErrors:false, autoClean:true, highlightSame:true, showTimer:true, large:false}))")
        await pg.goto(HTML + "#fs=1.30"); await pg.reload()
        check(await pg.evaluate("settings.large && !settings.showErrors"), "H: large should auto-enable even when settings were saved")
        await pg.evaluate("document.querySelector('.switch[data-key=large]').click()")
        check(await pg.evaluate("!settings.large"), "H: manual off failed")
        await pg.reload()
        check(await pg.evaluate("!settings.large"), "H: auto re-enabled after manual off")
        await ctx.close()

        # I：关掉显示计时，通关面板不显示用时
        for timer in (False, True):
            ctx, pg, errs = await fresh(b)
            await pg.evaluate(f"settings.showTimer = {str(timer).lower()}; startLevel(1); hideTip()")
            await pg.evaluate(f"G.val = '{sol}'.split('').map(Number); G.time = 65; after()")
            await pg.wait_for_timeout(500)
            vis = await pg.is_visible("#winTime")
            check(vis == timer, f"I: win time visible={vis} with showTimer={timer}")
            tip = await pg.text_content("#winTip")
            check(timer or "用时" not in tip, f"I: win tip mentions time: {tip}")
            await ctx.close()

        # J：讲解到一半刷新，再点提示不重复扣
        ctx, pg, errs = await fresh(b)
        await pg.evaluate("startLevel(1); hideTip(); $('tHint').click(); $('hpNext').click()")
        check(await pg.evaluate("G.hints") == 1 and await pg.evaluate("!!(H && H.open)"), "J: first hint")
        await pg.reload()
        check(await pg.evaluate("G && G.n === 1 && G.hints === 1"), "J: reload should resume level 1 with 1 hint used")
        await pg.evaluate("hideTip(); $('tHint').click()")
        st = await pg.evaluate("[G.hints, !!(H && H.open), HC]")
        check(st == [1, True, None], f"J: reopening hint after reload should be free and skip confirm: {st}")
        # 填入后盘面变了，下一次正常扣
        await pg.evaluate("while (H.i < H.list.length - 1) $('hpNext').click(); $('hpNext').click(); $('tHint').click()")
        check(await pg.evaluate("!!HC"), "J: next hint after placing should ask again")
        await ctx.close()

        # K：6×6 首页的技巧练习写明是 9×9
        ctx, pg, errs = await fresh(b)
        await pg.evaluate("document.querySelector('#modeSw button[data-m=\"6\"]').click()")
        check((await pg.text_content("#learnSub")).startswith("9×9"), "K: learn sub should mention 9x9 in 6x6 mode")
        await pg.evaluate("document.querySelector('#modeSw button[data-m=\"9\"]').click()")
        check(not (await pg.text_content("#learnSub")).startswith("9×9"), "K: 9x9 mode label")
        await ctx.close()

        # L：大字模式 360 宽，选中格有 9 个笔记时笔记行不折行、页面不出现纵向滚动
        for h in (640, 720):
            ctx, pg, errs = await fresh(b, 360, h, "#fs=1.30")
            await pg.evaluate(f"startLevel(50); hideTip(); const i = G.val.indexOf(0); G.notes[i] = 511; ({SEL})(i)")
            r = await pg.evaluate("[$('gNote').getBoundingClientRect().height, document.documentElement.scrollHeight - innerHeight]")
            check(r[0] < 40 and r[1] <= 0, f"L: 360x{h} note line height/scroll {r}")
            await ctx.close()

        # M：整题练习中途刷新，回到那一题
        ctx, pg, errs = await fresh(b)
        await pg.evaluate("startPractice(3, 1); G.started = true; const i = G.val.indexOf(0); G.notes[i] = 3; G.time = 9; save()")
        await pg.reload()
        st = await pg.evaluate("G && G.practice ? [G.practice.k, G.practice.j, G.time] : null")
        check(st == [3, 1, 9], f"M: practice not resumed after reload: {st}")
        await pg.evaluate("goHome()")
        await pg.reload()
        check(await pg.evaluate("G === null && $('home').classList.contains('on')"), "M: after leaving practice, reload should stay on home")
        await ctx.close()

        # N：存档里是完整正确答案 → 当作新的一局
        ctx, pg, errs = await fresh(b)
        await pg.evaluate(f"localStorage.setItem('sudoku.game.1', JSON.stringify({{p: '{puz}', val: '{sol}'.split('').map(Number), notes: Array(81).fill(0), mistakes: 0, hints: 0, time: 5}})); startLevel(1); hideTip()")
        check(await pg.evaluate("!G.done && G.val.join('') === G.given.join('')"), "N: solved save should start fresh")
        await ctx.close()

        # Q：关掉“标出错误”时，确认文字不说“填错了”
        ctx, pg, errs = await fresh(b)
        await pg.evaluate(f"settings.showErrors = false; startLevel(1); hideTip(); ({SEL})({e[0]}); pad.children[{wd - 1}].click(); $('tHint').click()")
        check("填错" not in await pg.text_content("#hpText"), "Q: confirm text reveals error when errors hidden")
        await ctx.close()

        # S：重玩三星关卡时用了提示
        ctx, pg, errs = await fresh(b)
        await pg.evaluate("PROG[9].stars[1] = 3; PROG[9].best[1] = 50; startLevel(1); hideTip(); G.hints = 1")
        await pg.evaluate(f"G.val = '{sol}'.split('').map(Number); after()")
        await pg.wait_for_timeout(500)
        check("保留" in await pg.text_content("#winTip"), "S: replay tip should say previous 3 stars kept")
        await ctx.close()

        # T：进关卡什么都没做就返回，首页仍是“开始第 1 关”
        ctx, pg, errs = await fresh(b)
        await pg.evaluate("startLevel(1); hideTip(); goHome()")
        check(await pg.text_content("#continueText") == "开始第 1 关", "T: blank game left a save")
        check(await pg.evaluate("localStorage.getItem('sudoku.game.1')") is None, "T: blank save stored")
        await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[0]}); pad.children[{int(sol[e[0]]) - 1}].click(); goHome()")
        check(await pg.text_content("#continueText") == "继续第 1 关", "T: real progress should be saved")
        await ctx.close()

        # E：长按后按键失去焦点
        ctx, pg, errs = await fresh(b)
        await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[2]})")
        key = pg.locator('#pad .key[data-d="7"]'); box = await key.bounding_box()
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.wait_for_timeout(600); await pg.mouse.up(); await pg.wait_for_timeout(50)
        check(await pg.evaluate("!document.activeElement || !document.activeElement.classList.contains('key')"), "E: key keeps focus after long press")
        await ctx.close()

        # 第 2 轮：讲解中途在设置里切换大字模式，面板重新贴合，不盖住棋盘
        ctx, pg, errs = await fresh(b, 360, 640)
        await pg.evaluate("startLevel(2); hideTip(); $('tHint').click(); $('hpNext').click(); H.i = Math.min(1, H.list.length - 1); render(); renderHint()")
        for _ in range(2):
            await pg.evaluate("$('openSettings2').click(); document.querySelector('.switch[data-key=large]').click(); closeSheet('setSheet')")
            await pg.wait_for_timeout(300)
            ov = await pg.evaluate("board.getBoundingClientRect().bottom - $('hpanel').getBoundingClientRect().top")
            check(ov <= 0, f"R2: panel overlaps board by {ov}px after toggling large={await pg.evaluate('settings.large')}")
        # 关掉标出错误、选中错格时的确认文字说的是直接给答案
        await pg.evaluate(f"closeHintPanel(); settings.showErrors = false; startLevel(1); hideTip(); ({SEL})({e[0]}); pad.children[{wd - 1}].click(); $('tHint').click()")
        t = await pg.text_content("#hpText")
        check("如果盘面上有不对的数" in t and "填错" not in t, f"R2: confirm text {t}")   # 第 11 轮：关掉标出错误时不透露有没有错
        await ctx.close()

        # 第 2 轮：大字模式设置面板顶部有“完成”，内容超出时有滑动提示，滑到底后提示消失
        ctx, pg, errs = await fresh(b, 393, 780, "#fs=1.30")
        await pg.evaluate("startLevel(1); hideTip(); $('openSettings2').click()")
        check(await pg.is_visible("#setDone"), "R2: top done button should be visible")
        sb = await pg.evaluate("[$('setBody').scrollHeight > $('setBody').clientHeight, $('setMore').classList.contains('on')]")
        check(sb[0] == sb[1], f"R2: settings scroll cue {sb}")
        await pg.evaluate("$('setBody').scrollTop = 99999"); await pg.wait_for_timeout(100)
        check(not await pg.evaluate("$('setMore').classList.contains('on')"), "R2: cue should hide at bottom")
        check(await pg.is_visible("#resetBtn"), "R2: reset reachable after scrolling")
        await pg.click("#setDone")
        check(not await pg.evaluate("$('setSheet').classList.contains('on')"), "R2: top done closes")
        # 技巧练习讲解第一页：截断时有提示
        cues = []
        for k in range(10):
            r = await pg.evaluate(f"""() => {{ openTech(); openTeach({k});
              const p = $('tPanel'); return [p.scrollHeight > p.clientHeight + 2, $('tMore').classList.contains('on')]; }}""")
            cues.append(r)
        check(all(x[0] == x[1] for x in cues), f"R2: lesson cue mismatch {cues}")
        await ctx.close()

        # 自动清理：标出错误开着时，填错不清别人的笔记
        ctx, pg, errs = await fresh(b)
        peer = await pg.evaluate(f"startLevel(1); hideTip(); GM.PEERS[{e[0]}].find(p => !G.given[p])")
        await pg.evaluate(f"G.notes[{peer}] = 511; ({SEL})({e[0]}); pad.children[{wd - 1}].click()")
        check(await pg.evaluate(f"G.notes[{peer}]") == 511, "R2: wrong entry cleaned peer notes")
        await pg.evaluate(f"$('tErase').click(); pad.children[{int(sol[e[0]]) - 1}].click()")
        check(await pg.evaluate(f"G.notes[{peer}]") == 511 & ~(1 << (int(sol[e[0]]) - 1)), "R2: correct entry should clean peer notes")
        await ctx.close()

        # 双击关卡块：提醒不被第二下关掉
        ctx, pg, errs = await fresh(b)
        lv = await pg.query_selector('.lv[data-n="1"]'); bx = await lv.bounding_box()
        cx, cy = bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2
        await pg.mouse.click(cx, cy)
        await pg.wait_for_timeout(120)
        # 双击的第二下：同一位置落在棋盘的某一格上
        await pg.evaluate(f"cells[40].dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true, clientX: {cx}, clientY: {cy}}}))")
        check(await pg.evaluate("$('tipPanel').classList.contains('on')"), "R2: double tap dismissed the tier tip")
        # 别处的点击照常关掉提醒
        await pg.evaluate(f"cells[40].dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true, clientX: {cx} + 120, clientY: {cy} + 120}}))")
        check(not await pg.evaluate("$('tipPanel').classList.contains('on')"), "R2: tap elsewhere should dismiss tip")
        await ctx.close()

        # 通关时设置面板开着：通关面板在最上面，返回键先关它并回首页，不留设置面板
        ctx, pg, errs = await fresh(b)
        await pg.evaluate(f"startLevel(1); hideTip(); G.val = '{sol}'.split('').map(Number); after(); $('openSettings2').click()")
        await pg.wait_for_timeout(500)
        st = await pg.evaluate("[...document.querySelectorAll('.sheet-bg.on')].map(x => x.id)")
        check(st == ["winSheet"], f"R2: open sheets after win {st}")
        await pg.evaluate("handleBack()")
        check(await pg.evaluate("$('home').classList.contains('on') && !document.querySelector('.sheet-bg.on')"), "R2: back after win")
        await ctx.close()

        # 6×6 大字小屏：讲解面板不盖住棋盘
        for w, h in ((320, 568), (360, 640)):
            ctx, pg, errs = await fresh(b, w, h, "#fs=1.30")
            await pg.evaluate("HM = 6; progress = PROG[6]")
            bad = 0
            for n in range(1, 51, 3):
                await pg.evaluate(f"H = null; HC = null; startLevel({n}); hideTip(); $('tHint').click(); $('hpNext').click()")
                k = await pg.evaluate("H ? H.list.length : 0")
                for i in range(k):
                    ov = await pg.evaluate(f"H.i = {i}; render(); renderHint(); board.getBoundingClientRect().bottom - $('hpanel').getBoundingClientRect().top")
                    if ov > 0: bad += 1
            check(bad == 0, f"R2: 6x6 large {w}x{h} panel overlaps in {bad} frames")
            await ctx.close()

        # 第 3 轮：双击“使用提示”不跳过讲解第一步；长按滑出后切大字，第一次点数字照常填入
        ctx, pg, errs = await fresh(b)
        await pg.evaluate("startLevel(1); hideTip(); $('tHint').click()")
        await pg.dblclick("#hpNext")
        check(await pg.evaluate("H && H.open && H.i === 0"), f"R3: double tap skipped first frame, H.i={await pg.evaluate('H && H.i')}")
        await pg.wait_for_timeout(800); await pg.click("#hpNext")
        check(await pg.evaluate("!H || !H.open || H.i === 1 || H.list.length === 1"), "R3: later tap on next should advance")
        await ctx.close()
        ctx, pg, errs = await fresh(b)
        await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[4]})")
        key = pg.locator('#pad .key[data-d="5"]'); box = await key.bounding_box()
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.wait_for_timeout(600)
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] - 200); await pg.mouse.up()
        await pg.evaluate("document.querySelector('.switch[data-key=large]').click()")
        await pg.evaluate(f"({SEL})({e[5]})")
        await pg.click('#pad .key[data-d="%s"]' % sol[e[5]])
        check(await pg.evaluate(f"G.val[{e[5]}]") == int(sol[e[5]]), "R3: first tap after stale long-press swallowed")
        await ctx.close()

        # 第 3 轮：双击弹层按钮，第二下不穿透到下面的数字键/齿轮
        ctx, pg, errs = await fresh(b, 360, 640, "#fs=1.30")
        await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[6]})")
        async def dbl(sel_):
            bb = await pg.locator(sel_).bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            await pg.mouse.click(x, y); await pg.wait_for_timeout(120); await pg.mouse.click(x, y); await pg.wait_for_timeout(50)
        for btn in ("#hpClose",):
            await pg.evaluate("$('tHint').click()")
            await dbl(btn)
            st = await pg.evaluate(f"[G.val[{e[6]}], G.mistakes, $('hpanel').classList.contains('on')]")
            check(st == [0, 0, False], f"R3: double tap on {btn} leaked through: {st}")
        await pg.evaluate("$('openSettings2').click()"); await pg.wait_for_timeout(300)
        await dbl("#setDone")
        check(not await pg.evaluate("$('setSheet').classList.contains('on')"), "R3: double tap on top done reopened settings")
        await pg.wait_for_timeout(450)
        # 正常的单击不受影响
        await pg.click('#pad .key[data-d="%s"]' % sol[e[6]])
        check(await pg.evaluate(f"G.val[{e[6]}]") == int(sol[e[6]]), "R3: normal tap after shield window blocked")
        # 大字模式下写第一个笔记，棋盘不上下跳
        y0 = await pg.evaluate("board.getBoundingClientRect().top")
        await pg.evaluate(f"({SEL})({e[7]}); G.noteMode = true; pad.children[0].click(); G.noteMode = false; render()")
        y1 = await pg.evaluate("board.getBoundingClientRect().top")
        check(abs(y1 - y0) < 0.5, f"R3: board moved {y0}->{y1} when note shown")
        # 点题目给的数字再按数字键：有提示
        gi = await pg.evaluate("G.given.findIndex(x => x)")
        await pg.evaluate(f"({SEL})({gi}); pad.children[0].click()")
        check("题目给的" in await pg.text_content("#toast") if await pg.query_selector("#toast") else True, "R3: no feedback on given cell")
        await ctx.close()
        # 回首页时首页回到原来的滚动位置
        ctx, pg, errs = await fresh(b, 360, 640)
        await pg.evaluate("for (let k = 1; k < 60; k++) PROG[9].stars[k] = 3; progress = PROG[9]; renderHome(); window.scrollTo(0, 900)")
        y = await pg.evaluate("scrollY")
        await pg.evaluate("startLevel(50); hideTip(); goHome()")
        check(abs(await pg.evaluate("scrollY") - y) < 2, "R3: home scroll not restored")
        await ctx.close()

        # 第 4 轮：双击“下一关”进入新难度段，不会被第二下带进技巧练习；刚弹出的通关面板不吃连点；双击“清除全部进度”确认框不一闪而过
        for w, h, hs in ((393, 852, ""), (360, 640, "#fs=1.30")):
            ctx, pg, errs = await fresh(b, w, h, hs)
            s20 = P[19]["s"]
            await pg.evaluate(f"for (let k = 1; k < 20; k++) PROG[9].stars[k] = 3; progress = PROG[9]; startLevel(20); hideTip(); G.val = '{s20}'.split('').map(Number); after()")
            await pg.wait_for_timeout(1100)
            bb = await pg.locator("#winNext").bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            await pg.mouse.click(x, y); await pg.wait_for_timeout(150); await pg.mouse.click(x, y); await pg.wait_for_timeout(100)
            st = await pg.evaluate("[$('game').classList.contains('on'), G && G.n, $('tipPanel').classList.contains('on')]")
            check(st == [True, 21, True], f"R4 {w}x{h}: double tap on next level -> {st}")
            # 通关后 500ms 再点同一位置（慢速双击）：通关面板留着
            await pg.evaluate("hideTip(); for (let k = 1; k < 21; k++) PROG[9].stars[k] = 3")
            s21 = P[20]["s"]
            await pg.evaluate(f"G.val = '{s21}'.split('').map(Number); after()")
            await pg.wait_for_timeout(420)
            await pg.mouse.click(x, y); await pg.wait_for_timeout(100)
            check(await pg.evaluate("$('winSheet').classList.contains('on')"), f"R4 {w}x{h}: fresh win sheet swallowed by a late tap")
            await pg.wait_for_timeout(800)
            await pg.mouse.click(x, y); await pg.wait_for_timeout(100)
            check(await pg.evaluate("G && G.n === 22"), f"R4 {w}x{h}: normal tap on next level after the guard")
            # 双击设置里的“清除全部进度”：确认框还在
            await pg.evaluate("hideTip(); $('openSettings2').click(); $('setBody').scrollTop = 99999"); await pg.wait_for_timeout(300)
            bb = await pg.locator("#resetBtn").bounding_box(); x2, y2 = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            await pg.mouse.click(x2, y2); await pg.wait_for_timeout(150); await pg.mouse.click(x2, y2); await pg.wait_for_timeout(100)
            check(await pg.evaluate("$('confirmSheet').classList.contains('on')"), f"R4 {w}x{h}: reset confirm closed by double tap")
            await pg.evaluate("closeSheet('confirmSheet')")
            check(not errs, f"R4 errors {errs}")
            await ctx.close()

        # 第 4 轮（老人手势）：双击齿轮、双击“开始练习”、双击“继续”；点设置行的文字也能开关
        for w, h, hs in ((360, 640, ""), (360, 640, "#fs=1.30"), (393, 852, "#fs=1.30")):
            ctx, pg, errs = await fresh(b, w, h, hs)
            async def dbl(sel_, gap=150):
                bb = await pg.locator(sel_).bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
                await pg.mouse.click(x, y); await pg.wait_for_timeout(gap); await pg.mouse.click(x, y); await pg.wait_for_timeout(80)
            lg = await pg.evaluate("settings.large")
            await dbl("#openSettings")
            st = await pg.evaluate("[$('setSheet').classList.contains('on'), settings.large]")
            check(st == [True, lg], f"R4b {w}x{h}{hs}: double tap gear -> {st}")
            await pg.evaluate("closeSheet('setSheet')"); await pg.wait_for_timeout(450)
            await dbl("#continueBtn")
            st = await pg.evaluate("[$('game').classList.contains('on'), sel, G && G.started]")
            check(st[0] and st[1] == -1 and not st[2], f"R4b {w}x{h}{hs}: double tap continue -> {st}")
            await pg.evaluate("hideTip(); goHome(); openTeach(0); T.fi = T.frames.length - 1; renderT(); lastTap = null")
            await dbl("#tBtnB")
            st = await pg.evaluate("[T.mode, T.j]")
            check(st == ["drill", 0], f"R4b {w}x{h}{hs}: double tap start practice -> {st}")
            await pg.evaluate("lessonBack(); lessonBack && 0; renderHome(); show('home')")
            await pg.evaluate("$('openSettings').click()"); await pg.wait_for_timeout(450)
            before = await pg.evaluate("settings.highlightSame")
            await pg.click(".set-row:has([data-key=highlightSame]) b")
            check(await pg.evaluate("settings.highlightSame") != before, f"R4b {w}x{h}{hs}: tapping the row text should toggle")
            check(not errs, f"R4b errors {errs}")
            await ctx.close()

        # 第 5 轮：快速连点相邻的数字键/格子不被防双击吞掉
        for w in (320, 360, 393):
            ctx, pg, errs = await fresh(b, w, 760)
            await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[8]}); G.noteMode = true; render()")
            for d in (1, 2, 3, 4):
                bb = await pg.locator(f'#pad .key[data-d="{d}"]').bounding_box()
                await pg.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2); await pg.wait_for_timeout(150)
            check(await pg.evaluate(f"G.notes[{e[8]}]") == 0b1111, f"R5 {w}: quick adjacent keys swallowed, notes={await pg.evaluate(f'G.notes[{e[8]}]')}")
            await pg.evaluate("G.noteMode = false; render()")
            c0 = await pg.evaluate("cells[40].getBoundingClientRect().toJSON()")
            c1 = await pg.evaluate("cells[41].getBoundingClientRect().toJSON()")
            await pg.mouse.click(c0["x"] + c0["width"] / 2, c0["y"] + c0["height"] / 2); await pg.wait_for_timeout(150)
            await pg.mouse.click(c1["x"] + c1["width"] / 2, c1["y"] + c1["height"] / 2); await pg.wait_for_timeout(50)
            check(await pg.evaluate("sel") == 41, f"R5 {w}: quick adjacent cell swallowed, sel={await pg.evaluate('sel')}")
            await ctx.close()
        # 弹层打开时首页滚动位置不丢（真实 App 里 html, body 是 height:100%）
        ctx, pg, errs = await fresh(b, 360, 640)
        await pg.evaluate("for (let k = 1; k < 60; k++) PROG[9].stars[k] = 3; progress = PROG[9]; renderHome(); window.scrollTo(0, 900)")
        y = await pg.evaluate("scrollY")
        await pg.evaluate("$('openSettings').click()"); await pg.wait_for_timeout(200)
        y1 = await pg.evaluate("scrollY")
        await pg.evaluate("$('setClose').click()"); await pg.wait_for_timeout(200)
        y2 = await pg.evaluate("scrollY")
        check(y > 0 and y1 == y and y2 == y, f"R5: home scroll lost when opening settings {y} {y1} {y2}")
        await ctx.close()
        # 窄屏（安卓“显示大小”调大）不横向溢出
        for w in (260, 280, 300):
            for mode in (9, 6):
                ctx, pg, errs = await fresh(b, w, 600, "#fs=1.30")
                await pg.evaluate(f"HM = {mode}; progress = PROG[HM]; renderHome()")
                r = [await pg.evaluate("document.documentElement.scrollWidth")]
                await pg.evaluate("startLevel(1); hideTip()"); r.append(await pg.evaluate("document.documentElement.scrollWidth"))
                check(max(r) <= w, f"R5: {w}px large {mode}x{mode} overflow {r}")
                await ctx.close()

        # 第 5 轮（慢速双击、窄屏）
        ctx, pg, errs = await fresh(b, 360, 640, "#fs=1.30")
        await pg.evaluate(f"startLevel(1); hideTip(); G.val = '{sol}'.split('').map(Number); after()")
        await pg.wait_for_timeout(1200)
        bb = await pg.locator("#winHome").bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
        await pg.mouse.click(x, y); await pg.wait_for_timeout(550); await pg.mouse.click(x, y); await pg.wait_for_timeout(100)
        check(await pg.evaluate("$('home').classList.contains('on') && G === null"), "R5: slow double tap on back-to-levels started a level")
        # 单步练习：双击“下一题”只前进一题；已经划掉的候选数再点不报红
        await pg.evaluate("openTech(); openDrill(3, 0); lastTap = null"); await pg.wait_for_timeout(700)
        await pg.dblclick("#tBtnB"); await pg.wait_for_timeout(100)
        check(await pg.evaluate("T.j") == 1, f"R5: double tap next drill -> j={await pg.evaluate('T.j')}")
        r = await pg.evaluate("""() => { const x = T.insts[0], [c, d] = x.elim[0]; T.sel = c; tinput(d); tinput(d); return [T.cls, T.msg]; }""")
        check(r[0] == "ok" or "完成" in r[1], f"R5: repeated elimination shows error {r}")
        await ctx.close()
        for w in (260, 280, 300, 320):
            ctx, pg, errs = await fresh(b, w, 600, "#fs=1.30")
            await pg.evaluate("openTech(); startPractice(9, 0)")
            hb = await pg.evaluate("[$('gTitle').getBoundingClientRect().top, $('gTier').getBoundingClientRect().height]")
            check(hb[0] >= 0 and hb[1] < 30, f"R5 {w}: practice title wraps/clipped {hb}")
            await pg.evaluate(f"goHome(); startLevel(1); hideTip(); const i = G.val.indexOf(0); G.notes[i] = 511; ({SEL})(i)")
            check(await pg.evaluate("document.documentElement.scrollWidth") <= w, f"R5 {w}: 9 notes overflow")
            await ctx.close()
            ctx, pg, errs = await fresh(b, w, 600)
            await pg.evaluate("startLevel(1); hideTip(); toast('这一步需要更复杂的推理，直接告诉你答案')"); await pg.wait_for_timeout(300)
            tb = await pg.evaluate("$('toast').getBoundingClientRect().toJSON()")
            check(tb["left"] >= 0 and tb["right"] <= w, f"R5 {w}: normal toast clipped {tb['left']}..{tb['right']}")
            await ctx.close()

        # 第 5 轮（防双击不能误拦正常操作）
        for w, h, hs in ((360, 640, ""), (393, 852, ""), (360, 640, "#fs=1.30")):
            ctx, pg, errs = await fresh(b, w, h, hs)
            async def tap(sel_):
                bb = await pg.locator(sel_).bounding_box(); await pg.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
            await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[9]})")
            # 确认后 600ms 内的“下一步”当作慢速双击拦掉（第 8 轮）；650ms 后的要生效
            await pg.evaluate("window.__tc2 = []; document.addEventListener('click', e => { if (e.target.closest && e.target.closest('#hpNext')) __tc2.push(e.timeStamp); }, true)")
            await tap("#tHint"); await pg.wait_for_timeout(300); await tap("#hpNext"); await pg.wait_for_timeout(500); await tap("#hpNext")
            st = await pg.evaluate("H && [H.i, H.list.length, __tc2[1] - __tc2[0]]")
            check(st and (st[0] == 0 or st[2] >= 600), f"R8 {w}{hs}: slow double (500ms) on confirm skipped step 1 {st}")   # 机器忙时实际间隔可能超过 600ms
            if st and st[0] == 0: await pg.wait_for_timeout(150); await tap("#hpNext")
            st = await pg.evaluate("H && [H.i, H.list.length]")
            check(st and (st[0] == 1 or st[1] == 1), f"R5c {w}{hs}: next after confirm (670ms) swallowed {st}")
            await pg.evaluate("H.i = H.list.length - 2 < 0 ? 0 : H.list.length - 2; render(); renderHint(); lastTap = null")
            if await pg.evaluate("H.list.length") > 1:
                await tap("#hpNext"); await pg.wait_for_timeout(500); await tap("#hpNext")
            else:
                await tap("#hpNext")
            await pg.wait_for_timeout(100)
            check(await pg.evaluate("!H"), f"R5c {w}{hs}: fill after last next (500ms) swallowed")
            # 提示面板开着时连点撤销两下
            hist = await pg.evaluate(f"({SEL})({e[10]}); pad.children[0].click(); pad.children[1].click(); G.history.length")
            await pg.evaluate("$('tHint').click()"); await pg.wait_for_timeout(100)
            covered = await pg.evaluate("(() => { const r = $('tUndo').getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !$('tUndo').contains(t) || !!shifted; })()")   # 页面被推上去时第一下只关面板（第 10 轮）
            await tap("#tUndo"); await pg.wait_for_timeout(300); await tap("#tUndo"); await pg.wait_for_timeout(100)
            if not covered:   # 提示面板没盖住撤销键时，两下都要生效（盖住时第一下点的是面板按钮）
                check(await pg.evaluate("G.history.length") == hist - 2, f"R5c {w}{hs}: second undo swallowed")
            # 取消提示后 650ms 点数字键
            await pg.evaluate(f"({SEL})({e[11]})")
            await tap("#tHint"); await pg.wait_for_timeout(300)
            bb = await pg.locator("#hpClose").bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            await pg.mouse.click(x, y); await pg.wait_for_timeout(650); await pg.mouse.click(x, y); await pg.wait_for_timeout(100)
            check(await pg.evaluate("$('hpanel').classList.contains('on') === false"), f"R5c {w}{hs}: cancel")
            await ctx.close()
        # 通关面板弹出 500ms 后点“下一关”有效
        ctx, pg, errs = await fresh(b, 393, 852)
        await pg.evaluate(f"startLevel(1); hideTip(); G.val = '{sol}'.split('').map(Number); after()")
        await pg.wait_for_timeout(350 + 500); await pg.click("#winNext"); await pg.wait_for_timeout(100)
        check(await pg.evaluate("G && G.n === 2"), "R5c: next level 500ms after win sheet swallowed")
        await ctx.close()

        # 第 6 轮：600ms 的慢速双击也不穿透；大字开关双击不拨到别的开关；宽按钮另一头的第二下也算同一位置
        for w, h, hs in ((360, 640, ""), (320, 568, "#fs=1.30"), (393, 852, "")):
            ctx, pg, errs = await fresh(b, w, h, hs)
            # 机器忙时两下的实际间隔会超过 650ms（那样本来就不该拦）：量出页面里真实的间隔，超了就重来
            await pg.evaluate("document.addEventListener('click', e => { if (window.__tc) __tc.push(e.timeStamp); }, true)")
            async def dbl2(sel_, gap, dx=0, reset=None):
                for _ in range(4):
                    await pg.evaluate("window.__tc = []")
                    bb = await pg.locator(sel_).bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
                    await pg.mouse.click(x, y); await pg.wait_for_timeout(gap); await pg.mouse.click(x + dx, y); await pg.wait_for_timeout(80)
                    real = await pg.evaluate("__tc.length >= 2 ? __tc[__tc.length - 1] - __tc[0] : 0")
                    if real < 640 or not reset: return real
                    await reset(); await pg.wait_for_timeout(800)
                return real
            await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[12]})")
            st0 = await pg.evaluate(f"[G.val[{e[12]}], G.mistakes]")
            async def re_hint(): await pg.evaluate("closeHintPanel(); $('tHint').click()"); await pg.wait_for_timeout(100)
            await pg.evaluate("$('tHint').click()"); await pg.wait_for_timeout(100)
            await dbl2("#hpClose", 600, reset=re_hint)
            check(await pg.evaluate(f"[G.val[{e[12]}], G.mistakes]") == st0, f"R6 {w}{hs}: slow double on hint close leaked")
            await pg.evaluate("$('openSettings2').click()"); await pg.wait_for_timeout(200)
            async def re_set(): await pg.evaluate("document.querySelectorAll('.sheet-bg.on').forEach(b => closeSheet(b.id)); $('openSettings2').click()"); await pg.wait_for_timeout(200)
            await dbl2("#setDone", 600, reset=re_set)
            check(not await pg.evaluate("$('setSheet').classList.contains('on')"), f"R6 {w}{hs}: slow double on done reopened settings")
            await pg.wait_for_timeout(700)
            lg = await pg.evaluate("settings.large")
            async def re_gear(): await pg.evaluate("document.querySelectorAll('.sheet-bg.on').forEach(b => closeSheet(b.id))")
            real = await dbl2("#openSettings2", 600, reset=re_gear)
            st = await pg.evaluate("[$('setSheet').classList.contains('on'), settings.large]")
            check(st == [True, lg] or real >= 640, f"R6 {w}{hs}: slow double on gear -> {st}")   # 机器太忙、四次都超过 650ms 时不算
            await pg.evaluate("if (!$('setSheet').classList.contains('on')) $('openSettings2').click()")
            await pg.wait_for_timeout(700)
            snap = await pg.evaluate("JSON.stringify(settings)")
            await dbl2(".switch[data-key=large]", 150)
            after_ = await pg.evaluate("JSON.parse(JSON.stringify(settings))")
            before = __import__("json").loads(snap)
            others = [k for k in before if k != "large" and before[k] != after_[k]]
            check(after_["large"] != before["large"] and not others, f"R6 {w}{hs}: double tap on large toggled {others or 'large twice'}")
            await pg.evaluate("closeSheet('setSheet')")
            await ctx.close()
        # 宽按钮（继续）：第二下点在另一头、隔 600ms，提醒仍在
        ctx, pg, errs = await fresh(b, 393, 852)
        bb = await pg.locator("#continueBtn").bounding_box(); x, y = bb["x"] + bb["width"] * 0.25, bb["y"] + bb["height"] / 2
        await pg.mouse.click(x, y); await pg.wait_for_timeout(600); await pg.mouse.click(x + bb["width"] * 0.5, y); await pg.wait_for_timeout(80)
        check(await pg.evaluate("$('game').classList.contains('on') && $('tipPanel').classList.contains('on') && sel === -1"), "R6: wide-button second tap leaked")
        await ctx.close()
        # 技巧练习：看讲解后双击返回，不会直接退出课程；回到题目后双击“下一题”只前进一题
        ctx, pg, errs = await fresh(b, 360, 640)
        await pg.evaluate("openTech(); openDrill(2, 0); lastTap = null"); await pg.wait_for_timeout(700)
        await pg.click("#tBtnA"); await pg.wait_for_timeout(700)
        bb = await pg.locator("#lessonBack").bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
        await pg.mouse.click(x, y); await pg.wait_for_timeout(300); await pg.mouse.click(x, y); await pg.wait_for_timeout(80)
        check(await pg.evaluate("$('lesson').classList.contains('on') && T && T.mode === 'drill' && !T.frames"), "R6: double tap back in explanation left the lesson")
        await ctx.close()

        # 第 7 轮：窄屏大字模式技巧列表按钮不换行
        for w in (260, 280, 300):
            ctx, pg, errs = await fresh(b, w, 600, "#fs=1.30")
            await pg.evaluate("openTech()")
            n = await pg.evaluate("[...document.querySelectorAll('.lcard-btns .lbtn')].filter(x => x.scrollHeight > x.clientHeight + 1).length")
            check(n == 0, f"R7 {w}: {n} lesson buttons overflow")
            await ctx.close()

        # 家人反馈：提示让人删笔记里本来没有的数。现在提示按玩家的笔记推理
        ctx, pg, errs = await fresh(b)
        r = await pg.evaluate("""() => {
          for (let k = 1; k < 70; k++) PROG[9].stars[k] = 3; progress = PROG[9];
          const out = [];
          for (const n of [50, 60, 70]) {
            startLevel(n); hideTip(); lastTap = null;
            // 用提示推到中盘，再给每个空格记上“删掉了一个不可能的数”的笔记
            for (let g = 0; g < 8; g++) { H = null; HC = null; G.hints = 0; runHint(-1, true); if (H) { H.i = H.list.length - 1; $('hpNext').click(); } }
            const b = SE.basicCands(G.val);
            for (let i = 0; i < 81; i++) if (!G.val[i]) { let m = b[i]; for (let d = 1; d <= 9; d++) if (d !== G.sol[i] && (m >> (d - 1)) & 1) { m &= ~(1 << (d - 1)); break; } G.notes[i] = m; }
            H = null; HC = null; G.hints = 0; G.hsig = ""; render();
            $('tHint').click(); $('hpNext').click();
            if (!H) { out.push([n, 'no chain']); continue; }
            const notes = G.notes.slice();
            let bad = 0;
            H.list.forEach(it => it.f.strike.forEach(([c, d]) => { if (notes[c] && !((notes[c] >> (d - 1)) & 1)) bad++; }));
            H.list.forEach(it => { for (let i = 0; i < 81; i++) if (notes[i] && (it.cand[i] & ~notes[i])) bad++; });
            const h0 = G.hints;
            // 改了笔记后再点提示：按新笔记重新讲，不再扣次数
            const tp = H.place.slice(); closeHintPanel(); const j = G.val.indexOf(0); G.notes[j] = b[j]; render();
            $('tHint').click();
            // 讲的还是同一格：按新笔记免费重讲；换了一格：付过的那一格还空着，先免费填上它（第 11 轮）
            out.push([n, bad, G.hints === h0, (H && H.open && H.nsig === G.notes.join()) || G.val[tp[0]] === tp[1]]);
          }
          return out;
        }""")
        check(all(x[1] == 0 and x[2] and x[3] for x in r if x[1] != 'no chain'), f"notes-aware hint: {r}")
        check(not errs, f"notes-aware hint errors {errs}")
        await ctx.close()

        # ---------- 第 8 轮 ----------
        ctx, pg, errs = await fresh(b)
        r = await pg.evaluate("""() => {
          const o = {};
          for (let k = 1; k < 60; k++) PROG[9].stars[k] = 3; progress = PROG[9]; store.set('progress', progress);
          startLevel(55); hideTip(); lastTap = null;
          const e = G.val.indexOf(0); sel = e; G.notes[e] = 0; render();
          const peerNoted = GM.PEERS[e].find(j => !G.val[j]);
          G.notes[peerNoted] = SE.basicCands(G.val)[peerNoted];
          $('tHint').click(); o.confirmStar = /最多得 2 星/.test($('hpText').textContent);
          $('hpNext').click();
          // 讲解时：不画选中格、十字和相同数字；数字键变淡；目标格用主题色框
          o.noSel = !document.querySelector('#board .cell.sel, #board .cell.zone, #board .cell.same') && sel === -1;
          o.dim = pad.classList.contains('dim');
          const t = document.querySelector('#board .cell.h-tgt');
          o.tgtColor = !t || getComputedStyle(t).boxShadow.indexOf(getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() ? '' : 'x') >= 0;
          o.tgtNotRed = !t || getComputedStyle(t).backgroundColor !== getComputedStyle(document.querySelector('#board .cell')).getPropertyValue('--error-soft');
          // 记了笔记的空格显示这一步的候选数
          const it = H.list[H.i];
          o.candShown = [...cells[peerNoted].querySelectorAll('.notes span')].map(s => s.textContent).join('') === SE.digs ? true :
            [...cells[peerNoted].querySelectorAll('.notes span')].map(s => s.textContent).join('') === [1,2,3,4,5,6,7,8,9].filter(d => (it.cand[peerNoted] >> (d - 1)) & 1).join('');
          // 填入：讲解里划掉的数也从笔记里划掉；撤销恢复，并回到原来的选中格
          for (let i = 0; i < 81; i++) if (!G.val[i]) G.notes[i] = SE.basicCands(G.val)[i];
          H = null; HC = null; G.hsig = ""; render(); $('tHint').click(); $('hpNext').click();
          const elim = [].concat(...H.steps.map(st => st.inst.elim || []));
          const n0 = G.notes.slice();
          H.i = H.list.length - 1; $('hpNext').click();
          o.elimApplied = elim.every(([c, d]) => G.val[c] || !((G.notes[c] >> (d - 1)) & 1));
          o.elimCount = elim.length;
          undo(); o.undoNotes = G.notes.join() === n0.join();
          return o;
        }""")
        check(r["confirmStar"], f"R8 confirm text without star cost {r}")
        check(r["noSel"] and r["dim"] and r["tgtNotRed"] and r["candShown"], f"R8 hint display {r}")
        check(r["elimApplied"] and r["undoNotes"], f"R8 fill should strike explained candidates from notes {r}")
        # 标出错误关着、盘面上有填错的数（没选中）：提示先改正它
        r = await pg.evaluate("""() => {
          startLevel(55); hideTip(); lastTap = null; settings.showErrors = false;
          const e = G.val.findIndex((x, i) => !x); const bad = G.sol[e] % 9 + 1;
          G.val[e] = bad; sel = -1; G.hints = 0; render();
          $('tHint').click(); const txt = $('hpText').textContent; $('hpNext').click();
          const o = [/如果盘面上有不对的数/.test(txt), G.val[e] === G.sol[e], G.hints === 1, !H, /填错了/.test($('toast').textContent)];
          settings.showErrors = true; return o;
        }""")
        check(all(r), f"R8 hint fixes an unselected wrong cell first {r}")
        # 改了笔记、讲解换了一格：算新的提示（要确认、扣次数）
        r = await pg.evaluate("""() => {
          startLevel(55); hideTip(); lastTap = null; G.hints = 0;
          let tries = 0, ok = null;
          for (let t = 0; t < 30 && ok === null; t++) {
            H = null; HC = null; G.hsig = ""; G.hpaid = []; for (let i = 0; i < 81; i++) G.notes[i] = 0; render();
            $('tHint').click(); $('hpNext').click(); const p0 = H.place.slice(), h0 = G.hints; closeHintPanel();
            // 给目标格以外的某个空格记上只剩答案的笔记：常常会换成先讲那一格
            const j = G.val.findIndex((x, i) => !x && i !== p0[0] && i > t); if (j < 0) break;
            G.notes[j] = 1 << (G.sol[j] - 1); render();
            $('tHint').click();
            const c = chainNow();
            if (c.r.place[0] !== p0[0]) ok = [!!HC, G.hints === h0]; else ok = null;
            HC = null; G.hints = 0;
          }
          return ok;
        }""")
        check(r is None or r == [True, True], f"R8 changed notes, different cell should be a new hint {r}")
        # 笔记模式存档；数字键数到了只变淡；没选格子擦除有提示；Ctrl+Shift+Z 撤销
        await pg.evaluate("startLevel(55); hideTip(); const e = G.val.indexOf(0); sel = e; G.noteMode = false; input(G.sol[e]); $('tNote').click()")
        await pg.reload(); await pg.wait_for_timeout(200)
        check(await pg.evaluate("G && G.n === 55 && G.noteMode === true && $('tNote').classList.contains('on')"), "R8 note mode not restored after reload")
        r = await pg.evaluate("""() => {
          hideTip(); G.noteMode = false; settings.showErrors = false; render();
          const d = 1; const left = () => +pad.children[0].querySelector('small').textContent || 0;
          // 用一个填错的 1 把数字 1 的剩余数凑到 0
          let n = left(); for (let i = 0; i < 81 && n > 0; i++) if (!G.val[i]) { G.val[i] = 1; n--; }
          render();
          const k = pad.children[0], o = [k.classList.contains('used'), !k.classList.contains('done'), getComputedStyle(k).visibility === 'visible'];
          settings.showErrors = true; render(); return o;
        }""")
        check(all(r), f"R8 key with count 0 should stay tappable when errors are hidden {r}")
        r = await pg.evaluate("""() => {
          startLevel(55); hideTip(); sel = -1; render(); $('tErase').click();
          const t = $('toast').textContent;
          const e = G.val.indexOf(0); sel = e; G.noteMode = false; input(G.sol[e]);
          document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Z', ctrlKey: true, shiftKey: true }));
          return [t === '先选一个格子', G.val[e] === 0];
        }""")
        check(all(r), f"R8 erase without selection / Ctrl+Shift+Z {r}")
        # 通关面板：标出错误关着时不显示错误一栏；重玩成绩变差时说明保留原来的星级
        r = await pg.evaluate("""() => {
          settings.showErrors = false; PROG[9].stars[3] = 3; progress = PROG[9];
          startLevel(3); hideTip(); G.hints = 1; G.val = PUZZLES[2].s.split('').map(Number); after();
          const o = [$('winErr').parentNode.hidden, $('winTip').textContent];
          settings.showErrors = true; closeSheet('winSheet'); return o;
        }""")
        check(r[0] and "这次 2 星，之前的 3 星成绩保留" in r[1], f"R8 win panel {r}")
        # 首页：有存档的关卡标“进行中”；全部通关后的副标题
        r = await pg.evaluate("""() => {
          goHome(); startLevel(4); hideTip(); const e = G.val.indexOf(0); sel = e; G.noteMode = false; input(G.sol[e]); goHome();
          const t = document.querySelector('.lv[data-n="4"] .bt').textContent;
          for (let k = 1; k <= 100; k++) { PROG[9].stars[k] = 3; store.del('game.' + k); } progress = PROG[9]; renderHome();
          return [t, $('continueSub').textContent, $('homeSub').querySelectorAll('span').length];
        }""")
        check(r == ["进行中", "重玩第 100 关", 2], f"R8 home {r}")
        # 第 1 关提醒说明小数字；X-Wing 不在连字符后断行
        r = await pg.evaluate("""() => { store.del('tip.1'); PROG[9].stars = {}; progress = PROG[9]; startLevel(1);
          return [/小数字/.test($('tipText').textContent), wj('X-Wing') !== 'X-Wing']; }""")
        check(all(r), f"R8 tips {r}")
        await ctx.close()
        # 技巧练习
        ctx, pg, errs = await fresh(b)
        r = await pg.evaluate("""() => {
          const o = {};
          // 宫内排除课：填了正确答案、但不是本课方法能推出的格子：中性说明，不报红
          openDrill(1, 0); const st = T.st, sol = drillSol();
          const okCells = new Set(T.insts.map(x => x.place[0]));
          const i = st.val.findIndex((v, j) => !v && !okCells.has(j) && (st.cand[j] >> (sol[j] - 1)) & 1);
          if (i >= 0) { T.sel = i; tinput(sol[i]); o.neutral = /确实是这一格的答案/.test(T.msg) && T.cls === ''; } else o.neutral = true;
          // 看讲解后回到题目：恢复任务说明
          T.sel = st.val.findIndex(v => !v); tinput(9); $('tBtnA').click(); o.title = $('tStep').textContent;
          $('tBtnA').click(); for (let k = 0; k < 20 && T.frames; k++) $('tBtnB').click();
          o.task = T.msg === SE.LESSONS[1].task;
          // 第 10 题做完再按数字：说点“完成”
          openDrill(1, 9); const x = T.insts[0]; T.sel = x.place[0]; tinput(x.place[1]); tinput(1); o.done10 = /点“完成”/.test(T.msg);
          openDrill(1, 9); o.before = /做对过/.test($('lSub').textContent);
          return o;
        }""")
        check(r["neutral"] and r["task"] and r["done10"] and r["before"] and (r["title"] == "这一题的推理" or r["title"].startswith("第 1 步")), f"R8 drills {r}")
        # 唯一候选数课的整题：提示讲的是本课方法
        r = await pg.evaluate("""() => { startPractice(0, 0); hideTip(); $('tHint').click(); return H && H.steps[0].inst.t; }""")
        check(r == "naked_single", f"R8 practice hint should use the lesson technique, got {r}")
        check(not errs, f"R8 errors {errs}")
        await ctx.close()

        # ---------- 第 9 轮 ----------
        ctx, pg, errs = await fresh(b)
        r = await pg.evaluate("""() => {
          const o = {};
          for (let k = 1; k < 60; k++) PROG[9].stars[k] = 3; progress = PROG[9]; store.set('progress', progress);
          startLevel(1); hideTip(); lastTap = null;
          // 1) 讲解没用到、笔记漏了答案的格子：照样显示玩家自己的笔记
          const c0 = chainNow(); const used = new Set(); H = null;
          c0.r.steps.forEach(st => st.frames.forEach(f => [...f.pat, ...f.tgt, ...f.no, ...f.strike.map(x => x[0]), ...f.mark.map(x => x[0])].forEach(x => used.add(x))));
          used.add(c0.r.place[0]);
          const j = G.val.findIndex((x, i) => !x && !used.has(i));
          const wrongNote = SE.basicCands(G.val)[j] & ~(1 << (G.sol[j] - 1)) || (1 << (G.sol[j] % 9));
          G.notes[j] = wrongNote; render();
          $('tHint').click(); $('hpNext').click();
          const shown = [...cells[j].querySelectorAll('.notes span')].map(s => s.textContent).join('');
          o.lostHidden = shown === GM.digits.filter(d => (wrongNote >> (d - 1)) & 1).join('');
          // 2) 关闭讲解回到原来选中的格子；讲解开着时点数字键只关掉讲解
          closeHintPanel(); sel = 10; render(); $('tHint').click(); o.selCleared = sel === -1;
          $('hpClose').click(); o.selBack = sel === 10;
          $('tHint').click(); const v0 = G.val.join(); pad.children[0].click(); o.keyOnlyCloses = G.val.join() === v0 && !(H && H.open) && sel === 10;
          // 3) 付过的目标：关掉不填、自己填了别的格子，再点提示不扣
          const h0 = G.hints, tgt = H.place;
          const k = G.val.findIndex((x, i) => !x && i !== tgt[0]); sel = k; G.noteMode = false; input(G.sol[k]);
          $('tHint').click(); o.paidAgain = !HC && G.hints === h0 && H && H.open && H.place[0] === tgt[0];
          closeHintPanel();
          // 改正错格后撤销，再改同一格不扣
          const e = G.val.findIndex(x => !x); sel = e; input(G.sol[e] % 9 + 1);
          $('tHint').click(); $('hpNext').click(); const h1 = G.hints;
          undo(); $('tHint').click(); o.fixAgain = !HC && G.hints === h1 && G.val[e] === G.sol[e];
          return o;
        }""")
        check(all(r.values()), f"R9 hint {r}")
        # 4) 笔记里的过期数字有说明；“放不了”的格子用斜线
        r = await pg.evaluate("""() => {
          startLevel(46); hideTip(); lastTap = null; G.hints = 0; G.hpaid = [];
          const b = SE.basicCands(G.val);
          for (let i = 0; i < 81; i++) if (!G.val[i]) G.notes[i] = 511;   // 全记 1–9：大多含过期数字
          render(); $('tHint').click(); $('hpNext').click();
          const t = H.list[0].f.text;
          let no = false;
          for (let n of [1, 2, 3, 21, 25]) { startLevel(n); hideTip(); G.hpaid = []; G.hints = 0; for (let g = 0; g < 6 && !no; g++) { H = null; HC = null; const c = chainNow(); if (c.r.steps.some(st => st.frames.some(f => f.no.length))) no = true; else { G.val[c.r.place[0]] = c.r.place[1]; } } }
          return [/填过了，讲解时不算/.test(t), no];
        }""")
        check(all(r), f"R9 stale note / no-cells {r}")
        # 5) 首页“进行中”：只点了格子、计了时的不算；只开了笔记模式也记得
        r = await pg.evaluate("""() => {
          goHome(); startLevel(3); hideTip(); sel = 0; G.started = true; G.time = 9; save(); goHome();
          const t = document.querySelector('.lv[data-n="3"] .bt').textContent;
          startLevel(5); hideTip(); $('tNote').click(); goHome(); startLevel(5); const nm = G.noteMode; goHome();
          return [t !== '进行中', nm];
        }""")
        check(all(r), f"R9 home in-progress / note mode {r}")
        # 6) 6×6 第 1 关的操作说明；第 1 关提醒跟着大字模式变
        r = await pg.evaluate("""() => {
          HM = 6; progress = PROG[6]; startLevel(1); const a = $('tipPanel').classList.contains('on') && /6×6/.test($('tipText').textContent) && $('tipGo').hidden;
          goHome(); HM = 9; progress = PROG[9]; store.del('tip.1'); PROG[9].stars = {}; startLevel(1);
          const before = /长按/.test($('tipText').textContent);
          $('openSettings2').click(); document.querySelector('.switch[data-key=large]').click(); closeSheet('setSheet');
          const after = /“笔记”按钮/.test($('tipText').textContent);
          document.querySelector('.switch[data-key=large]').click();
          return [a, before, after, !$('tipGo').hidden];
        }""")
        check(all(r), f"R9 tips {r}")
        # 7) 单步练习做对后显示 ✓；整题里的“重新开始这一题”
        r = await pg.evaluate("""() => {
          openDrill(0, 3); const x = T.insts[0]; T.sel = x.place[0]; tinput(x.place[1]); const ok = / ✓$/.test($('lSub').textContent);
          startPractice(0, 0); hideTip(); $('openSettings2').click(); const t = $('restartBtn').textContent; closeSheet('setSheet');
          return [ok, t === '重新开始这一题'];
        }""")
        check(all(r), f"R9 practice texts {r}")
        check(not errs, f"R9 errors {errs}")
        await ctx.close()
        # 8) 笔记模式下慢速双击同一个数字键：笔记不被马上删掉
        ctx, pg, errs = await fresh(b)
        await pg.evaluate(f"startLevel(1); hideTip(); G.noteMode = true; render(); ({SEL})(G.val.indexOf(0))")
        kb = await pg.locator('#pad .key[data-d="3"]').bounding_box()
        await pg.mouse.click(kb["x"] + kb["width"] / 2, kb["y"] + kb["height"] / 2); await pg.wait_for_timeout(350)
        await pg.mouse.click(kb["x"] + kb["width"] / 2, kb["y"] + kb["height"] / 2); await pg.wait_for_timeout(50)
        check(await pg.evaluate("(G.notes[sel] >> 2) & 1") == 1, "R9 slow double tap removed the note")
        await pg.wait_for_timeout(700)
        await pg.mouse.click(kb["x"] + kb["width"] / 2, kb["y"] + kb["height"] / 2)
        check(await pg.evaluate("(G.notes[sel] >> 2) & 1") == 0, "R9 deliberate second tap should remove the note")
        # 9) 大字模式：慢速双击齿轮，第二下落在“大字模式”上不关掉它
        await pg.evaluate("settings.large = true; applyLarge(); fitBoard(); render()")
        gb = await pg.locator("#openSettings2").bounding_box()
        await pg.mouse.click(gb["x"] + gb["width"] / 2, gb["y"] + gb["height"] / 2); await pg.wait_for_timeout(720)
        rb = await pg.evaluate("(() => { const r = document.querySelector('.switch[data-key=large]').closest('.set-row').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()")
        await pg.mouse.click(rb[0], rb[1]); await pg.wait_for_timeout(50)
        check(await pg.evaluate("settings.large === true"), "R9 slow double on gear turned large mode off")
        await ctx.close()
        # 10) 大字模式的棋盘不比普通模式小；小屏确认框的文字全露出来
        for w, h in ((412, 720), (393, 660), (360, 640), (430, 800)):
            sizes = []
            for hs in ("", "#fs=1.30"):
                ctx, pg, errs = await fresh(b, w, h, hs)
                await pg.evaluate("startLevel(1); hideTip()")
                sizes.append(await pg.evaluate("[board.getBoundingClientRect().width, document.documentElement.scrollHeight]"))
                if hs:
                    await pg.evaluate("$('tHint').click()"); await pg.wait_for_timeout(300)
                    t = await pg.evaluate("[$('hpText').scrollHeight, $('hpText').clientHeight]")
                    check(t[0] <= t[1] + 2, f"R9 {w}x{h}: confirm text cut {t}")
                await ctx.close()
            check(sizes[1][0] >= sizes[0][0] and sizes[0][1] <= h and sizes[1][1] <= h, f"R9 {w}x{h}: board normal/large {sizes}")

        # ---------- 第 10 轮 ----------
        ctx, pg, errs = await fresh(b, 360, 640, "#fs=1.30")
        r = await pg.evaluate("""() => {
          const o = {};
          for (let k = 1; k < 60; k++) PROG[9].stars[k] = 3; progress = PROG[9]; store.set('progress', progress);
          // 1) 讲解翻页时棋盘不跳
          startLevel(46); hideTip(); for (let i = 0; i < 81; i++) if (!G.val[i]) G.notes[i] = SE.basicCands(G.val)[i]; render();
          $('tHint').click(); const t0 = gwrap.style.transform; $('hpNext').click();
          const ts = [t0, gwrap.style.transform]; while (H.i < H.list.length - 1) { $('hpNext').click(); ts.push(gwrap.style.transform); }
          o.noJump = ts.slice(1).every(x => x === ts[1]);
          closeHintPanel(true); o.back = gwrap.style.transform === '';
          // 2) 没记笔记的“放不了”斜线格不显示候选数
          startLevel(1); hideTip(); G.notes = G.notes.map(() => 0); render(); $('tHint').click(); $('hpNext').click();
          while (H.i < H.list.length - 1 && !H.list[H.i].f.no.length) { $('hpNext').click(); }
          const nos = [...document.querySelectorAll('#board .cell.h-no')];
          o.noCand = nos.length > 0 && nos.every(c => ![...c.querySelectorAll('.notes span')].some(s => s.textContent));
          closeHintPanel(true);
          // 3) 面板开着时点数字键 / “笔记” / N：只关面板，回到原来的格子
          const e = G.val.indexOf(0); sel = e; render(); $('tHint').click(); pad.children[0].click(); o.digitClose = !HC && sel === e && !G.val[e];
          $('tHint').click(); $('hpNext').click(); $('tNote').click(); o.noteBack = sel === e; $('tNote').click();
          // 4) 笔记模式双击：删掉的笔记不马上加回来；擦除后重新记不算双击
          G.noteMode = true; G.notes[e] = 1 << 4; input.nt = null; render();
          input(5, true); input(5, true); o.delStays = !((G.notes[e] >> 4) & 1);
          input.nt = null; input(5, true); erase(); input(5, true); o.afterErase = !!((G.notes[e] >> 4) & 1);
          G.noteMode = false; render();
          return o;
        }""")
        check(all(r.values()), f"R10 hint/panel {r}")
        # 5) 页面推上去时点棋盘左上角：只关面板、选中格子，不会点到“返回”
        await pg.evaluate("startLevel(46); hideTip(); for (let i = 0; i < 81; i++) if (!G.val[i]) G.notes[i] = SE.basicCands(G.val)[i]; render(); $('tHint').click(); $('hpNext').click()")
        await pg.wait_for_timeout(700)
        check(await pg.evaluate("!!(H && H.open) && !!shifted"), "R10 setup: explanation should push the page up")
        c0 = await pg.evaluate("(() => { const r = cells[0].getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()")
        await pg.mouse.click(c0[0], c0[1]); await pg.wait_for_timeout(200)
        st = await pg.evaluate("[$('game').classList.contains('on'), $('setSheet').classList.contains('on'), sel]")
        check(st[0] and not st[1] and st[2] == 0, f"R10 tap through to back/settings {st}")
        # 提醒点棋盘关掉也算看过
        await pg.evaluate("goHome(); store.del('tip.1'); PROG[9].stars = {}; store.set('progress', PROG[9]); startLevel(1); sel = -1; pickCell({ target: cells[40], clientX: 0, clientY: 0 })")
        check(await pg.evaluate("store.get('tip.1', false) === true"), "R10 tip closed by tapping the board should count as seen")
        # 6) 难度提醒弹出时被回收，下次还会出现
        await pg.evaluate("goHome(); store.del('tip.1'); startLevel(1)")
        await pg.reload(); await pg.wait_for_timeout(200)
        check(await pg.evaluate("$('tipPanel').classList.contains('on') && $('tipStep').textContent === '怎么玩'"), "R10 tip lost after reload")
        await ctx.close()
        ctx, pg, errs = await fresh(b, 412, 760, "#fs=1.30")
        r = await pg.evaluate("""() => { startLevel(1); hideTip(); const sq = $('game').classList.contains('squeeze');
          sel = 0; G.started = true; G.time = 9; save(); goHome(); const t = $('continueText').textContent;
          return [sq, t]; }""")
        check(r == [False, "开始第 1 关"], f"R10 squeeze / continue {r}")
        r = await pg.evaluate("""() => { settings.large = false; applyLarge(); toast('盘面填满了，但还有错误。可以点提示改正，或在设置里打开“标出错误”看是哪一格');
          const b = $('toast').getBoundingClientRect(); return [b.left >= 0, b.right <= innerWidth]; }""")
        check(all(r), f"R10 long toast cut {r}")
        check(not errs, f"R10 errors {errs}")
        await ctx.close()

        # ---------- 第 11 轮 ----------
        ctx, pg, errs = await fresh(b)
        r = await pg.evaluate("""() => {
          const o = {};
          for (let k = 1; k < 60; k++) PROG[9].stars[k] = 3; progress = PROG[9]; store.set('progress', progress);
          // 1) 关掉自动清理、笔记里有过期数字：讲解涉及的格子每一帧都不显示过期数字
          settings.autoClean = false; startLevel(25); hideTip();
          for (let i = 0; i < 81; i++) if (!G.val[i]) G.notes[i] = SE.basicCands(G.val)[i];
          for (let g = 0; g < 3; g++) { const c = chainNow(); if (!c.r.place) return { stuck: false, g, n: G.n, hint: JSON.stringify(c.r.stuck) }; G.val[c.r.place[0]] = c.r.place[1]; }
          render(); $('tHint').click(); $('hpNext').click();
          let bad = 0;
          for (H.i = 0; H.i < H.list.length; H.i++) { render();
            for (let i = 0; i < 81; i++) if (!G.val[i] && H.inv.has(i) && G.notes[i]) {
              const shown = [...cells[i].querySelectorAll('.notes span')].reduce((m, s, k) => m | (s.textContent ? 1 << k : 0), 0);
              if (shown & ~H.list[H.i].cand[i]) bad++; } }
          H.i = 0; o.noStale = bad === 0; closeHintPanel(); settings.autoClean = true;
          // 2) 付过还空着的目标：引擎换了一格时先免费填上
          startLevel(30); hideTip(); G.hints = 0; G.hpaid = [];
          $('tHint').click(); $('hpNext').click(); const t0 = H.place.slice(); closeHintPanel();
          const k = G.val.findIndex((x, i) => !x && i !== t0[0]); G.val[k] = G.sol[k]; render();
          $('tHint').click(); o.owed = G.hints === 1 && !HC && (G.val[t0[0]] === t0[1] || !!(H && H.open && H.place[0] === t0[0]));
          // 3) 提醒开着时清除全部进度，提醒还会再出现
          goHome(); store.del('tip.1'); PROG[9].stars = {}; startLevel(1);
          $('openSettings2').click(); $('resetBtn').click(); $('cfYes').click();
          o.tipBack = !store.get('tip.1', false);
          // 4) 设置里的“怎么玩”
          $('openSettings').click(); $('howBtn').click(); o.how = $('confirmSheet').classList.contains('on') && $('cfNo').hidden && /先点一个空格/.test($('cfText').textContent);
          closeSheet('confirmSheet');
          return o;
        }""")
        check(all(r.values()), f"R11 {r}")
        await ctx.close()
        # 5) 技巧练习说明框固定高度：翻页时“下一步”不动
        ctx, pg, errs = await fresh(b, 320, 568, "#fs=1.30")
        r = await pg.evaluate("""() => { openTeach(3); const ys = []; for (let k = 0; k < 4; k++) { ys.push(Math.round($('tBtnB').getBoundingClientRect().top)); $('tBtnB').click(); } return ys; }""")
        check(len(set(r)) == 1, f"R11 lesson buttons move {r}")
        # 6) 页面落回原位后 650ms 内的真实点击不算（双击格子第二下不会选到别的格子、不会点到返回）
        await pg.evaluate("for (let k = 1; k < 60; k++) PROG[9].stars[k] = 3; progress = PROG[9]; startLevel(46); hideTip(); for (let i = 0; i < 81; i++) if (!G.val[i]) G.notes[i] = SE.basicCands(G.val)[i]; render(); $('tHint').click(); $('hpNext').click()")
        await pg.wait_for_timeout(700)
        if await pg.evaluate("!!shifted"):
            c0 = await pg.evaluate("(() => { const r = cells[40].getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()")
            await pg.mouse.click(c0[0], c0[1]); await pg.wait_for_timeout(250); await pg.mouse.click(c0[0], c0[1]); await pg.wait_for_timeout(100)
            check(await pg.evaluate("$('game').classList.contains('on') && sel === 40"), f"R11 double tap after drop selected {await pg.evaluate('sel')}")
        check(not errs, f"R11 errors {errs}")
        await ctx.close()

        await b.close()
    print("FAIL:\n  " + "\n  ".join(fails) if fails else "review1 tests: all passed")
    sys.exit(1 if fails else 0)
asyncio.run(main())
