// 6×6 数独题库（宫：2 行 × 3 列）。唯一解、按解题技巧和提示数分 4 段，共 50 关。
const fs = require("fs");
const SE = require("../web/engine.js").six;
const N = 6, NN = 36, BR = 2, BC = 3;
const R = i => Math.floor(i / N), C = i => i % N, B = i => Math.floor(R(i) / BR) * (N / BC) + Math.floor(C(i) / BC);
const PEERS = [...Array(NN)].map((_, i) => [...Array(NN).keys()].filter(j => j !== i && (R(j) === R(i) || C(j) === C(i) || B(j) === B(i))));
// mulberry32：质量好的可复现随机数
let seed = +(process.argv[2] || 66) >>> 0;
const rnd = () => { seed = (seed + 0x6D2B79F5) >>> 0; let t = seed; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const rand = n => Math.floor(rnd() * n);
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = rand(i + 1); [a[i], a[j]] = [a[j], a[i]]; } return a; };
function fullGrid() {
  const g = Array(NN).fill(0);
  (function rec(i) {
    if (i === NN) return true;
    for (const d of shuffle([1, 2, 3, 4, 5, 6])) if (PEERS[i].every(p => g[p] !== d)) { g[i] = d; if (rec(i + 1)) return true; }
    g[i] = 0; return false;
  })(0);
  return g;
}
function count(g0, limit = 2) {
  const g = g0.slice(); let n = 0;
  (function rec() {
    let best = -1, bm = 0, bc = 9;
    for (let i = 0; i < NN; i++) if (!g[i]) {
      let m = 63; PEERS[i].forEach(p => { if (g[p]) m &= ~(1 << (g[p] - 1)); });
      const c = SE.popc(m); if (c < bc) { bc = c; best = i; bm = m; if (c === 0) return false; }
    }
    if (best < 0) { n++; return n >= limit; }
    for (let d = 1; d <= N; d++) if (bm & (1 << (d - 1))) { g[best] = d; if (rec()) return true; g[best] = 0; }
    return false;
  })();
  return n;
}
const ORDER = ["naked_single", "hidden_single_box", "hidden_single_line", "pointing", "claiming", "naked_pair", "hidden_pair",
  "naked_triple", "hidden_triple", "x_wing", "xy_wing", "xyz_wing", "swordfish", "naked_quad", "hidden_quad"];
function grade(p, sol) {
  const val = p.slice(), cand = SE.basicCands(val); let maxL = 0, score = 0;
  for (let k = 0; k < 300 && val.some(v => !v); k++) {
    const x = SE.next(val, cand, ORDER); if (!x) return null;
    const L = SE.TECH_LESSON[x.t]; maxL = Math.max(maxL, L); score += [1, 1, 2, 6, 6, 8, 10, 15, 18, 20, 30, 35, 35, 30, 35][ORDER.indexOf(x.t)];
    if (x.place && sol[x.place[0]] !== x.place[1]) throw new Error("bad");
    if (x.elim) x.elim.forEach(([c, d]) => { if (sol[c] === d) throw new Error("bad elim"); });
    SE.apply(x, val, cand);
  }
  return val.join("") === sol.join("") ? { maxL, score } : null;
}
function make(minGivens) {
  const sol = fullGrid(), g = sol.slice();
  const cells = shuffle([...Array(NN).keys()]);
  for (const i of cells) {
    if (g.filter(v => v).length <= minGivens) break;
    const pair = [...new Set([i, NN - 1 - i])];
    const keep = pair.map(c => g[c]);
    pair.forEach(c => { g[c] = 0; });
    if (count(g) !== 1) pair.forEach((c, k) => { g[c] = keep[k]; });
  }
  return { g, sol };
}
const pools = { 1: [], 2: [], 3: [], 4: [] };
const stat = {};
for (let t = 0; t < 12000; t++) {
  const kind = t % 4, mg = [rand(5) + 20, rand(4) + 15, rand(4) + 11, 0][kind];
  const { g, sol } = make(mg);
  const gv = g.filter(v => v).length, r = grade(g, sol);
  if (!r) continue;
  stat[`L${r.maxL}`] = (stat[`L${r.maxL}`] || 0) + 1;
  const rec = { p: g.join(""), s: sol.join(""), givens: gv, maxL: r.maxL, score: r.score };
  if (gv >= 20 && r.maxL <= 1) pools[1].push(rec);
  else if (gv >= 15 && gv <= 18 && r.maxL <= 2) pools[2].push(rec);
  else if (gv >= 11 && gv <= 14 && r.maxL <= 2) pools[3].push(rec);
  else if (gv <= 10 && r.maxL <= 4) pools[4].push(rec);   // 困难段：提示数最少，但不需要 X-Wing 之类的高级技巧
}
console.log("technique levels seen:", JSON.stringify(stat));
console.log("pool sizes:", Object.entries(pools).map(([k, v]) => k + ":" + v.length).join(" "),
  "| tier4 needing eliminations:", pools[4].filter(r => r.maxL >= 3).length, "| tier4 givens:", [...new Set(pools[4].map(r => r.givens))].sort().join(","));
const want = { 1: 12, 2: 13, 3: 13, 4: 12 };
const out = []; const seen = new Set();
for (const k of [1, 2, 3, 4]) {
  let pool = pools[k].filter(r => !seen.has(r.p));
  // 在段内均匀挑选，然后按难度排序
  pool.sort((a, b) => k <= 2 ? (b.givens - a.givens || a.score - b.score) : (a.score - b.score));
  const step = pool.length / want[k], picked = [];
  for (let j = 0; j < want[k]; j++) picked.push(pool[Math.floor(j * step)]);
  picked.forEach(r => seen.add(r.p));
  out.push(...picked.map(r => ({ p: r.p, s: r.s, tier: k, givens: r.givens, maxL: r.maxL, score: r.score })));
}
fs.writeFileSync(__dirname + "/puzzles6.json", JSON.stringify(out.map(({ p, s }) => ({ p, s }))));
fs.writeFileSync(__dirname + "/puzzles6_report.json", JSON.stringify(out.map((r, k) => ({ level: k + 1, tier: r.tier, givens: r.givens, maxLesson: r.maxL, score: r.score }))));
console.log("levels", out.length, "| givens by level:", out.map(r => r.givens).join(" "));
console.log("max technique lesson by level:", out.map(r => r.maxL).join(""));
