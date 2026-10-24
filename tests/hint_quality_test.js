// 讲解型提示的质量：沿提示走完全部关卡，检查
// 1) 每一步都对（划掉的不是答案、填的是答案）；2) 链条不啰嗦（去掉任何一步排除都推不出同一个数）；
// 3) 文字说“高亮”的帧确实有高亮；4) 只剩一个空格时不出现空洞的“挡住”帧。
const SE = require("../web/engine.js");
const P9 = require("../gen/puzzles.json"), P6 = require("../gen/puzzles6.json");
const bad = []; let chains = 0, maxSteps = 0;
function run(E, P, NN, tag) {
  P.forEach((p, li) => {
    const v = [...p.p].map(Number), sol = [...p.s].map(Number);
    for (let g = 0; g < NN && v.some(x => !x); g++) {
      const r = E.hintChain(v);
      if (r.stuck) { bad.push(`${tag}${li + 1}: stuck`); return; }
      chains++; maxSteps = Math.max(maxSteps, r.steps.length);
      r.steps.forEach((st, k) => {
        (st.inst.elim || []).forEach(([c, d]) => { if (sol[c] === d) bad.push(`${tag}${li + 1}: eliminated answer ${c}=${d}`); });
        st.frames.forEach(f => {
          if (/高亮/.test(f.text) && !f.pat.length && !f.tgt.length && !f.zone.length) bad.push(`${tag}${li + 1}: "高亮" frame without highlight: ${f.text}`);
          if (/别的空格都放不了/.test(f.text) && !f.tgt.length) bad.push(`${tag}${li + 1}: empty blocker frame: ${f.text}`);
          if (!f.text || /undefined|NaN/.test(f.text)) bad.push(`${tag}${li + 1}: bad text ${f.text}`);
        });
      });
      if (sol[r.place[0]] !== r.place[1]) bad.push(`${tag}${li + 1}: wrong place`);
      // 链条最简：去掉任何一步排除后，最后那个数都推不出来（按引擎自己的重放规则）
      const insts = r.steps.map(s => s.inst);
      insts.forEach(x => { if (!x.place && !x.elim.length) bad.push(`${tag}${li + 1}: empty elimination step`); });
      for (let i = 0; i < insts.length - 1; i++)
        if (E.replay(v, insts.slice(0, i).concat(insts.slice(i + 1)))) bad.push(`${tag}${li + 1}: step ${i} (${insts[i].t}) is not needed`);
      v[r.place[0]] = r.place[1];
    }
  });
}
run(SE, P9, 81, "9x9 L");
run(SE.six, P6, 36, "6x6 L");
// 只剩一个空格的宫：直接说缺的数字
{
  const p = P9[0], v = [...p.s].map(Number); v[1] = 0;
  const r = SE.hintChain(v), txt = r.steps[0].frames.map(f => f.text).join(" | ");
  if (!/只剩.*这一个空格/.test(txt) || /挡住/.test(txt)) bad.push("last empty cell frames: " + txt);
}
// 第 4 轮审查找到的例子：区块排除那一步和最后的 9 无关
{
  const r = SE.hintChain([..."170230600003786014600015037030670102017023060006051073960348701700192306301567009"].map(Number));
  if (r.steps.map(s => s.inst.t).join() !== "x_wing,hidden_single_box") bad.push("unpruned example: " + r.steps.map(s => s.inst.t));
}
// 随机“卡住”盘面：从答案随机挖空，链条都要最简
{
  let seed = 7; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let t = 0; t < 1500; t++) {
    const p = P9[t % P9.length], v = [...p.s].map(Number);
    for (let i = 0; i < 81; i++) if (rnd() < 0.62) v[i] = 0;
    const r = SE.hintChain(v); if (r.stuck) continue;
    const insts = r.steps.map(s => s.inst);
    if (+p.s[r.place[0]] !== r.place[1]) bad.push("random: wrong place");
    for (let i = 0; i < insts.length - 1; i++) if (SE.replay(v, insts.slice(0, i).concat(insts.slice(i + 1)))) bad.push(`random ${t}: step ${i} not needed`);
  }
}
if (maxSteps > 6) bad.push("hint chain too long: " + maxSteps + " steps");
console.log(`chains ${chains} max steps ${maxSteps}`);
console.log(bad.length ? "FAILS:\n  " + bad.slice(0, 20).join("\n  ") : "FAILS: none");
process.exit(bad.length ? 1 : 0);
