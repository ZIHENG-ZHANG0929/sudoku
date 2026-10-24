// 6×6 推理引擎：每关用讲解型提示一路解到底；随机“玩到一半”的盘面也要能讲到填入；排除和填数都必须和答案一致。
const SE = require("../web/engine.js").six;
const P = require("../gen/puzzles6.json");
let bad = 0, steps = 0; const used = {};
function chain(val, sol, label) {
  const r = SE.hintChain(val);
  if (r.stuck) { console.log("STUCK", label); bad++; return null; }
  for (const st of r.steps) {
    steps++; used[st.inst.t] = (used[st.inst.t] || 0) + 1;
    if (st.inst.elim) for (const [c, d] of st.inst.elim) if (sol[c] === d) { console.log("UNSOUND", label); bad++; }
    if (st.frames.some(f => !f.text || /undefined|NaN|1 到 9/.test(f.text))) { console.log("BAD TEXT", label, st.frames.map(f => f.text)); bad++; }
    if (st.frames.some(f => [...f.zone, ...f.pat, ...f.tgt].some(c => !(c >= 0 && c < 36)))) { console.log("BAD CELL", label); bad++; }
  }
  if (sol[r.place[0]] !== r.place[1] || val[r.place[0]]) { console.log("WRONG PLACE", label); bad++; }
  return r.place;
}
P.forEach((x, k) => {
  const val = [...x.p].map(Number), sol = [...x.s].map(Number);
  for (let g = 0; g < 40 && val.some(v => !v); g++) { const pl = chain(val, sol, "level " + (k + 1)); if (!pl) break; val[pl[0]] = pl[1]; }
  if (val.join("") !== x.s) { console.log("NOT SOLVED", k + 1); bad++; }
});
let rs = 7; const rand = n => { rs = (rs * 48271) % 2147483647; return rs % n; };
for (let t = 0; t < 3000; t++) {
  const x = P[rand(50)], val = [...x.p].map(Number), sol = [...x.s].map(Number);
  const e = val.map((v, i) => v ? -1 : i).filter(i => i >= 0), k = rand(e.length);
  for (let j = 0; j < k; j++) { const i = e[rand(e.length)]; val[i] = sol[i]; }
  if (val.some(v => !v)) chain(val, sol, "random " + t);
}
console.log("6x6 steps checked", steps, JSON.stringify(used));
console.log(bad ? "FAILS: " + bad : "FAILS: none");
