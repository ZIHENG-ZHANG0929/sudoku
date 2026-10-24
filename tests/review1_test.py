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
        check(await pg.evaluate("!!(HC && HC.wrongSel)"), "F: wrong-cell confirm expected")
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
        check("直接给出" in t and "填错" not in t, f"R2: confirm text {t}")
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
        check(all(x[0] == x[1] for x in cues) and any(x[0] for x in cues), f"R2: lesson cue mismatch {cues}")
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
            await tap("#tHint"); await pg.wait_for_timeout(300); await tap("#hpNext"); await pg.wait_for_timeout(500); await tap("#hpNext")
            st = await pg.evaluate("H && [H.i, H.list.length]")
            check(st and (st[0] == 1 or st[1] == 1), f"R5c {w}{hs}: next after confirm (500ms) swallowed {st}")
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
            covered = await pg.evaluate("(() => { const r = $('tUndo').getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !$('tUndo').contains(t); })()")
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
            async def dbl2(sel_, gap, dx=0):
                bb = await pg.locator(sel_).bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
                await pg.mouse.click(x, y); await pg.wait_for_timeout(gap); await pg.mouse.click(x + dx, y); await pg.wait_for_timeout(80)
            await pg.evaluate(f"startLevel(1); hideTip(); ({SEL})({e[12]})")
            st0 = await pg.evaluate(f"[G.val[{e[12]}], G.mistakes]")
            await pg.evaluate("$('tHint').click()"); await pg.wait_for_timeout(100)
            await dbl2("#hpClose", 600)
            check(await pg.evaluate(f"[G.val[{e[12]}], G.mistakes]") == st0, f"R6 {w}{hs}: slow double on hint close leaked")
            await pg.evaluate("$('openSettings2').click()"); await pg.wait_for_timeout(200)
            await dbl2("#setDone", 600)
            check(not await pg.evaluate("$('setSheet').classList.contains('on')"), f"R6 {w}{hs}: slow double on done reopened settings")
            await pg.wait_for_timeout(700)
            lg = await pg.evaluate("settings.large")
            await dbl2("#openSettings2", 600)
            st = await pg.evaluate("[$('setSheet').classList.contains('on'), settings.large]")
            check(st == [True, lg], f"R6 {w}{hs}: slow double on gear -> {st}")
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

        await b.close()
    print("FAIL:\n  " + "\n  ".join(fails) if fails else "review1 tests: all passed")
    sys.exit(1 if fails else 0)
asyncio.run(main())
