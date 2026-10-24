// 每道练习：这一课的技巧确实能用；比它简单的技巧都用不上；排除和填数都和答案一致；讲解文字完整。
const SE = require("../web/engine.js");
const L = require("../gen/lessons.json");
const sols = require(process.argv[2]);
const dec = c => [...Array(81)].map((_, i) => parseInt(c.substr(i * 2, 2), 36));
const ORDER = ["naked_single", "hidden_single_box", "hidden_single_line", "pointing", "claiming", "naked_pair", "hidden_pair",
  "naked_triple", "hidden_triple", "x_wing", "xy_wing", "xyz_wing", "swordfish"];
let bad = [], n = 0;
L.forEach((les, k) => {
  const lesson = SE.LESSONS[k];
  [["demo", les.demo], ...les.drills.map((d, j) => ["drill" + j, d])].forEach(([name, D]) => {
    n++;
    const val = [...D.v].map(Number), cand = dec(D.c), sol = [...sols[k + ":" + name]].map(Number);
    const insts = [].concat(...lesson.techs.map(t => SE.find(t, val, cand)));
    if (!insts.length) bad.push(`${les.id} ${name}: technique not applicable`);
    // 更简单的方法都用不上（唯一候选数这一课：宫内/行列排除也用不上，避免混淆）
    const easier = k === 0 ? ["hidden_single_box", "hidden_single_line"] : ORDER.filter(t => SE.TECH_LESSON[t] < k);
    easier.forEach(t => { if (SE.find(t, val, cand).length) bad.push(`${les.id} ${name}: easier technique ${t} applies`); });
    insts.forEach(x => {
      if (x.place && sol[x.place[0]] !== x.place[1]) bad.push(`${les.id} ${name}: wrong placement`);
      if (x.elim) x.elim.forEach(([c, d]) => { if (sol[c] === d) bad.push(`${les.id} ${name}: eliminates the answer`); });
      const fr = SE.describe(x, val, cand, { basic: lesson.kind === "place" });
      if (fr.length < 2 || fr.some(f => !f.text || /undefined|NaN|null/.test(f.text))) bad.push(`${les.id} ${name}: bad text ${fr.map(f => f.text)}`);
      if (fr.some(f => [...f.zone, ...f.pat, ...f.tgt].some(c => !(c >= 0 && c < 81)))) bad.push(`${les.id} ${name}: bad highlight`);
    });
  });
});
console.log("drill states checked", n);
console.log(bad.length ? "FAILS: " + bad.slice(0, 10).join(" | ") : "FAILS: none");
