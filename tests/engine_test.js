// 推理引擎正确性：用提示链把每一关解到底；每一步排除都不能删掉正确答案，每一步填数都必须正确。
const SE = require("../web/engine.js");
const P = require("../gen/puzzles.json");
let bad = 0, steps = 0; const used = {};
function checkChain(val, sol, label) {
  const r = SE.hintChain(val);
  if (r.stuck) { console.log("STUCK", label); bad++; return null; }
  for (const st of r.steps) {
    steps++; used[st.inst.t] = (used[st.inst.t] || 0) + 1;
    if (st.inst.elim) for (const [c, d] of st.inst.elim) if (sol[c] === d) { console.log("UNSOUND elim", label, st.inst.t, c, d); bad++; }
    if (!st.frames.length || st.frames.some(f => !f.text || /undefined|NaN/.test(f.text))) { console.log("BAD TEXT", label, st.inst.t, st.frames.map(f => f.text)); bad++; }
  }
  const [c, d] = r.place;
  if (sol[c] !== d || val[c]) { console.log("WRONG PLACE", label, c, d, sol[c]); bad++; }
  return r.place;
}
// 1) 每关从初始盘面开始，一直用提示链解到底
P.forEach((x, k) => {
  const val = [...x.p].map(Number), sol = [...x.s].map(Number);
  let guard = 0;
  while (val.some(v => !v) && guard++ < 90) {
    const pl = checkChain(val, sol, "level " + (k + 1));
    if (!pl) break;
    val[pl[0]] = pl[1];
  }
  if (val.join("") !== x.s) { console.log("NOT SOLVED", k + 1); bad++; }
});
// 2) 随机的“玩到一半”盘面：随机填对一部分空格
let rnd = 12345; const rand = n => { rnd = (rnd * 1103515245 + 12345) & 0x7fffffff; return rnd % n; };
for (let t = 0; t < 3000; t++) {
  const x = P[rand(100)], val = [...x.p].map(Number), sol = [...x.s].map(Number);
  const empt = val.map((v, i) => v ? -1 : i).filter(i => i >= 0);
  const k = rand(empt.length);
  for (let j = 0; j < k; j++) { const i = empt[rand(empt.length)]; val[i] = sol[i]; }
  if (val.some(v => !v)) checkChain(val, sol, "random " + t);
}
console.log("steps checked", steps, "techniques used", JSON.stringify(used));
console.log(bad ? "FAILS: " + bad : "FAILS: none");
