// 生成教学数据：每课 1 个讲解盘面、10 道单步练习、2 道整题。
// 单步练习盘面要求：这一课的技巧能用，且没有更简单的技巧可用（单数类课程里，更前面的课的技巧都用不上）。
const fs = require("fs");
const SE = require("../web/engine.js");
const pool = require("./pool.json");

const LESSON_ORDER = ["naked_single", "hidden_single_box", "hidden_single_line", "pointing", "claiming",
  "naked_pair", "hidden_pair", "naked_triple", "hidden_triple", "x_wing", "xy_wing", "xyz_wing", "swordfish",
  "naked_quad", "hidden_quad"];
const NL = SE.LESSONS.length;
const enc = c => c.map(m => m.toString(36).padStart(2, "0")).join("");
let seed = 20261018; const rand = n => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % n; };

const drills = [...Array(NL)].map(() => []);   // 候选盘面
const full = [...Array(NL)].map(() => []);     // 整题候选

pool.forEach((pz, pi) => {
  const val = [...pz.p].map(Number), sol = [...pz.s].map(Number);
  let cand = SE.basicCands(val), elimUsed = false, maxL = 0, usedL = {};
  const empties = () => val.filter(v => !v).length;
  for (let guard = 0; guard < 400 && val.some(v => !v); guard++) {
    const inst = SE.next(val, cand, LESSON_ORDER);
    if (!inst) { maxL = 99; break; }
    const L = SE.TECH_LESSON[inst.t];
    maxL = Math.max(maxL, L); usedL[L] = (usedL[L] || 0) + 1;
    // 记录练习盘面
    if (L < NL) {
      let ok = true;
      if (L <= 2) {
        ok = !elimUsed && empties() >= (L === 0 ? 25 : 35);
        if (L === 0) ok = ok && !SE.find("hidden_single_box", val, cand).length && !SE.find("hidden_single_line", val, cand).length;
      } else ok = empties() >= 25;
      // 同一道题每课只取一个盘面
      if (ok && !drills[L].some(d => d.pi === pi)) {
        const n = SE.LESSONS[L].techs.reduce((a, t) => a + SE.find(t, val, cand).length, 0);
        drills[L].push({ pi, p: pz.p, v: val.join(""), c: enc(cand), t: inst.t, n, e: empties() });
      }
    }
    if (inst.elim) elimUsed = true;
    // 校验：排除和填数都必须和答案一致
    if (inst.place && sol[inst.place[0]] !== inst.place[1]) throw new Error("bad place");
    if (inst.elim) inst.elim.forEach(([c, d]) => { if (sol[c] === d) throw new Error("bad elim"); });
    SE.apply(inst, val, cand);
  }
  if (maxL < NL && val.join("") === pz.s && (usedL[maxL] || 0) >= (maxL <= 2 ? 3 : 1)) {
    const givens = [...pz.p].filter(c => c !== "0").length;
    full[maxL].push({ pi, p: pz.p, s: pz.s, uses: usedL[maxL], givens });
  }
});

function pick(arr, k, pref) {
  const a = arr.slice(); const out = [];
  if (pref) a.sort(pref);
  while (out.length < k && a.length) {
    const j = pref ? 0 : rand(a.length);
    out.push(a.splice(j, 1)[0]);
  }
  return out;
}

const lessons = SE.LESSONS.map((L, k) => {
  const pool_ = drills[k];
  // 讲解盘面：只有一处能用的最清楚；区块排除、数对、三数组优先用第一种变体做讲解
  const primary = L.techs[0];
  const demoCands = pool_.filter(d => d.n === 1 && d.t === primary);
  const demo = demoCands.length ? demoCands[rand(demoCands.length)] : pool_[0];
  const rest = pool_.filter(d => d !== demo);
  // 练习：两种变体都有时尽量各取一部分
  let picks = [];
  if (L.techs.length > 1) {
    const a = rest.filter(d => d.t === L.techs[0]), b = rest.filter(d => L.techs.slice(1).indexOf(d.t) >= 0);
    picks = pick(a, Math.max(10 - Math.min(4, b.length), 0)).concat(pick(b, Math.min(4, b.length)));
  }
  if (picks.length < 10) picks = picks.concat(pick(rest.filter(d => picks.indexOf(d) < 0), 10 - picks.length));
  // 打乱顺序
  picks = pick(picks, picks.length);
  // 整题：入门类挑提示数多的，其余挑用到本课技巧次数多的
  const fp = full[k].filter(f => !picks.some(d => d.pi === f.pi) && f.pi !== demo.pi);
  const fullPicks = pick(fp, 2, (x, y) => (k <= 2 ? y.givens - x.givens : y.uses - x.uses));
  console.log(L.name.padEnd(6), "drill pool", String(pool_.length).padStart(5), "| demo", demo.t, "| drills", [...new Set(picks.map(d => d.t))].map(t => t + "×" + picks.filter(d => d.t === t).length).join(" "),
    "| full pool", full[k].length, "givens", fullPicks.map(f => f.givens).join(","), "uses", fullPicks.map(f => f.uses).join(","));
  const pack = d => ({ p: d.p, v: d.v, c: d.c });
  return { id: L.id, demo: pack(demo), drills: picks.map(pack), full: fullPicks.map(f => ({ p: f.p, s: f.s })) };
});
const bad = lessons.filter(l => l.drills.length < 10 || l.full.length < 2);
if (bad.length) { console.log("NOT ENOUGH for", bad.map(l => l.id)); process.exit(1); }
fs.writeFileSync(__dirname + "/lessons.json", JSON.stringify(lessons));
console.log("written", fs.statSync(__dirname + "/lessons.json").size, "bytes");
