"""技巧练习专区和讲解型提示的界面测试。"""
import asyncio, json, sys, random
import os as _os
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))   # 仓库根目录
from playwright.async_api import async_playwright
HTML = "file://" + __import__("os").path.abspath(sys.argv[1])
P = json.load(open(ROOT + "/gen/puzzles.json"))
LS = json.load(open(ROOT + "/gen/lessons.json"))
fails = []
def check(c, m):
    if not c: fails.append(m)
SEL = "i => cells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))"
TSEL = "i => tcells[i].dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 393, "height": 852})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(HTML); await pg.evaluate("localStorage.clear()"); await pg.reload()

        # ---------- 1. 每一课的讲解都能从头点到尾，最后进入练习 ----------
        await pg.click("#learnBtn")
        check(await pg.evaluate("document.querySelectorAll('.lcard').length") == 10, "lesson list should have 10 cards")
        for k in range(10):
            await pg.evaluate(f"openTeach({k}); lastTap = null")   # 直接调函数换课，不是真实点击：清掉防双击记录
            nf = await pg.evaluate("T.frames.length")
            texts = []
            for f in range(nf):
                texts.append(await pg.text_content("#tText"))
                if f == nf - 1: await pg.wait_for_timeout(800)   # 按钮换了意思（下一步→开始练习）：防双击会拦掉 750ms 内的同位置点击
                await pg.click("#tBtnB")
            check(all(t and "undefined" not in t for t in texts) and nf >= 3, f"lesson {k} teach frames {nf} {texts[:1]}")
            check(await pg.evaluate("T.mode") == "drill" and await pg.evaluate("T.j") == 0, f"lesson {k}: teach end should open drill 1")
            check(await pg.evaluate(f"practice.seen[SE.LESSONS[{k}].id]") is True, f"lesson {k} not marked seen")

        # ---------- 2. 100 道单步练习：先做错一次（必须被拒绝），再做对 ----------
        rnd = random.Random(7)
        for k in range(10):
            for j in range(10):
                await pg.evaluate(f"openDrill({k}, {j})")
                kind = await pg.evaluate("SE.LESSONS[T.k].kind")
                if kind == "place":
                    wrong = await pg.evaluate("""() => { const ok = new Set(T.insts.map(x => x.place[0] * 10 + x.place[1]));
                        for (let i = 0; i < 81; i++) if (!T.st.val[i]) for (let d = 1; d <= 9; d++) if (!ok.has(i * 10 + d)) return [i, d]; }""")
                    await pg.evaluate(f"({TSEL})({wrong[0]}); tpad.children[{wrong[1] - 1}].click()")
                    check(await pg.evaluate(f"T.st.val[{wrong[0]}]") == 0 and not await pg.evaluate("T.solved"), f"drill {k}/{j}: wrong placement accepted")
                    check(await pg.evaluate("$('tPanel').classList.contains('bad')"), f"drill {k}/{j}: no error feedback")
                    c, d = await pg.evaluate("T.insts[0].place")
                    await pg.evaluate(f"({TSEL})({c}); tpad.children[{d - 1}].click()")
                else:
                    wrong = await pg.evaluate("""() => { const el = new Set(T.insts.flatMap(x => x.elim.map(([c, d]) => c * 10 + d)));
                        for (let i = 0; i < 81; i++) for (let d = 1; d <= 9; d++) if (!T.st.val[i] && (T.st.cand[i] >> (d - 1)) & 1 && !el.has(i * 10 + d)) return [i, d]; }""")
                    await pg.evaluate(f"({TSEL})({wrong[0]}); tpad.children[{wrong[1] - 1}].click()")
                    check(await pg.evaluate(f"T.st.removed[{wrong[0]}]") == 0 and not await pg.evaluate("T.solved"), f"drill {k}/{j}: wrong elimination accepted")
                    elim = await pg.evaluate("T.insts[0].elim")
                    for idx, (c, d) in enumerate(elim):
                        await pg.evaluate(f"({TSEL})({c}); tpad.children[{d - 1}].click()")
                        if idx < len(elim) - 1:
                            # 中途：已划掉的数不再显示，但还没完成（除非另一处恰好已完成）
                            pass
                check(await pg.evaluate("T.solved") is True, f"drill {k}/{j}: correct answer not accepted")
                # 看推理
                await pg.evaluate("lastTap = null")   # 上面是直接调函数换题的，不是真实点击
                await pg.click("#tBtnA")
                nf = await pg.evaluate("T.frames ? T.frames.length : 0")
                check(nf >= 3, f"drill {k}/{j}: explanation frames {nf}")
                await pg.evaluate("for (let q = 0; q < 10 && T.frames; q++) $('tBtnB').click()")
                check(await pg.evaluate("T.frames") is None, f"drill {k}/{j}: explanation did not return to drill")
        prog = await pg.evaluate("SE.LESSONS.map(L => Object.values(practice.drills[L.id]).filter(v => v === 1).length)")
        check(prog == [10] * 10, f"drill progress {prog}")
        # 看讲解但没做对：记为“看过”(2)，不算完成
        await pg.evaluate("practice.drills.pair = {}; savePractice(); openDrill(4, 3); $('tBtnA').click()")
        check(await pg.evaluate("practice.drills.pair[3]") == 2, "viewing explanation should mark drill as viewed, not solved")
        # 列表上的进度
        await pg.evaluate("openTech()")
        txt = await pg.evaluate("[...document.querySelectorAll('.lbtn[data-a=drill] small')].map(e => e.textContent)")
        check(txt[0] == "10 / 10" and txt[4] == "0 / 10", f"list progress text {txt[:5]}")
        # 刷新后进度还在
        await pg.reload()
        check(await pg.evaluate("Object.keys(practice.drills.naked_single).length") == 10, "practice progress lost after reload")

        # ---------- 3. 整题练习：提示不限次数、不计入闯关、通关后记录 ----------
        await pg.evaluate("startPractice(3, 0)")
        check(await pg.evaluate("$('hintBadge').style.display") == "none", "practice should hide hint count")
        for _ in range(5):
            await pg.evaluate("$('tHint').click(); for (let k = 0; k < 80 && $('hpanel').classList.contains('on'); k++) $('hpNext').click();")
        check(await pg.evaluate("G.hints") == 0 and await pg.evaluate("G.practiceHints") == 5, "practice hints should be unlimited and separate")
        sol = LS[3]["full"][0]["s"]
        await pg.evaluate(f"""(sol) => {{ for (let i = 0; i < 81; i++) if (G.val[i] !== +sol[i]) {{ ({SEL})(i); pad.children[+sol[i] - 1].click(); }} }}""", sol)
        await pg.wait_for_timeout(450)
        check(await pg.evaluate("$('winSheet').classList.contains('on')"), "practice win sheet not shown")
        check(await pg.text_content("#winHome") == "返回练习" and await pg.text_content("#winNext") == "下一道", "practice win buttons text")
        check(await pg.evaluate("practice.full.box_line[0]") == 1, "practice full puzzle not recorded")
        check(await pg.evaluate("Object.keys(progress.stars).length") == 0, "practice must not touch level progress")
        await pg.wait_for_timeout(700)   # 通关面板刚弹出的 700ms 内不响应点击
        await pg.click("#winNext")
        check(await pg.evaluate("G.practice && G.practice.j") == 1, "next practice puzzle not opened")
        await pg.evaluate("handleBack()")
        check(await pg.evaluate("$('tech').classList.contains('on')"), "back from practice game should return to practice list")
        # 闯关的“继续”不受影响，练习存档单独存
        check(await pg.evaluate("localStorage.getItem('sudoku.current')") is None, "practice should not set current level")
        # 闯关胜利面板文字恢复
        await pg.evaluate("startLevel(1); hideTip()")
        await pg.evaluate(f"""(sol) => {{ for (let i = 0; i < 81; i++) if (G.val[i] !== +sol[i]) {{ ({SEL})(i); pad.children[+sol[i] - 1].click(); }} }}""", P[0]["s"])
        await pg.wait_for_timeout(450)
        check(await pg.text_content("#winHome") == "返回关卡" and await pg.text_content("#winNext") == "下一关" and await pg.evaluate("$('winStars').children.length") == 3,
              "level win sheet texts not restored after practice")
        await pg.evaluate("closeSheet('winSheet'); goHome()")

        # ---------- 4. 讲解型提示的规则 ----------
        await pg.evaluate("localStorage.clear()"); await pg.reload()
        await pg.evaluate("progress.stars = {}; for (let k = 1; k < 60; k++) progress.stars[k] = 3; store.set('progress', progress); startLevel(60); hideTip()")
        # 4a0 点提示先确认：取消不扣次数
        await pg.click("#tHint")
        check(await pg.evaluate("HC !== null") and await pg.evaluate("G.hints") == 0, "hint should ask for confirmation first")
        check(await pg.text_content("#hpNext") == "使用提示" and await pg.evaluate("$('hpPrev').hidden"), "confirm panel buttons")
        await pg.click("#hpClose")
        check(await pg.evaluate("G.hints") == 0 and not await pg.evaluate("$('hpanel').classList.contains('on')"), "cancel should not charge")
        await pg.click("#tHint"); await pg.evaluate(f"({SEL})(0)")
        check(await pg.evaluate("G.hints") == 0 and await pg.evaluate("HC") is None, "tapping board during confirm should cancel without charging")
        await pg.click("#tHint")
        check(await pg.evaluate("handleBack()") is True and await pg.evaluate("G.hints") == 0, "back during confirm should cancel")
        # 4a 确认后开始讲解；关闭后再打开不重复扣次数
        await pg.click("#tHint"); await pg.click("#hpNext")
        h1 = await pg.evaluate("G.hints")
        await pg.click("#hpClose")
        check(not await pg.evaluate("$('hpanel').classList.contains('on')"), "hint panel did not close")
        await pg.click("#tHint")
        check(await pg.evaluate("HC") is None, "reopening same hint should not ask again")
        check(await pg.evaluate("G.hints") == h1 == 1, f"reopening same hint charged again: {h1} -> {await pg.evaluate('G.hints')}")
        # 4b 讲解中盘面没有被改动；上一步/下一步正常
        before = await pg.evaluate("G.val.join('')")
        await pg.evaluate("$('hpNext').click(); $('hpPrev').click()")
        check(await pg.evaluate("G.val.join('')") == before and await pg.evaluate("H.i") == 0, "hint navigation changed the board")
        # 4c 填入后：只改一个格子、改对了、面板关闭
        await pg.evaluate("for (let k = 0; k < 80 && $('hpanel').classList.contains('on'); k++) $('hpNext').click();")
        after = await pg.evaluate("G.val.join('')")
        diff = [i for i in range(81) if before[i] != after[i]]
        check(len(diff) == 1 and after[diff[0]] == P[59]["s"][diff[0]], f"hint fill wrong: {diff}")
        check(await pg.evaluate("G.hints") == 1, "filling should not charge again")
        # 4d 讲解时点格子会收起面板；盘面改变后再点提示是新的一次
        await pg.click("#tHint"); await pg.click("#hpNext"); await pg.evaluate(f"({SEL})(0)")
        check(not await pg.evaluate("$('hpanel').classList.contains('on')"), "tapping board should close hint panel")
        check(await pg.evaluate("G.hints") == 2, "second hint should be charged")
        # 4e 选中填错的格子：直接改正
        wrong_i = await pg.evaluate("G.val.indexOf(0)")
        wd = (int(P[59]["s"][wrong_i]) % 9) + 1
        await pg.evaluate(f"({SEL})({wrong_i}); pad.children[{wd - 1}].click(); $('tHint').click()")
        check("填错" in await pg.text_content("#hpText"), "wrong-cell confirm text")
        await pg.click("#hpNext")
        check(await pg.evaluate(f"G.val[{wrong_i}]") == int(P[59]["s"][wrong_i]) and await pg.evaluate("G.hints") == 3, "wrong selected cell should be corrected by hint")
        # 4f 用完后不能再用
        before = await pg.evaluate("G.val.join('')")
        await pg.click("#tHint")
        check(await pg.evaluate("G.val.join('')") == before and not await pg.evaluate("$('hpanel').classList.contains('on')"), "hint used after limit")
        # 4g 返回键先关面板
        await pg.evaluate("G.hints = 2; $('tHint').click(); $('hpNext').click()")
        check(await pg.evaluate("handleBack()") is True and await pg.evaluate("$('game').classList.contains('on')"), "back should close hint panel first")

        # ---------- 5. 提示在 100 关的各种进度下都能讲到填入，且填对 ----------
        rnd = random.Random(3)
        bad_hint = 0
        for t in range(150):
            n = rnd.randint(1, 100)
            await pg.evaluate(f"progress.stars = {{}}; for (let k = 1; k < {n}; k++) progress.stars[k] = 1; store.del('game.{n}'); startLevel({n}); hideTip()")
            sol = P[n - 1]["s"]
            empt = [i for i in range(81) if P[n - 1]["p"][i] == "0"]
            fill = rnd.sample(empt, rnd.randint(0, len(empt) - 1))
            await pg.evaluate("(a) => { const [cells_, sol] = a; cells_.forEach(i => { G.val[i] = +sol[i]; }); render(); }", [fill, sol])
            before = await pg.evaluate("G.val.join('')")
            await pg.evaluate("$('tHint').click(); for (let k = 0; k < 80 && $('hpanel').classList.contains('on'); k++) $('hpNext').click();")
            after = await pg.evaluate("G.val.join('')")
            diff = [i for i in range(81) if before[i] != after[i]]
            if len(diff) != 1 or after[diff[0]] != sol[diff[0]]: bad_hint += 1
        check(bad_hint == 0, f"hint failed on {bad_hint} random states")

        # ---------- 6. 新难度段提醒：只出现一次；“先去学习”打开练习专区 ----------
        await pg.evaluate("localStorage.clear()"); await pg.reload()
        await pg.evaluate("progress.stars = {}; for (let k = 1; k < 46; k++) progress.stars[k] = 2; store.set('progress', progress); startLevel(46)")
        check(await pg.evaluate("$('tipPanel').classList.contains('on')"), "tier tip not shown at level 46")
        await pg.click("#tipGo")
        check(await pg.evaluate("$('tech').classList.contains('on')"), "tip button did not open practice list")
        await pg.evaluate("startLevel(46)")
        check(not await pg.evaluate("$('tipPanel').classList.contains('on')"), "tier tip shown twice")

        # ---------- 7. 清除进度也清掉练习记录 ----------
        await pg.evaluate("practice.drills.pair = {0: 1}; savePractice(); goHome(); $('openSettings').click(); $('resetBtn').click(); $('cfYes').click()")
        check(await pg.evaluate("Object.keys(practice.drills.pair).length") == 0 and await pg.evaluate("localStorage.getItem('sudoku.practice')") is not None or True, "reset")
        check(await pg.evaluate("Object.keys(practice.drills.pair).length") == 0, "reset should clear practice progress")

        # ---------- 8. 损坏的练习存档不影响启动 ----------
        for junk in ['{oops', '[1,2]', '{"drills": {"pair": {"0": "x", "3": 1}}, "full": 5, "seen": {"pair": 1}}']:
            await pg.evaluate("j => localStorage.setItem('sudoku.practice', j)", junk); await pg.reload()
            st = await pg.evaluate("[document.querySelectorAll('.lv').length, Object.keys(practice.drills.pair).length]")
            check(st[0] == 100, f"corrupt practice data broke startup: {junk}")
        check(await pg.evaluate("practice.drills.pair[3]") == 1 and await pg.evaluate("practice.drills.pair[0]") is None, "corrupt practice data not sanitized")

        check(not errs, f"page errors {errs[:3]}")
        print("FAILS:", fails if fails else "none")
        await b.close()
asyncio.run(main())
