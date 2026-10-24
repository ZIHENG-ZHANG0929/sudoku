// 数独技巧推理引擎：找出每种技巧能用在哪里，并生成分步讲解（文字 + 高亮）。
// 网页里用它做讲解型提示和练习判题；生成练习题的 Node 脚本也用同一份代码。
// 支持 9×9（宫 3×3）和 6×6（宫 2 行 × 3 列）：build(N, 宫的行数, 宫的列数)
var SE = (function () {
  "use strict";
  function build(N, BR, BC) {
  var NN = N * N, FULL = (1 << N) - 1;
  var R = function (i) { return Math.floor(i / N); }, C = function (i) { return i % N; };
  var B = function (i) { return Math.floor(R(i) / BR) * (N / BC) + Math.floor(C(i) / BC); };
  var ROWS = [], COLS = [], BOXES = [];
  for (var a = 0; a < N; a++) { ROWS.push([]); COLS.push([]); BOXES.push([]); }
  for (var i = 0; i < NN; i++) { ROWS[R(i)].push(i); COLS[C(i)].push(i); BOXES[B(i)].push(i); }
  var UNITS = [];
  ROWS.forEach(function (u, k) { UNITS.push({ kind: "row", i: k, cells: u }); });
  COLS.forEach(function (u, k) { UNITS.push({ kind: "col", i: k, cells: u }); });
  BOXES.forEach(function (u, k) { UNITS.push({ kind: "box", i: k, cells: u }); });
  var PEERS = [];
  for (var p = 0; p < NN; p++) {
    var s = {};
    ROWS[R(p)].concat(COLS[C(p)], BOXES[B(p)]).forEach(function (j) { if (j !== p) s[j] = 1; });
    PEERS.push(Object.keys(s).map(Number).sort(function (x, y) { return x - y; }));
  }
  var PEERSET = PEERS.map(function (l) { var o = {}; l.forEach(function (j) { o[j] = 1; }); return o; });
  function sees(x, y) { return x !== y && !!PEERSET[x][y]; }
  function popc(m) { var n = 0; while (m) { n += m & 1; m >>= 1; } return n; }
  function digs(m) { var o = []; for (var d = 1; d <= N; d++) if (m & (1 << (d - 1))) o.push(d); return o; }
  function bit(d) { return 1 << (d - 1); }
  function combos(arr, n) {
    var out = [];
    (function rec(start, cur) {
      if (cur.length === n) { out.push(cur.slice()); return; }
      for (var k = start; k < arr.length; k++) { cur.push(arr[k]); rec(k + 1, cur); cur.pop(); }
    })(0, []);
    return out;
  }
  function uniq(a) { var o = {}, r = []; a.forEach(function (x) { if (!o[x]) { o[x] = 1; r.push(x); } }); return r; }

  function basicCands(val) {
    var c = new Array(NN);
    for (var i = 0; i < NN; i++) {
      if (val[i]) { c[i] = 0; continue; }
      var m = FULL;
      PEERS[i].forEach(function (j) { if (val[j]) m &= ~bit(val[j]); });
      c[i] = m;
    }
    return c;
  }

  // ---------- 各种技巧：返回所有能用的位置 ----------
  function nakedSingle(val, cand) {
    var out = [];
    for (var i = 0; i < NN; i++) if (!val[i] && popc(cand[i]) === 1) out.push({ t: "naked_single", place: [i, digs(cand[i])[0]], pat: [i] });
    return out;
  }
  function hiddenSingle(kinds, t) {
    return function (val, cand) {
      var out = [], seen = {};
      UNITS.forEach(function (u) {
        if (kinds.indexOf(u.kind) < 0) return;
        for (var d = 1; d <= N; d++) {
          var spots = u.cells.filter(function (c) { return !val[c] && (cand[c] & bit(d)); });
          var placed = u.cells.some(function (c) { return val[c] === d; });
          if (spots.length === 1 && !placed) {
            var key = spots[0] + ":" + d + ":" + u.kind;
            if (seen[key]) continue; seen[key] = 1;
            out.push({ t: t, place: [spots[0], d], unit: { kind: u.kind, i: u.i }, digit: d, pat: [spots[0]] });
          }
        }
      });
      return out;
    };
  }
  function pointing(val, cand) {
    var out = [];
    BOXES.forEach(function (box, b) {
      for (var d = 1; d <= N; d++) {
        var spots = box.filter(function (c) { return !val[c] && (cand[c] & bit(d)); });
        if (spots.length < 2) continue;
        [["row", R, ROWS], ["col", C, COLS]].forEach(function (L) {
          var lines = uniq(spots.map(L[1]));
          if (lines.length !== 1) return;
          var tg = L[2][lines[0]].filter(function (c) { return B(c) !== b && !val[c] && (cand[c] & bit(d)); });
          if (tg.length) out.push({ t: "pointing", digit: d, unit: { kind: "box", i: b }, line: { kind: L[0], i: lines[0] }, pat: spots, elim: tg.map(function (c) { return [c, d]; }) });
        });
      }
    });
    return out;
  }
  function claiming(val, cand) {
    var out = [];
    UNITS.forEach(function (u) {
      if (u.kind === "box") return;
      for (var d = 1; d <= N; d++) {
        var spots = u.cells.filter(function (c) { return !val[c] && (cand[c] & bit(d)); });
        if (spots.length < 2) continue;
        var bs = uniq(spots.map(B));
        if (bs.length !== 1) continue;
        var tg = BOXES[bs[0]].filter(function (c) { return u.cells.indexOf(c) < 0 && !val[c] && (cand[c] & bit(d)); });
        if (tg.length) out.push({ t: "claiming", digit: d, unit: { kind: u.kind, i: u.i }, box: bs[0], pat: spots, elim: tg.map(function (c) { return [c, d]; }) });
      }
    });
    return out;
  }
  function naked(n, t) {
    return function (val, cand) {
      var out = [];
      UNITS.forEach(function (u) {
        var empt = u.cells.filter(function (c) { return !val[c]; });
        var pool = empt.filter(function (c) { var k = popc(cand[c]); return k >= 2 && k <= n; });
        combos(pool, n).forEach(function (cmb) {
          var m = 0; cmb.forEach(function (c) { m |= cand[c]; });
          if (popc(m) !== n) return;
          var el = [];
          empt.forEach(function (c) { if (cmb.indexOf(c) < 0) digs(cand[c] & m).forEach(function (d) { el.push([c, d]); }); });
          if (el.length) out.push({ t: t, unit: { kind: u.kind, i: u.i }, pat: cmb, digits: digs(m), elim: el });
        });
      });
      return out;
    };
  }
  function hidden(n, t) {
    return function (val, cand) {
      var out = [];
      UNITS.forEach(function (u) {
        var empt = u.cells.filter(function (c) { return !val[c]; });
        var dpos = {};
        for (var d = 1; d <= N; d++) {
          if (u.cells.some(function (c) { return val[c] === d; })) continue;
          var sp = empt.filter(function (c) { return cand[c] & bit(d); });
          if (sp.length >= 2 && sp.length <= n) dpos[d] = sp;
        }
        combos(Object.keys(dpos).map(Number), n).forEach(function (ds) {
          var cells = uniq([].concat.apply([], ds.map(function (d) { return dpos[d]; })));
          if (cells.length !== n) return;
          var keep = 0; ds.forEach(function (d) { keep |= bit(d); });
          var el = [];
          cells.forEach(function (c) { digs(cand[c] & ~keep).forEach(function (d) { el.push([c, d]); }); });
          if (el.length) out.push({ t: t, unit: { kind: u.kind, i: u.i }, pat: cells.sort(function (x, y) { return x - y; }), digits: ds, elim: el });
        });
      });
      return out;
    };
  }
  function fish(n, t) {
    return function (val, cand) {
      var out = [];
      for (var d = 1; d <= N; d++) {
        [["row", ROWS, COLS, C, R], ["col", COLS, ROWS, R, C]].forEach(function (F) {
          var base = F[1], cover = F[2], coverOf = F[3], baseOf = F[4];
          var lines = {};
          base.forEach(function (line, li) {
            var pos = uniq(line.filter(function (c) { return !val[c] && (cand[c] & bit(d)); }).map(coverOf));
            if (pos.length >= 2 && pos.length <= n) lines[li] = pos;
          });
          combos(Object.keys(lines).map(Number), n).forEach(function (ls) {
            var cov = uniq([].concat.apply([], ls.map(function (l) { return lines[l]; })));
            if (cov.length !== n) return;
            var el = [];
            cov.forEach(function (ci) { cover[ci].forEach(function (c) { if (ls.indexOf(baseOf(c)) < 0 && !val[c] && (cand[c] & bit(d))) el.push([c, d]); }); });
            if (!el.length) return;
            var pat = [];
            ls.forEach(function (l) { base[l].forEach(function (c) { if (!val[c] && (cand[c] & bit(d))) pat.push(c); }); });
            out.push({ t: t, digit: d, base: { kind: F[0], lines: ls.slice().sort() }, cover: { kind: F[0] === "row" ? "col" : "row", lines: cov.slice().sort() }, pat: pat, elim: el });
          });
        });
      }
      return out;
    };
  }
  function xyWing(val, cand) {
    var out = [];
    var bi = []; for (var i = 0; i < NN; i++) if (!val[i] && popc(cand[i]) === 2) bi.push(i);
    bi.forEach(function (pv) {
      var pm = cand[pv];
      var wings = bi.filter(function (q) { return sees(pv, q) && popc(pm & cand[q]) === 1; });
      combos(wings, 2).forEach(function (w) {
        var am = cand[w[0]], bm = cand[w[1]];
        if ((am & pm) === (bm & pm)) return;
        var z = am & ~pm;
        if (popc(z) !== 1 || (bm & ~pm) !== z) return;
        var zd = digs(z)[0], el = [];
        for (var c = 0; c < NN; c++) if (c !== pv && !val[c] && (cand[c] & z) && sees(c, w[0]) && sees(c, w[1])) el.push([c, zd]);
        if (el.length) out.push({ t: "xy_wing", pivot: pv, wings: w, digit: zd, x: digs(am & pm)[0], y: digs(bm & pm)[0], pat: [pv, w[0], w[1]], elim: el });
      });
    });
    return out;
  }
  function xyzWing(val, cand) {
    var out = [];
    for (var pv = 0; pv < NN; pv++) {
      if (val[pv] || popc(cand[pv]) !== 3) continue;
      var pm = cand[pv];
      var wings = PEERS[pv].filter(function (q) { return !val[q] && popc(cand[q]) === 2 && (cand[q] & ~pm) === 0; });
      combos(wings, 2).forEach(function (w) {
        var am = cand[w[0]], bm = cand[w[1]];
        if (am === bm || (am | bm) !== pm) return;
        var z = am & bm; if (popc(z) !== 1) return;
        var zd = digs(z)[0], el = [];
        for (var c = 0; c < NN; c++) if (c !== pv && w.indexOf(c) < 0 && !val[c] && (cand[c] & z) && sees(c, pv) && sees(c, w[0]) && sees(c, w[1])) el.push([c, zd]);
        if (el.length) out.push({ t: "xyz_wing", pivot: pv, wings: w, digit: zd, pat: [pv, w[0], w[1]], elim: el });
      });
    }
    return out;
  }

  var FIND = {
    naked_single: nakedSingle,
    hidden_single_box: hiddenSingle(["box"], "hidden_single_box"),
    hidden_single_line: hiddenSingle(["row", "col"], "hidden_single_line"),
    pointing: pointing, claiming: claiming,
    naked_pair: naked(2, "naked_pair"), hidden_pair: hidden(2, "hidden_pair"),
    naked_triple: naked(3, "naked_triple"), hidden_triple: hidden(3, "hidden_triple"),
    x_wing: fish(2, "x_wing"), xy_wing: xyWing, xyz_wing: xyzWing, swordfish: fish(3, "swordfish"),
    naked_quad: naked(4, "naked_quad"), hidden_quad: hidden(4, "hidden_quad"),
  };
  // 提示时按人最容易看出来的顺序找
  var HINT_ORDER = ["hidden_single_box", "hidden_single_line", "naked_single", "pointing", "claiming",
    "naked_pair", "hidden_pair", "naked_triple", "hidden_triple", "x_wing", "xy_wing", "xyz_wing", "swordfish",
    "naked_quad", "hidden_quad"];

  var LESSONS = [
    { id: "naked_single", name: "唯一候选数", techs: ["naked_single"], tier: "入门", kind: "place",
      short: "一个格子能填的数只剩一个",
      intro: "看一个空格所在的行、列和宫。这三处已经出现过的数字，这一格都不能再填。如果 1 到 9 里只剩一个数字没出现过，这一格就只能填它。",
      task: "找出一个只剩一个数能填的空格，把数字填进去。" },
    { id: "hidden_single_box", name: "宫内排除", techs: ["hidden_single_box"], tier: "入门", kind: "place",
      short: "某个数在一个宫里只剩一个位置",
      intro: "每个宫（3×3 的小方块，从左上到右下编号 1–9）都必须有 1 到 9 各一个。挑一个这个宫还没有的数字，看它在宫里能放在哪：凡是同一行或同一列已经有这个数字的格子都放不了。如果最后只剩一个格子，数字就一定在那里。",
      task: "找一个宫，里面某个数字只剩一个位置能放，把它填进去。" },
    { id: "hidden_single_line", name: "行列排除", techs: ["hidden_single_line"], tier: "简单", kind: "place",
      short: "某个数在一行或一列里只剩一个位置",
      intro: "和宫内排除一样的道理，换成一整行或一整列。挑一个这一行还没有的数字，把同列、同宫已经有这个数字的格子都排除掉，只剩一格时，数字就在那一格。",
      task: "找一行或一列，里面某个数字只剩一个位置能放，把它填进去。" },
    { id: "box_line", name: "区块排除", techs: ["pointing", "claiming"], tier: "中等", kind: "elim",
      short: "候选数挤在一条线上或一个宫里",
      intro: "从这一课开始要用到笔记（候选数）。如果某个数字在一个宫里的候选位置都在同一行（或同一列），那这个数字在这一行一定落在这个宫里，同一行在宫外的格子就都不能是它。反过来也成立：一行里某个数字的候选都在同一个宫，这个宫里不在这一行的格子就不能是它。",
      task: "找出可以用区块排除划掉的候选数，在那些格子里点数字把它划掉。" },
    { id: "pair", name: "数对", techs: ["naked_pair", "hidden_pair"], tier: "中等", kind: "elim",
      short: "两个格子锁定两个数",
      intro: "同一行（列、宫）里，如果有两个格子的候选数都只有同样的两个数，比如都是 3 和 7，那 3 和 7 一定分别在这两格里，这一行其他格子都不能再是 3 或 7。这叫显性数对。另一种是隐性数对：两个数字在一行里都只能放在同样的两格，这两格就被它们占住，格子里的其他候选数可以划掉。",
      task: "找出一个数对，把它能划掉的候选数划掉。" },
    { id: "triple", name: "三数组", techs: ["naked_triple", "hidden_triple"], tier: "困难", kind: "elim",
      short: "三个格子锁定三个数",
      intro: "数对的扩展。同一行（列、宫）里的三个格子，候选数加起来只有三个数字（每格不一定三个都有），这三个数字就一定分布在这三格里，其他格子都不能是它们。隐性三数组则是三个数字在一行里只能放在同样的三格，这三格的其他候选数可以划掉。",
      task: "找出一个三数组，把它能划掉的候选数划掉。" },
    { id: "x_wing", name: "X-Wing", techs: ["x_wing"], tier: "困难", kind: "elim",
      short: "两行两列组成的矩形",
      intro: "看某一个数字。如果有两行，这个数字在每一行里都只剩两个候选位置，而且这两行的候选位置正好在同样的两列上，四个格子就组成一个矩形。两行的这个数字要么落在左上和右下，要么落在右上和左下，不管哪种，这两列里的这个数字都被这两行用掉了，所以两列里其他格子都不能是它。行和列换过来也一样。",
      task: "找出一个 X-Wing，把它能划掉的候选数划掉。" },
    { id: "xy_wing", name: "XY-Wing", techs: ["xy_wing"], tier: "专家", kind: "elim",
      short: "三个双候选格子连成的钳子",
      intro: "找一个只有两个候选数的格子当枢纽，比如 x 和 y。它能看到的另外两个双候选格子分别是 x、z 和 y、z。枢纽如果是 x，第一个翅膀就只能是 z；枢纽如果是 y，第二个翅膀就只能是 z。总之两个翅膀里至少有一个是 z，所以同时能看到两个翅膀的格子都不能是 z。",
      task: "找出一个 XY-Wing，把它能划掉的候选数划掉。" },
    { id: "xyz_wing", name: "XYZ-Wing", techs: ["xyz_wing"], tier: "专家", kind: "elim",
      short: "XY-Wing 的升级版",
      intro: "和 XY-Wing 很像，只是枢纽有三个候选数 x、y、z，两个翅膀分别是 x、z 和 y、z。枢纽如果是 z 就不用说了；如果是 x 或 y，对应的那个翅膀就只能是 z。所以三格里一定有一个 z，同时能看到枢纽和两个翅膀的格子都不能是 z。",
      task: "找出一个 XYZ-Wing，把它能划掉的候选数划掉。" },
    { id: "swordfish", name: "剑鱼", techs: ["swordfish"], tier: "专家", kind: "elim",
      short: "三行三列版本的 X-Wing",
      intro: "X-Wing 的扩展。看某一个数字：如果有三行，这个数字在每一行里的候选位置都落在同样的三列之内（每行两到三个位置），那这三行的三个这个数字正好占掉这三列，三列里其他格子都不能是它。",
      task: "找出一个剑鱼，把它能划掉的候选数划掉。" },
  ];
  var TECH_LESSON = {};
  LESSONS.forEach(function (l, k) { l.techs.forEach(function (t) { TECH_LESSON[t] = k; }); });
  TECH_LESSON.naked_quad = TECH_LESSON.hidden_quad = 99;
  var TECH_NAME = { naked_single: "唯一候选数", hidden_single_box: "宫内排除", hidden_single_line: "行列排除",
    pointing: "区块排除", claiming: "区块排除", naked_pair: "显性数对", hidden_pair: "隐性数对",
    naked_triple: "显性三数组", hidden_triple: "隐性三数组", x_wing: "X-Wing", xy_wing: "XY-Wing",
    xyz_wing: "XYZ-Wing", swordfish: "剑鱼", naked_quad: "显性四数组", hidden_quad: "隐性四数组" };

  function find(t, val, cand) { return FIND[t](val, cand); }
  function next(val, cand, order) {
    order = order || HINT_ORDER;
    for (var k = 0; k < order.length; k++) { var r = FIND[order[k]](val, cand); if (r.length) return r[0]; }
    return null;
  }
  function apply(inst, val, cand) {
    if (inst.place) {
      var c = inst.place[0], d = inst.place[1];
      val[c] = d; cand[c] = 0;
      PEERS[c].forEach(function (j) { cand[j] &= ~bit(d); });
    } else inst.elim.forEach(function (e) { cand[e[0]] &= ~bit(e[1]); });
  }

  // ---------- 讲解文字 ----------
  var unitName = function (u) { return "第 " + (u.i + 1) + " " + ({ row: "行", col: "列", box: "宫" })[u.kind]; };
  var cellName = function (c) { return "第 " + (R(c) + 1) + " 行第 " + (C(c) + 1) + " 列"; };
  function list(ds) { ds = ds.slice(); if (ds.length === 1) return String(ds[0]); var last = ds.pop(); return ds.join("、") + " 和 " + last; }
  function linesName(kind, ls) { return "第 " + ls.map(function (l) { return l + 1; }).join("、") + " " + (kind === "row" ? "行" : "列"); }
  function unitCells(u) { return u.kind === "row" ? ROWS[u.i] : u.kind === "col" ? COLS[u.i] : BOXES[u.i]; }
  function elimCells(inst) { return uniq(inst.elim.map(function (e) { return e[0]; })); }
  function elimDigits(inst) { return uniq(inst.elim.map(function (e) { return e[1]; })).sort(); }
  function F(text, o) { o = o || {}; return { text: text, zone: o.zone || [], pat: o.pat || [], tgt: o.tgt || [], place: o.place || null, strike: o.strike || [], mark: o.mark || [] }; }

  // ctx.basic: 这一步之前没有做过任何排除（候选数完全由已填数字决定）
  function describe(inst, val, cand, ctx) {
    ctx = ctx || {};
    var basic = ctx.basic !== false;
    var t = inst.t, fr = [];
    if (t === "naked_single") {
      var c = inst.place[0], d = inst.place[1];
      var zone = uniq(ROWS[R(c)].concat(COLS[C(c)], BOXES[B(c)])).filter(function (j) { return j !== c; });
      var bc = basicCands(val)[c];
      if (basic || popc(bc) === 1) {
        var seenD = {}, pat = [];
        zone.forEach(function (j) { if (val[j] && !seenD[val[j]]) { seenD[val[j]] = 1; pat.push(j); } });
        var have = Object.keys(seenD).map(Number).sort();
        fr.push(F("看" + cellName(c) + "这一格。它所在的行、列和宫里已经出现了 " + list(have) + "。", { zone: zone, pat: pat, tgt: [c] }));
        fr.push(F("1 到 " + N + " 里只有 " + d + " 没出现过，所以这一格只能填 " + d + "。", { zone: zone, tgt: [c], place: [c, d] }));
      } else {
        fr.push(F("前面的排除做完后，" + cellName(c) + "这一格的候选数只剩下 " + d + "，所以它只能填 " + d + "。", { tgt: [c], place: [c, d], mark: [[c, d]] }));
      }
    } else if (t === "hidden_single_box" || t === "hidden_single_line") {
      var c2 = inst.place[0], d2 = inst.place[1], uc = unitCells(inst.unit);
      var others = uc.filter(function (j) { return j !== c2 && !val[j]; });
      var blockers = [], allByValue = true;
      others.forEach(function (j) {
        var b = PEERS[j].filter(function (q) { return val[q] === d2 && uc.indexOf(q) < 0; });
        if (b.length) { if (!blockers.some(function (x) { return b.indexOf(x) >= 0; })) blockers.push(b[0]); }
        else allByValue = false;
      });
      if (!others.length) {
        fr.push(F("看" + unitName(inst.unit) + "：这里只剩" + cellName(c2) + "这一个空格，还缺的数字是 " + d2 + "。", { zone: uc, tgt: [c2] }));
        fr.push(F("所以这一格填 " + d2 + "。", { zone: uc, tgt: [c2], place: [c2, d2] }));
        fr.forEach(function (f) { f.tech = t; });
        return fr;
      }
      fr.push(F("看" + unitName(inst.unit) + "：这里还没有 " + d2 + "，它一定在剩下的空格里。", { zone: uc }));
      if (allByValue) {
        fr.push(F("高亮的这些 " + d2 + " 所在的行、列、宫会挡住同一条线上的格子，" + unitName(inst.unit) + "里别的空格都放不了 " + d2 + "。", { zone: uc, pat: blockers, tgt: others }));
        fr.push(F("只剩" + cellName(c2) + "这一格能放 " + d2 + "，所以填 " + d2 + "。", { zone: uc, pat: blockers, tgt: [c2], place: [c2, d2] }));
      } else {
        fr.push(F("前面的排除做完后，" + unitName(inst.unit) + "里只有" + cellName(c2) + "这一格还能放 " + d2 + "，所以填 " + d2 + "。", { zone: uc, tgt: [c2], place: [c2, d2] }));
      }
    } else if (t === "pointing") {
      var bx = unitCells(inst.unit), ln = unitCells(inst.line), dp = inst.digit, ec = elimCells(inst);
      fr.push(F("看" + unitName(inst.unit) + "里的数字 " + dp + "：它只可能出现在高亮的这几格。", { zone: bx, pat: inst.pat, mark: inst.pat.map(function (c) { return [c, dp]; }) }));
      fr.push(F("这几格都在" + unitName(inst.line) + "上。所以不管 " + dp + " 最后落在哪一格，" + unitName(inst.line) + "的 " + dp + " 都在这个宫里。", { zone: ln, pat: inst.pat, mark: inst.pat.map(function (c) { return [c, dp]; }) }));
      fr.push(F(unitName(inst.line) + "在宫外的这些格子就不能是 " + dp + "，可以把 " + dp + " 划掉。", { zone: ln, pat: inst.pat, tgt: ec, strike: inst.elim }));
    } else if (t === "claiming") {
      var ln2 = unitCells(inst.unit), bx2 = BOXES[inst.box], dc = inst.digit, ec2 = elimCells(inst);
      fr.push(F("看" + unitName(inst.unit) + "里的数字 " + dc + "：它只可能出现在高亮的这几格。", { zone: ln2, pat: inst.pat, mark: inst.pat.map(function (c) { return [c, dc]; }) }));
      fr.push(F("这几格都在第 " + (inst.box + 1) + " 宫里。所以这个宫的 " + dc + " 一定在" + unitName(inst.unit) + "上。", { zone: bx2, pat: inst.pat, mark: inst.pat.map(function (c) { return [c, dc]; }) }));
      fr.push(F("第 " + (inst.box + 1) + " 宫里不在这条线上的格子就不能是 " + dc + "，可以划掉。", { zone: bx2, pat: inst.pat, tgt: ec2, strike: inst.elim }));
    } else if (/^naked_(pair|triple|quad)$/.test(t)) {
      var uc3 = unitCells(inst.unit), n = inst.pat.length, word = ["", "", "两", "三", "四"][n];
      var mk = []; inst.pat.forEach(function (c) { digs(cand[c]).forEach(function (d) { mk.push([c, d]); }); });
      fr.push(F("看" + unitName(inst.unit) + "里高亮的" + word + "格，它们的候选数合起来只有 " + list(inst.digits) + "。", { zone: uc3, pat: inst.pat, mark: mk }));
      fr.push(F("这" + word + "个数一定分别填在这" + word + "格里，所以" + unitName(inst.unit) + "的其他格子都不能是 " + list(elimDigits(inst)) + "，可以划掉。", { zone: uc3, pat: inst.pat, tgt: elimCells(inst), strike: inst.elim, mark: mk }));
    } else if (/^hidden_(pair|triple|quad)$/.test(t)) {
      var uc4 = unitCells(inst.unit), n2 = inst.pat.length, word2 = ["", "", "两", "三", "四"][n2];
      var mk2 = []; inst.pat.forEach(function (c) { inst.digits.forEach(function (d) { if (cand[c] & bit(d)) mk2.push([c, d]); }); });
      fr.push(F("在" + unitName(inst.unit) + "里，" + list(inst.digits) + " 都只能放在高亮的这" + word2 + "格。", { zone: uc4, pat: inst.pat, mark: mk2 }));
      fr.push(F("这" + word2 + "格必须留给 " + list(inst.digits) + "，所以格子里的其他候选数（" + list(elimDigits(inst)) + "）都可以划掉。", { zone: uc4, pat: inst.pat, tgt: inst.pat, strike: inst.elim, mark: mk2 }));
    } else if (t === "x_wing" || t === "swordfish") {
      var dx = inst.digit, word3 = t === "x_wing" ? "两" : "三";
      var baseCells = [].concat.apply([], inst.base.lines.map(function (l) { return (inst.base.kind === "row" ? ROWS : COLS)[l]; }));
      var covCells = [].concat.apply([], inst.cover.lines.map(function (l) { return (inst.cover.kind === "row" ? ROWS : COLS)[l]; }));
      var mk3 = inst.pat.map(function (c) { return [c, dx]; });
      fr.push(F("看数字 " + dx + "：在" + linesName(inst.base.kind, inst.base.lines) + "，" + dx + " 都只可能出现在" + linesName(inst.cover.kind, inst.cover.lines) + "上（高亮的格子）。", { zone: baseCells, pat: inst.pat, mark: mk3 }));
      fr.push(F("这" + word3 + (inst.base.kind === "row" ? "行" : "列") + "各有一个 " + dx + "，加起来正好" + word3 + "个，而且只能落在这" + word3 + (inst.cover.kind === "row" ? "行" : "列") + "上，所以这" + word3 + (inst.cover.kind === "row" ? "行" : "列") + "的 " + dx + " 都被它们用掉了。", { zone: covCells, pat: inst.pat, mark: mk3 }));
      fr.push(F("这" + word3 + (inst.cover.kind === "row" ? "行" : "列") + "里其他格子都不能是 " + dx + "，可以划掉。", { zone: covCells, pat: inst.pat, tgt: elimCells(inst), strike: inst.elim, mark: mk3 }));
    } else if (t === "xy_wing") {
      var pv = inst.pivot, w = inst.wings, z = inst.digit, x = inst.x, y = inst.y;
      var mk4 = [[pv, x], [pv, y], [w[0], x], [w[0], z], [w[1], y], [w[1], z]];
      fr.push(F("枢纽：" + cellName(pv) + "只能是 " + x + " 或 " + y + "。它能看到两个只有两个候选数的格子：一个是 " + x + "/" + z + "，一个是 " + y + "/" + z + "。", { pat: [pv, w[0], w[1]], mark: mk4 }));
      fr.push(F("枢纽是 " + x + " 时，" + x + "/" + z + " 那格只能是 " + z + "；枢纽是 " + y + " 时，" + y + "/" + z + " 那格只能是 " + z + "。总之两个翅膀里至少有一个是 " + z + "。", { pat: [pv, w[0], w[1]], mark: [[w[0], z], [w[1], z]] }));
      fr.push(F("所以同时能看到这两个翅膀的格子都不能是 " + z + "，可以划掉。", { pat: [pv, w[0], w[1]], tgt: elimCells(inst), strike: inst.elim, mark: [[w[0], z], [w[1], z]] }));
    } else if (t === "xyz_wing") {
      var pv2 = inst.pivot, w2 = inst.wings, z2 = inst.digit;
      var pd = digs(cand[pv2]);
      var mk5 = []; [pv2, w2[0], w2[1]].forEach(function (c) { digs(cand[c]).forEach(function (d) { mk5.push([c, d]); }); });
      fr.push(F("枢纽：" + cellName(pv2) + "的候选数是 " + list(pd) + "。它能看到的两个翅膀分别是 " + digs(cand[w2[0]]).join("/") + " 和 " + digs(cand[w2[1]]).join("/") + "，都含有 " + z2 + "。", { pat: [pv2, w2[0], w2[1]], mark: mk5 }));
      fr.push(F("枢纽如果是 " + z2 + " 就不用说了；如果是另外两个数之一，对应的那个翅膀就只能是 " + z2 + "。所以这三格里一定有一个 " + z2 + "。", { pat: [pv2, w2[0], w2[1]], mark: [[pv2, z2], [w2[0], z2], [w2[1], z2]] }));
      fr.push(F("同时能看到这三格的格子都不能是 " + z2 + "，可以划掉。", { pat: [pv2, w2[0], w2[1]], tgt: elimCells(inst), strike: inst.elim, mark: [[pv2, z2], [w2[0], z2], [w2[1], z2]] }));
    }
    fr.forEach(function (f) { f.tech = t; });
    return fr;
  }

  // 讲解型提示：从当前盘面（只看填对的数字）一路推到下一个能填的格子
  function hintChain(val, maxSteps) {
    var v = val.slice(), cand = basicCands(v), insts = [];
    for (var k = 0; k < (maxSteps || 40); k++) {
      var inst = next(v, cand);
      if (!inst) return { steps: build_(val, insts), stuck: true };
      insts.push(inst);
      if (inst.place) {
        insts = prune(val, insts);
        return { steps: build_(val, insts), place: insts[insts.length - 1].place };
      }
      apply(inst, v, cand);
    }
    return { steps: build_(val, insts), stuck: true };
  }
  // 同一个“形状”的推理（同一技巧、同样的格子和数字），用来判断去掉别的步骤后它还成不成立
  function sig(x) { return JSON.stringify([x.t, x.digit, x.unit, x.line, x.box, x.base, x.cover, x.pivot, x.wings, x.digits, x.pat, x.place]); }
  // 按顺序重放这些排除，每一步都必须在当时的盘面上仍然成立；成立就返回重放后的实例（划掉的候选数按当时实际情况），否则返回 null
  function replay(val, list) {
    var v = val.slice(), cand = basicCands(v), out = [];
    for (var k = 0; k < list.length; k++) {
      var want = sig(list[k]), got = null, r = FIND[list[k].t](v, cand);
      for (var q = 0; q < r.length; q++) if (sig(r[q]) === want) { got = r[q]; break; }
      if (!got && list[k].place) {   // 最后一步填数：换成别的单数技巧也行，只要填的是同一格同一个数
        var SINGLES = ["hidden_single_box", "hidden_single_line", "naked_single"];
        for (var a = 0; a < SINGLES.length && !got; a++) {
          var rr = FIND[SINGLES[a]](v, cand);
          for (var b = 0; b < rr.length; b++) if (rr[b].place[0] === list[k].place[0] && rr[b].place[1] === list[k].place[1]) { got = rr[b]; break; }
        }
      }
      if (!got) return null;
      out.push(got);
      if (!got.place) apply(got, v, cand);
    }
    return out;
  }
  // 逐个试着去掉排除步骤：去掉后剩下的推理仍然成立、最后还能填同一个数，就不讲这一步
  function prune(val, insts) {
    var cur = insts, changed = true;
    // 删掉一步后，前面原来删不掉的步骤可能也变得可以删了：从头再试，直到一整轮都删不掉
    while (changed) {
      changed = false;
      for (var i = 0; i < cur.length - 1; i++) {
        var r = replay(val, cur.slice(0, i).concat(cur.slice(i + 1)));
        if (r) { cur = r; changed = true; break; }
      }
    }
    return replay(val, cur) || insts;
  }
  function build_(val, insts) {
    var v = val.slice(), cand = basicCands(v), steps = [];
    insts.forEach(function (inst, k) {
      steps.push({ inst: inst, frames: describe(inst, v, cand, { basic: k === 0 }), cand: cand.slice() });
      if (!inst.place) apply(inst, v, cand);
    });
    return steps;
  }

  return { N: N, basicCands: basicCands, find: find, next: next, apply: apply, describe: describe, hintChain: hintChain, replay: replay,
    LESSONS: LESSONS, TECH_LESSON: TECH_LESSON, TECH_NAME: TECH_NAME, HINT_ORDER: HINT_ORDER, PEERS: PEERS, digs: digs, popc: popc, bit: bit };
  }
  var se = build(9, 3, 3);
  se.six = build(6, 2, 3);
  return se;
})();
if (typeof module !== "undefined") module.exports = SE;
