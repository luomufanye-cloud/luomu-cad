/*
MIT License

Copyright (c) 2026 ZWD11

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Pinned ZWD11/house-plan-designer commit 5f55f7f79d6b27dad3e7c0ece5f5f677ad70b0e5.
Extracted pure component functions from assets/template.html.
Adaptations: explicit exterior side, unsupported raster patterns/external images fail visibly.
Original upstream identifiers retained for source comparison.
*/
function _e(t, e) {
  const n = parseInt(t.slice(1), 16);
  let i = n >> 16, s = n >> 8 & 255, o = n & 255;
  const a = e < 0 ? 0 : 255, r = Math.abs(e);
  return i = Math.round(i + (a - i) * r), s = Math.round(s + (a - s) * r), o = Math.round(o + (a - o) * r), "#" + (1 << 24 | i << 16 | s << 8 | o).toString(16).slice(1);
}
;
function fs(t, e, n, i, s, o) {
  o = Math.max(0, Math.min(o, i / 2, s / 2)), t.moveTo(e + o, n), t.lineTo(e + i - o, n), t.quadraticCurveTo(e + i, n, e + i, n + o), t.lineTo(e + i, n + s - o), t.quadraticCurveTo(e + i, n + s, e + i - o, n + s), t.lineTo(e + o, n + s), t.quadraticCurveTo(e, n + s, e, n + s - o), t.lineTo(e, n + o), t.quadraticCurveTo(e, n, e + o, n), t.closePath();
}
;
const hr = { arc: { name: "\u534A\u5706\u5F27\u5F62", w: 3200, d: 1500, path: "-1350,450,950|-1050,-150,950|-450,-500,950|0,-560,950|450,-500,950|1050,-150,950|1350,450,950", open: 0 }, cornerChaise: { name: "\u8F6C\u89D2\u5F27\u5F62\uFF08\u5E26\u8D35\u5983\u4F4D\uFF09", w: 2600, d: 3400, path: "-577,1538,880|-651,920,1250|-651,327,1250|-370,-191,1000|311,-784,880|1027,-1351,880", open: 420 }, roundL: { name: "\u5706\u89D2 L \u5F62", w: 3200, d: 2400, path: "1450,750,950|200,750,950|-700,700,950|-1150,250,950|-1200,-600,950|-1200,-1050,950", open: 0 }, serpentine: { name: "S \u5F62\u86C7\u5F62", w: 4200, d: 1900, path: "-1900,350,900|-1250,-350,900|-450,-500,900|200,-150,900|900,350,900|1650,250,900|2000,-150,900", open: 0 }, crescent: { name: "\u6708\u7259\u5F62\uFF08\u4E24\u5934\u6536\u7A84\uFF09", w: 3e3, d: 1300, path: "-1400,350,650|-900,-150,900|0,-400,1000|900,-150,900|1400,350,650", open: 0 } };
const Lh = /* @__PURE__ */ new Map();
function V3(t) {
  var i, s, o, a;
  const e = JSON.stringify([t.type, t.w, t.d, (i = t.opt) == null ? void 0 : i.path, (s = t.opt) == null ? void 0 : s.open, (o = t.opt) == null ? void 0 : o.back, (a = t.opt) == null ? void 0 : a.flip]);
  let n = Lh.get(e);
  return n || (n = HT(t), Lh.size > 200 && Lh.clear(), Lh.set(e, n)), n;
}
;
function BT(t) {
  var f, u, h;
  const e = String(((f = t.opt) == null ? void 0 : f.path) ?? "").trim();
  if (e) {
    const d = e.split("|").map((p) => p.split(",").map(Number)).filter((p) => p.length >= 2 && p.every(Number.isFinite)).map((p) => ({ p: { x: p[0], y: p[1] }, d: p[2] > 0 ? p[2] : 0 }));
    if (d.length >= 2) {
      const p = ((u = d.find((m) => m.d)) == null ? void 0 : u.d) || 900, g = (h = t.opt) != null && h.flip ? -1 : 1;
      return d.map((m) => ({ p: { x: m.p.x * g, y: m.p.y }, d: m.d || p }));
    }
  }
  const n = Math.min(1e3, Math.max(650, t.d * 0.75)), i = t.w / 2, s = t.d / 2, o = i - n / 2, a = Math.max(200, t.d - n / 2), r = [], l = 9, c = Math.PI * 0.78;
  for (let d = 0; d < l; d++) {
    const p = -Math.PI / 2 - c / 2 + c * d / (l - 1);
    r.push({ p: { x: Math.cos(p) * o, y: s + Math.sin(p) * a }, d: n });
  }
  return r;
}
;
function zT(t) {
  const e = [], n = [], i = (s) => t[Math.max(0, Math.min(t.length - 1, s))];
  for (let s = 0; s < t.length - 1; s++) {
    const o = i(s - 1).p, a = i(s).p, r = i(s + 1).p, l = i(s + 2).p, c = Math.hypot(r.x - a.x, r.y - a.y), f = Math.max(2, Math.ceil(c / 40));
    for (let u = 0; u < f; u++) {
      const h = u / f, d = h * h, p = d * h, g = (m, y, b, x) => 0.5 * (2 * y + (-m + b) * h + (2 * m - 5 * y + 4 * b - x) * d + (-m + 3 * y - 3 * b + x) * p);
      e.push({ x: g(o.x, a.x, r.x, l.x), y: g(o.y, a.y, r.y, l.y) }), n.push(i(s).d + (i(s + 1).d - i(s).d) * h);
    }
  }
  return e.push({ ...t[t.length - 1].p }), n.push(t[t.length - 1].d), { pts: e, dep: n };
}
;
function HT(t) {
  var Y, V, Q;
  const { pts: e, dep: n } = zT(BT(t)), i = e.length, s = [], o = [0], a = (Y = t.opt) != null && Y.flip ? -1 : 1;
  for (let L = 0; L < i; L++) {
    const j = e[Math.max(0, L - 1)], X = e[Math.min(i - 1, L + 1)], W = X.x - j.x, te = X.y - j.y, se = Math.hypot(W, te) || 1;
    s.push({ x: a * te / se, y: -a * W / se }), L && o.push(o[L - 1] + Math.hypot(e[L].x - e[L - 1].x, e[L].y - e[L - 1].y));
  }
  const r = (L, j) => ({ x: e[L].x + s[L].x * j, y: e[L].y + s[L].y * j }), l = (L) => r(L, n[L] / 2), c = (L) => r(L, -n[L] / 2), f = (L, j) => {
    const X = -s[L].y * j, W = s[L].x * j, te = Math.min(160, n[L] * 0.22), se = [];
    for (let re = 0; re <= 8; re++) {
      const z = Math.PI * re / 8, ne = Math.cos(z) * n[L] / 2, ie = Math.sin(z) * te;
      se.push({ x: e[L].x + s[L].x * ne + X * ie, y: e[L].y + s[L].y * ne + W * ie });
    }
    return se;
  }, u = [...Array.from({ length: i }, (L, j) => l(j)), ...f(i - 1, 1).slice(1, -1), ...Array.from({ length: i }, (L, j) => c(i - 1 - j)), ...f(0, -1).reverse().slice(1, -1)], h = u.map((L) => L.x), d = u.map((L) => L.y), p = Math.min(...h), g = Math.max(...h), m = Math.min(...d), y = Math.max(...d), b = t.w / Math.max(1, g - p), x = t.d / Math.max(1, y - m), v = (p + g) / 2, w = (m + y) / 2, M = (L) => ({ x: (L.x - v) * b, y: (L.y - w) * x }), S = Math.sqrt(b * x), A = Math.min(260, Math.max(150, Number((V = t.opt) == null ? void 0 : V.back) || 220)) * S, T = Math.max(0, Number((Q = t.opt) == null ? void 0 : Q.open) || 0), _ = e.map(M), R = n.map((L) => L * S), P = _.map((L, j) => {
    const X = _[Math.max(0, j - 1)], W = _[Math.min(i - 1, j + 1)], te = W.x - X.x, se = W.y - X.y, re = Math.hypot(te, se) || 1;
    return { x: a * se / re, y: -a * te / re };
  }), D = [0];
  for (let L = 1; L < i; L++) D.push(D[L - 1] + Math.hypot(_[L].x - _[L - 1].x, _[L].y - _[L - 1].y));
  const E = (L, j) => ({ x: _[L].x + P[L].x * j, y: _[L].y + P[L].y * j }), I = Math.max(0, D.findIndex((L) => L >= T * S)), N = I < i - 2 ? [...Array.from({ length: i - I }, (L, j) => E(I + j, R[I + j] / 2)), ...Array.from({ length: i - I }, (L, j) => E(i - 1 - j, R[i - 1 - j] / 2 - A))] : [], U = [...Array.from({ length: i }, (L, j) => E(j, j >= I && N.length ? R[j] / 2 - A : R[j] / 2 - 40)), ...Array.from({ length: i }, (L, j) => E(i - 1 - j, -R[i - 1 - j] / 2 + 30))], $ = D[i - 1], H = Math.max(1, Math.round($ / 800)), F = Array.from({ length: H - 1 }, (L, j) => $ * (j + 1) / H), G = [];
  for (let L = 0; L < i - 1; L += 4) {
    const j = Math.min(i - 1, L + 4);
    G.push([E(L, R[L] / 2), E(j, R[j] / 2), E(j, -R[j] / 2), E(L, -R[L] / 2)]);
  }
  return { pts: _, dep: R, nrm: P, s: D, outline: u.map(M), back: N, seat: U, splits: F, quads: G, bk: A, open: T * S, len: $ };
}
;
function Jv(t, e) {
  const n = Math.max(1, t.s.findIndex((a) => a >= e)), i = n - 1, s = Math.min(1, Math.max(0, (e - t.s[i]) / Math.max(1e-6, t.s[n] - t.s[i]))), o = (a, r) => a + (r - a) * s;
  return { p: { x: o(t.pts[i].x, t.pts[n].x), y: o(t.pts[i].y, t.pts[n].y) }, d: o(t.dep[i], t.dep[n]), n: { x: o(t.nrm[i].x, t.nrm[n].x), y: o(t.nrm[i].y, t.nrm[n].y) } };
}
;
const v1 = [{ group: "\u5367\u5BA4", items: [{ key: "bed18", type: "bed", name: "\u53CC\u4EBA\u5E8A 1.8m", w: 1800, d: 2100, h: 1050, color: "#a9bccf" }, { key: "bed15", type: "bed", name: "\u53CC\u4EBA\u5E8A 1.5m", w: 1500, d: 2050, h: 1e3, color: "#d9b99b" }, { key: "bed12", type: "bed", name: "\u5355\u4EBA\u5E8A 1.2m", w: 1200, d: 2e3, h: 950, color: "#b8c9a8" }, { key: "bed20", type: "bed", name: "\u53CC\u4EBA\u5E8A 2.0m", w: 2e3, d: 2200, h: 1050, color: "#c9b8a6" }, { key: "roundBed", type: "roundBed", name: "\u5706\u5E8A", w: 2200, d: 2200, h: 900, color: "#d9cbbb" }, { key: "bunkBed", type: "bunkBed", name: "\u4E0A\u4E0B\u5E8A", w: 1e3, d: 2e3, h: 1750, color: "#c9a77d" }, { key: "crib", type: "crib", name: "\u5A74\u513F\u5E8A", w: 1250, d: 700, h: 950, color: "#f1e6d6" }, { key: "tatami", type: "tatami", name: "\u69BB\u69BB\u7C73", w: 2e3, d: 2e3, h: 400, color: "#d8c7a3" }, { key: "nightstand", type: "nightstand", name: "\u5E8A\u5934\u67DC\uFF08\u53F0\u706F\u53EF\u70B9\u4EAE\uFF09", w: 500, d: 420, h: 500, color: "#b48a62", pw: [["socket", 700, -80], ["socketUSB", 700, 80]] }, { key: "bedBench", type: "bedBench", name: "\u5E8A\u5C3E\u51F3", w: 1400, d: 400, h: 450, color: "#8e7b6a" }, { key: "wardrobe", type: "wardrobe", name: "\u8863\u67DC", w: 2e3, d: 600, h: 2400, color: "#ece7df" }, { key: "chest", type: "chest", name: "\u4E94\u6597\u67DC", w: 900, d: 480, h: 1100, color: "#d8c7ae" }, { key: "coatRack", type: "coatRack", name: "\u8863\u5E3D\u67B6", w: 500, d: 500, h: 1750, color: "#6b5442" }, { key: "stool", type: "stool", name: "\u5706\u51F3 / \u5316\u5986\u51F3", w: 400, d: 400, h: 450, color: "#c9b8a6" }, { key: "bayCushion", type: "bayCushion", name: "\u98D8\u7A97\u57AB", w: 1800, d: 500, h: 80, color: "#e3d7c6" }, { key: "dresser", type: "dresser", name: "\u68B3\u5986\u53F0", w: 1e3, d: 450, h: 750, color: "#e7ddd0", pw: [["socket", 1e3]] }, { key: "mirror", type: "mirror", name: "\u7A7F\u8863\u955C", w: 600, d: 60, h: 1650, color: "#cdb79a" }, { key: "desk", type: "desk", name: "\u4E66\u684C", w: 1200, d: 600, h: 750, color: "#c29a6b", pw: [["socket", 1e3, -300], ["net", 1e3, 0], ["socketUSB", 1e3, 300]] }, { key: "officeChair", type: "officeChair", name: "\u529E\u516C\u6905", w: 600, d: 600, h: 1050, color: "#3d434d" }, { key: "lDesk", type: "lDesk", name: "L \u5F62\u4E66\u684C", w: 1600, d: 1400, h: 750, color: "#c29a6b", pw: [["socket", 1e3, -300], ["net", 1e3, 0], ["socketUSB", 1e3, 300]] }, { key: "kidsDesk", type: "desk", name: "\u513F\u7AE5\u5B66\u4E60\u684C", w: 1e3, d: 600, h: 700, color: "#e8d9b5", pw: [["socket", 950, 0]] }, { key: "gamingChair", type: "officeChair", name: "\u7535\u7ADE\u6905", w: 700, d: 700, h: 1300, color: "#2b2e33" }, { key: "fileCabinet", type: "chest", name: "\u6587\u4EF6\u67DC", w: 450, d: 550, h: 1050, color: "#9aa1a8" }, { key: "bookshelf", type: "bookshelf", name: "\u4E66\u67B6", w: 900, d: 350, h: 2e3, color: "#c7a27a" }] }, { group: "\u5BA2\u9910\u5385", items: [{ key: "sofa", type: "sofa", name: "\u4E09\u4EBA\u6C99\u53D1", w: 2200, d: 950, h: 820, color: "#8e9aa8", pw: [["socket", 300, -1250], ["socket", 300, 1250]] }, { key: "lSofa", type: "lSofa", name: "L \u5F62\u8F6C\u89D2\u6C99\u53D1", w: 2800, d: 1700, h: 820, color: "#b9b2a6", pw: [["socket", 300, -1550], ["socket", 300, 1550]] }, { key: "loveseat", type: "sofa", name: "\u53CC\u4EBA\u6C99\u53D1", w: 1600, d: 900, h: 820, color: "#a3aeb8", pw: [["socket", 300, -950], ["socket", 300, 950]] }, { key: "uSofa", type: "uSofa", name: "U \u5F62\u6C99\u53D1", w: 3200, d: 2e3, h: 820, color: "#c4bcae", pw: [["socket", 300, -1750], ["socket", 300, 1750]] }, { key: "curvedSofa", type: "curvedSofa", name: "\u5F27\u5F62\u6C99\u53D1", w: 2600, d: 1100, h: 780, color: "#e7dccb" }, { key: "bendSofa", type: "bendSofa", name: "\u5F02\u5F62\u7EC4\u5408\u6C99\u53D1\uFF08\u66F2\u7EBF\u53EF\u8C03\uFF09", w: 3200, d: 2200, h: 760, color: "#d8d2c8", pw: [["socket", 300, -1700], ["socket", 300, 1700]] }, ...["cornerChaise", "roundL", "serpentine", "crescent"].map((t) => ({ key: "bendSofa_" + t, type: "bendSofa", name: { cornerChaise: "\u8F6C\u89D2\u5F27\u5F62\u6C99\u53D1\uFF08\u5E26\u8D35\u5983\uFF09", roundL: "\u5706\u89D2 L \u5F62\u6C99\u53D1", serpentine: "S \u5F62\u86C7\u5F62\u6C99\u53D1", crescent: "\u6708\u7259\u5F62\u6C99\u53D1" }[t], w: hr[t].w, d: hr[t].d, h: 760, color: "#d8d2c8", opt: { path: hr[t].path, open: hr[t].open, shape: t } })), { key: "chaise", type: "chaise", name: "\u8D35\u5983\u6905", w: 1700, d: 750, h: 800, color: "#b7a28a" }, { key: "beanbag", type: "beanbag", name: "\u61D2\u4EBA\u6C99\u53D1", w: 900, d: 900, h: 700, color: "#c96f4a" }, { key: "ottoman", type: "ottoman", name: "\u5706\u811A\u51F3 / \u5750\u58A9", w: 550, d: 550, h: 420, color: "#8fa58a" }, { key: "rockingChair", type: "rockingChair", name: "\u6447\u6905", w: 700, d: 950, h: 900, color: "#a07a52" }, { key: "hangingChair", type: "hangingChair", name: "\u540A\u6905", w: 1e3, d: 1e3, h: 1900, color: "#c9b18e" }, { key: "armchair", type: "armchair", name: "\u5355\u4EBA\u6C99\u53D1", w: 850, d: 850, h: 800, color: "#c98a5f" }, { key: "coffeeTable", type: "coffeeTable", name: "\u8336\u51E0", w: 1200, d: 600, h: 400, color: "#a47a55" }, { key: "roundCoffee", type: "roundTable", name: "\u5706\u8336\u51E0", w: 900, d: 900, h: 380, color: "#a47a55" }, { key: "ovalCoffee", type: "ovalTable", name: "\u692D\u5706\u8336\u51E0", w: 1300, d: 800, h: 380, color: "#a47a55" }, { key: "tvCabinet", type: "tvCabinet", name: "\u7535\u89C6\u67DC\uFF08\u7535\u89C6\u53EF\u5F00\u5173\uFF09", w: 2e3, d: 400, h: 450, color: "#e6e0d6", pw: [["tv", 1100, 0], ["socket", 1100, -350], ["socket", 1100, 350], ["net", 300, 600], ["socket", 300, -600]] }, { key: "diningTable", type: "diningTable", name: "\u9910\u684C", w: 1600, d: 900, h: 750, color: "#b98c5f" }, { key: "longTable", type: "diningTable", name: "\u957F\u9910\u684C\uFF088 \u4EBA\uFF09", w: 2400, d: 1e3, h: 750, color: "#8e6a4a" }, { key: "roundTable", type: "roundTable", name: "\u5706\u9910\u684C", w: 1300, d: 1300, h: 750, color: "#b98c5f" }, { key: "ovalTable", type: "ovalTable", name: "\u692D\u5706\u9910\u684C", w: 2400, d: 1100, h: 750, color: "#b98c5f" }, { key: "booth", type: "booth", name: "\u5361\u5EA7", w: 1800, d: 600, h: 1e3, color: "#8a7d6e" }, { key: "diningBench", type: "bedBench", name: "\u9910\u51F3", w: 1400, d: 350, h: 450, color: "#9c7652" }, { key: "chair", type: "chair", name: "\u9910\u6905", w: 460, d: 520, h: 880, color: "#5d636e" }, { key: "sideboard", type: "sideboard", name: "\u9910\u8FB9\u67DC", w: 1600, d: 400, h: 2200, color: "#e9e4dc", pw: [["socket", 1100, -400], ["socket", 1100, 400]] }, { key: "wineCabinet", type: "wineCabinet", name: "\u9152\u67DC", w: 900, d: 450, h: 2e3, color: "#4b3a2e", pw: [["socket", 300]] }, { key: "displayCabinet", type: "displayCabinet", name: "\u5C55\u793A\u67DC\uFF08\u73BB\u7483\u95E8\uFF09", w: 1e3, d: 400, h: 2e3, color: "#e8e1d6" }, { key: "consoleTable", type: "consoleTable", name: "\u7384\u5173\u684C / \u8FB9\u684C", w: 1200, d: 350, h: 800, color: "#9c7652" }, { key: "fireplace", type: "fireplace", name: "\u7535\u58C1\u7089", w: 1400, d: 400, h: 1100, color: "#e9e3da", pw: [["socket", 300]] }, { key: "fishTank", type: "fishTank", name: "\u9C7C\u7F38", w: 1200, d: 450, h: 1300, color: "#2b2e33", pw: [["socket", 300, -300], ["socket", 300, 300]] }, { key: "projScreen", type: "projScreen", name: "\u6295\u5F71\u5E55\u5E03", w: 2400, d: 80, h: 1500, z: 700, color: "#f4f4f2", pw: [["socket", 2400, 0]] }, { key: "speaker", type: "speaker", name: "\u843D\u5730\u97F3\u7BB1", w: 300, d: 350, h: 1e3, color: "#2b2e33", pw: [["socket", 300]] }, { key: "screenDivider", type: "screenDivider", name: "\u5C4F\u98CE", w: 1800, d: 40, h: 1800, color: "#b9956d" }, { key: "kitchenIsland", type: "kitchenIsland", name: "\u4E2D\u5C9B\u53F0", w: 1800, d: 900, h: 900, color: "#efebe5" }, { key: "barStool", type: "barStool", name: "\u5427\u6905", w: 400, d: 400, h: 750, color: "#3b3f46" }, { key: "shoeCabinet", type: "shoeCabinet", name: "\u978B\u67DC", w: 1200, d: 350, h: 1e3, color: "#e6e0d6" }, { key: "hallCabinet", type: "cabinet", name: "\u7384\u5173\u67DC\uFF08\u4E2D\u7A7A\uFF09", w: 1200, d: 400, h: 2400, color: "#e9e4dc", cab: { kind: "tall", door: "swing", cols: ["door", "open", "door"] } }, { key: "entryBench", type: "entryBench", name: "\u6362\u978B\u51F3", w: 900, d: 350, h: 450, color: "#b38b63" }, { key: "piano", type: "piano", name: "\u7ACB\u5F0F\u94A2\u7434", w: 1500, d: 600, h: 1250, color: "#1d1f23", pw: [["socket", 300]] }, { key: "rug", type: "rug", name: "\u5730\u6BEF", w: 2e3, d: 1700, h: 12, color: "#d9cbb5" }, { key: "plant", type: "plant", name: "\u7EFF\u690D", w: 500, d: 500, h: 1400, color: "#5f8f55" }] }, { group: "\u5BB6\u7535", items: [{ key: "acWall", type: "acWall", name: "\u6302\u673A\u7A7A\u8C03", w: 900, d: 260, h: 300, z: 2150, color: "#f5f6f7", pw: [["socketAC", 2200, 600], ["acHole", 2350, -600]] }, { key: "acFloor", type: "acFloor", name: "\u67DC\u673A\u7A7A\u8C03", w: 520, d: 380, h: 1850, color: "#f5f6f7", pw: [["socket16", 300], ["acHole", 300, 450]] }, { key: "waterHeater", type: "waterHeater", name: "\u7535\u70ED\u6C34\u5668", w: 800, d: 450, h: 450, z: 1800, color: "#f3f4f5", pw: [["socket16", 2100, 550], ["cold", 1650, 150], ["hot", 1650, -150]] }, { key: "miniHeater", type: "waterHeater", name: "\u5C0F\u53A8\u5B9D\uFF08\u53F0\u4E0B\u50A8\u6C34\u5F0F\uFF09", w: 380, d: 320, h: 420, z: 80, color: "#f3f4f5", pw: [["socket", 600, 0], ["cold", 450, 80], ["hot", 450, -80]] }, { key: "gasHeater", type: "gasHeater", name: "\u71C3\u6C14\u70ED\u6C34\u5668", w: 360, d: 180, h: 600, z: 1400, color: "#e9ebee", pw: [["socket", 1300, 320], ["gas", 1250, 0], ["cold", 1250, 130], ["hot", 1250, -130]] }, { key: "waterDispenser", type: "waterDispenser", name: "\u996E\u6C34\u673A", w: 320, d: 330, h: 1050, color: "#f1f2f3", pw: [["socket", 300]] }, { key: "purifier", type: "purifier", name: "\u51C0\u6C34\u5668\uFF08\u53F0\u4E0B\uFF09", w: 400, d: 200, h: 420, color: "#e8eaed", pw: [["socket", 500, 150], ["cold", 500, -150], ["waste", 400, 0]] }, { key: "dishwasher", type: "dishwasher", name: "\u6D17\u7897\u673A", w: 600, d: 600, h: 820, color: "#c7ccd2", pw: [["socket", 300], ["cold", 400, 200], ["waste", 300, -200]] }, { key: "tallOven", type: "tallOven", name: "\u7535\u5668\u9AD8\u67DC\uFF08\u84B8\u70E4\u7BB1\uFF09", w: 600, d: 600, h: 2200, color: "#efebe5", pw: [["socket16", 300]] }, { key: "hood", type: "hood", name: "\u6CB9\u70DF\u673A", w: 900, d: 520, h: 550, z: 1550, color: "#b9bec5", pw: [["socketHood", 2150]] }, { key: "microwave", type: "microwave", name: "\u5FAE\u6CE2\u7089", w: 480, d: 380, h: 280, z: 900, color: "#d4d8dd", pw: [["socket", 1100]] }, { key: "washer", type: "washer", name: "\u6D17\u8863\u673A", w: 600, d: 600, h: 850, color: "#f2f3f4", pw: [["socketW", 1300, 200], ["cold", 1200, -150]] }, { key: "dryer", type: "dryer", name: "\u70D8\u5E72\u673A", w: 600, d: 620, h: 850, color: "#eef0f2", pw: [["socketW", 1300]] }, { key: "wallTV", type: "wallTV", name: "\u58C1\u6302\u7535\u89C6\uFF08\u53EF\u5F00\u5173\uFF09", w: 1450, d: 60, h: 830, z: 850, color: "#121417", pw: [["tv", 1100, 0], ["socket", 1100, -300], ["net", 1100, 300]] }, { key: "airPurifier", type: "airPurifier", name: "\u7A7A\u6C14\u51C0\u5316\u5668", w: 380, d: 250, h: 700, color: "#f4f4f2", pw: [["socket", 300]] }, { key: "robotVac", type: "robotVac", name: "\u626B\u5730\u673A\u5668\u4EBA\u57FA\u7AD9", w: 380, d: 420, h: 450, color: "#2d3036", pw: [["socket", 300]] }, { key: "treadmill", type: "treadmill", name: "\u8DD1\u6B65\u673A", w: 800, d: 1800, h: 1350, color: "#2b2e33", pw: [["socket", 300]] }] }, { group: "\u706F\u9970 \xB7 \u7A97\u5E18", items: [{ key: "floorLamp", type: "floorLamp", name: "\u843D\u5730\u706F\uFF08\u53EF\u70B9\u4EAE\uFF09", w: 400, d: 400, h: 1650, color: "#e8dcc6", pw: [["socket", 300]] }, { key: "deskLamp", type: "deskLamp", name: "\u53F0\u706F\uFF08\u53EF\u70B9\u4EAE\uFF09", w: 250, d: 250, h: 450, z: 750, color: "#f1e7d4" }, { key: "curtain", type: "curtain", name: "\u843D\u5730\u7A97\u5E18\uFF08\u53EF\u5F00\u5408\uFF09", w: 2400, d: 160, h: 2650, color: "#d9d0c1" }, { key: "sheer", type: "curtain", name: "\u7EB1\u5E18\uFF08\u53EF\u5F00\u5408\uFF09", w: 2400, d: 120, h: 2650, color: "#f4f1ea" }] }, { group: "\u88C5\u9970 \xB7 \u7EFF\u690D", items: [{ key: "bigPlant", type: "plant", name: "\u5927\u578B\u7EFF\u690D", w: 800, d: 800, h: 1800, color: "#4f7f45" }, { key: "smallPlant", type: "plant", name: "\u5C0F\u76C6\u683D", w: 300, d: 300, h: 500, color: "#6f9a5f" }, { key: "hangingPlant", type: "hangingPlant", name: "\u540A\u5170\uFF08\u5438\u9876\uFF09", w: 400, d: 400, h: 600, color: "#6f9a5f", ceil: true }, { key: "floorVase", type: "vase", name: "\u843D\u5730\u82B1\u74F6", w: 350, d: 350, h: 900, color: "#c9b89f" }, { key: "wallPanel", type: "wallPanel", name: "\u5899\u9762\u9020\u578B\u677F", w: 2400, d: 60, h: 2600, color: "#b08a64" }, { key: "wallArt", type: "wallArt", name: "\u88C5\u9970\u753B", w: 900, d: 40, h: 650, z: 1350, color: "#c8442b" }, { key: "wallArt3", type: "wallArt", name: "\u88C5\u9970\u753B\uFF08\u4E09\u8054\uFF09", w: 1500, d: 40, h: 600, z: 1350, color: "#6f8fa8" }, { key: "wallClock", type: "clock", name: "\u6302\u949F", w: 400, d: 50, h: 400, z: 1900, color: "#2b2e33" }, { key: "roundRug", type: "rugRound", name: "\u5706\u5730\u6BEF", w: 2e3, d: 2e3, h: 12, color: "#cdbfa8" }, { key: "doormat", type: "rug", name: "\u95E8\u53E3\u5730\u57AB", w: 900, d: 600, h: 10, color: "#8a7d6e" }, { key: "fan", type: "fan", name: "\u843D\u5730\u6247", w: 400, d: 400, h: 1200, color: "#e9ebee", pw: [["socket", 300]] }, { key: "radiator", type: "radiator", name: "\u6696\u6C14\u7247", w: 1e3, d: 100, h: 600, z: 150, color: "#f2f2f0" }] }, { group: "\u5B9A\u5236\u67DC\u4F53\uFF08\u5C3A\u5BF8 / \u5206\u683C / \u9020\u578B\u90FD\u53EF\u6539\uFF09", items: [{ key: "cabWardrobe", type: "cabinet", name: "\u5B9A\u5236\u8863\u67DC", w: 2400, d: 600, h: 2600, color: "#efeae2", cab: { kind: "tall", door: "swing", cols: ["hang", "drawer", "hang", "door"], top: 450 } }, { key: "cabSlide", type: "cabinet", name: "\u63A8\u62C9\u95E8\u8863\u67DC", w: 2e3, d: 650, h: 2600, color: "#d9d4cc", cab: { kind: "tall", door: "sliding", cols: ["hang", "door", "hang"] } }, { key: "cabCorner", type: "cabinet", name: "\u8F6C\u89D2\u8863\u67DC\uFF08L \u5F62\uFF09", w: 2400, d: 1800, h: 2600, color: "#efeae2", cab: { kind: "tall", door: "swing", cols: ["hang", "drawer", "hang"], shape: "L", corner: "left", depth: 600, cols2: ["hang", "door"], top: 450 } }, { key: "cabShoe", type: "cabinet", name: "\u5B9A\u5236\u978B\u67DC\uFF08\u4E2D\u7A7A\uFF09", w: 1200, d: 380, h: 2400, color: "#e9e4dc", cab: { kind: "tall", door: "swing", cols: ["niche", "niche"], plinth: 0, handle: "hidden" } }, { key: "cabSideboard", type: "cabinet", name: "\u5B9A\u5236\u9910\u8FB9\u67DC", w: 1800, d: 400, h: 2400, color: "#e6e0d6", cab: { kind: "tall", door: "swing", cols: ["door", "niche", "glass", "niche"], ws: [400, 500, 500, 400] } }, { key: "cabTall", type: "cabinet", name: "\u4E66\u67DC / \u9AD8\u67DC", w: 1200, d: 400, h: 2400, color: "#c9ab88", cab: { kind: "tall", door: "swing", cols: ["open", "door", "open"] } }, { key: "cabBase", type: "cabinet", name: "\u5730\u67DC", w: 1600, d: 600, h: 850, color: "#f0ede8", cab: { kind: "base", door: "swing", cols: ["door", "drawer", "door"] } }, { key: "cabWall", type: "cabinet", name: "\u540A\u67DC", w: 1600, d: 350, h: 700, color: "#f0ede8", z: 1500, cab: { kind: "wall", door: "swing", cols: ["door", "door", "door"] } }, { key: "cabTV", type: "cabinet", name: "\u60AC\u7A7A\u7535\u89C6\u67DC", w: 2400, d: 400, h: 400, color: "#e6e0d6", z: 250, cab: { kind: "base", door: "swing", cols: ["drawer", "open", "open", "drawer"] } }] }, { group: "\u53A8\u623F", items: [{ key: "counter", type: "counter", name: "\u4E00\u5B57\u6A71\u67DC\uFF08\u53EF\u5B9A\u5236\uFF09", w: 2100, d: 600, h: 900, color: "#f0ede8", pw: [["socket", 1100, -100], ["socket", 1100, 250], ["socketHood", 2150, 540], ["cold", 500, -600], ["hot", 500, -750], ["waste", 400, -675], ["gas", 600, 300]] }, { key: "fridge", type: "fridge", name: "\u51B0\u7BB1", w: 700, d: 700, h: 1850, color: "#d8dde2", pw: [["socket", 300]] }, { key: "fridgeDouble", type: "fridge", name: "\u5BF9\u5F00\u95E8\u51B0\u7BB1", w: 910, d: 720, h: 1780, color: "#c9ced4", pw: [["socket", 300]] }, { key: "fridgeFrench", type: "fridge", name: "\u6CD5\u5F0F\u591A\u95E8\u51B0\u7BB1", w: 830, d: 700, h: 1900, color: "#b9bec5", pw: [["socket", 300]] }, { key: "lCounter", type: "lCounter", name: "L \u5F62\u6A71\u67DC\uFF08\u53EF\u5B9A\u5236\uFF09", w: 2400, d: 1800, h: 900, color: "#f0ede8", pw: [["hot", 500, -760], ["cold", 500, -610], ["waste", 400, -685], ["socket", 1100, -150], ["socket", 1100, 200], ["socketHood", 2150, 640], ["gas", 600, 880]] }, { key: "uCounter", type: "uCounter", name: "U \u5F62\u6A71\u67DC\uFF08\u53EF\u5B9A\u5236\uFF09", w: 2700, d: 2100, h: 900, color: "#f0ede8", pw: [["socket", 1100, 0]] }, { key: "freezer", type: "freezer", name: "\u51B0\u67DC", w: 1e3, d: 600, h: 850, color: "#eef0f2", pw: [["socket", 300]] }, { key: "trashBin", type: "bin", name: "\u5783\u573E\u6876", w: 300, d: 300, h: 600, color: "#9aa1a8" }] }, { group: "\u536B\u6D74", items: [{ key: "toilet", type: "toilet", name: "\u9A6C\u6876", w: 400, d: 700, h: 780, color: "#fafafa", pw: [["socketW", 400, 350], ["cold", 250, -250]] }, { key: "wallToilet", type: "toilet", name: "\u58C1\u6302\u9A6C\u6876", w: 380, d: 550, h: 400, color: "#fafafa", pw: [["socketW", 400, 350], ["cold", 900, -150]] }, { key: "squatToilet", type: "squat", name: "\u8E72\u4FBF\u5668", w: 450, d: 600, h: 200, color: "#fafafa", pw: [["cold", 900, 0]] }, { key: "vanity", type: "vanity", name: "\u6D74\u5BA4\u67DC\uFF08\u542B\u955C\uFF09", w: 800, d: 500, h: 850, color: "#c29a6b", pw: [["socketW", 1400, 520], ["hot", 500, -100], ["cold", 500, 100], ["waste", 400, 0]] }, { key: "mirrorCabinet", type: "mirrorCabinet", name: "\u955C\u67DC", w: 800, d: 150, h: 700, z: 1150, color: "#e9e5de" }, { key: "doubleVanity", type: "vanity", name: "\u53CC\u76C6\u6D74\u5BA4\u67DC", w: 1400, d: 550, h: 850, color: "#c29a6b", pw: [["socketW", 1400, 800], ["hot", 500, -450], ["cold", 500, -300], ["hot", 500, 300], ["cold", 500, 450], ["waste", 400, -375], ["waste", 400, 375]] }, { key: "pedestalSink", type: "pedestalSink", name: "\u7ACB\u67F1\u76C6", w: 500, d: 450, h: 850, color: "#fafafa", pw: [["hot", 500, -75], ["cold", 500, 75], ["waste", 400, 0]] }, { key: "freeTub", type: "freeTub", name: "\u72EC\u7ACB\u6D74\u7F38", w: 1700, d: 800, h: 620, color: "#fbfbfb", pw: [["cold", 600, 75], ["hot", 600, -75]] }, { key: "bathShelf", type: "shelfRack", name: "\u7F6E\u7269\u67B6", w: 600, d: 250, h: 1600, color: "#c7ccd2" }, { key: "shower", type: "shower", name: "\u6DCB\u6D74\u623F", w: 900, d: 900, h: 2e3, color: "#e9eef2", pw: [["cold", 1100, -225], ["hot", 1100, -375]] }, { key: "showerScreen", type: "showerScreen", name: "\u4E00\u5B57\u6DCB\u6D74\u9694\u65AD", w: 1200, d: 80, h: 2e3, color: "#e9eef2" }, { key: "bathtub", type: "bathtub", name: "\u6D74\u7F38", w: 1600, d: 750, h: 600, color: "#fbfbfb", pw: [["cold", 600, 75], ["hot", 600, -75]] }, { key: "showerSet", type: "showerSet", name: "\u5D4C\u5165\u5F0F\u6052\u6E29\u6DCB\u6D74", w: 900, d: 200, h: 1100, color: "#e4e2dc", pw: [["hot", 1e3, -75], ["cold", 1e3, 75]] }, { key: "towelWarmer", type: "towelWarmer", name: "\u7535\u70ED\u6BDB\u5DFE\u67B6", w: 500, d: 100, h: 800, z: 900, color: "#c7ccd2", pw: [["socketW", 1800]] }, { key: "bathHeater", type: "bathHeater", name: "\u98CE\u6696\u6D74\u9738\uFF08\u5438\u9876\uFF09", w: 300, d: 300, h: 160, color: "#f5f5f4", ceil: true }] }, { group: "\u9633\u53F0 \xB7 \u8863\u5E3D", items: [{ key: "laundrySink", type: "laundrySink", name: "\u6D17\u8863\u6C60\u67DC", w: 700, d: 550, h: 850, color: "#f0ede8", pw: [["hot", 500, -100], ["cold", 500, 100], ["waste", 400, 0], ["socketW", 1300, 420]] }, { key: "clothesRack", type: "clothesRack", name: "\u5347\u964D\u667E\u8863\u67B6\uFF08\u5438\u9876\uFF09", w: 2400, d: 450, h: 500, color: "#c7ccd2", ceil: true }, { key: "lounge", type: "lounge", name: "\u4F11\u95F2\u6905", w: 700, d: 750, h: 800, color: "#b7a58b" }, { key: "sideTable", type: "sideTable", name: "\u8FB9\u51E0", w: 500, d: 500, h: 550, color: "#9c7652" }, { key: "island", type: "island", name: "\u8863\u5E3D\u5C9B\u53F0", w: 1200, d: 600, h: 900, color: "#e3dccf" }] }, { group: "\u697C\u68AF\uFF08\u6574\u680B\u697C\uFF09", items: [{ key: "stairU", type: "stairU", name: "U \u5F62\u4E09\u8DD1\u697C\u68AF", w: 3300, d: 2400, h: 3320, color: "#c9a77d" }, { key: "stairRun", type: "stairRun", name: "\u76F4\u8DD1\u68AF\u6BB5", w: 1100, d: 3e3, h: 1700, color: "#c9a77d" }, { key: "stairLanding", type: "stairRun", name: "\u697C\u68AF\u5E73\u53F0", w: 1100, d: 1100, h: 1700, color: "#c9a77d" }, { key: "elevator", type: "elevator", name: "\u5BB6\u7528\u7535\u68AF\uFF08\u6F2B\u6E38\u65F6\u53EF\u4E58\u5750\uFF09", w: 910, d: 1160, h: 2600, color: "#b8bec6" }, { key: "stairDogleg", type: "stairDogleg", name: "\u53CC\u8DD1\u6247\u5F62\u8F6C\u89D2\u697C\u68AF", w: 2400, d: 3600, h: 3150, color: "#c9a77d", opt: { winders: 7, gap: 120 } }] }, { group: "\u4E95\u9053 \xB7 \u5BA4\u5916\u8BBE\u5907", items: [{ key: "riser", type: "riser", name: "\u7ACB\u7BA1\uFF08\u6392\u6C34 / \u96E8\u6C34 \u03A6110\uFF0C\u901A\u9AD8\uFF09", w: 110, d: 110, h: 2800, color: "#9aa1a8" }, { key: "acOutdoor", type: "acOutdoor", name: "\u7A7A\u8C03\u5BA4\u5916\u673A", w: 850, d: 320, h: 600, color: "#eceef0" }, { key: "louver", type: "louver", name: "\u767E\u53F6\uFF08\u7A7A\u8C03\u4F4D / \u98CE\u4E95\uFF09", w: 1e3, d: 60, h: 1800, z: 300, color: "#c9ced4" }, { key: "meterBox", type: "meterBox", name: "\u7535\u8868\u7BB1 / \u914D\u7EBF\u7BB1\uFF08\u4E95\u9053\uFF09", w: 500, d: 160, h: 700, z: 1e3, color: "#d9dde2" }] }, { group: "\u7EC4\u5408 \xB7 \u6446\u4EF6", items: [{ key: "cornerShelf", type: "cornerShelf", name: "\u659C\u89D2\u5F00\u653E\u5C55\u793A\u683C\uFF08\u4E09\u89D2\u591A\u5C42\uFF09", w: 450, d: 450, h: 1800, color: "#e6e0d6", opt: { shelves: 5, corner: "left" } }, { key: "modularSofa", type: "modularSofa", name: "\u6A21\u5757\u6C99\u53D1\uFF08\u6309\u683C\u6570\uFF0C\u53EF\u5E26\u811A\u8E0F\uFF09", w: 2700, d: 1e3, h: 760, color: "#c8c0b4", opt: { n: 3, ottoman: false } }, { key: "bayDeck", type: "bayDeck", name: "\u5BA4\u5185\u98D8\u7A97\u53F0\uFF08450 \u9AD8\u53F0\u9762\uFF09", w: 1800, d: 550, h: 450, color: "#e9e4dc" }, { key: "plushToy", type: "plushToy", name: "\u6BDB\u7ED2\u73A9\u5076", w: 300, d: 250, h: 380, color: "#d9b48f" }, { key: "tableVase", type: "tableVase", name: "\u82B1\u74F6\uFF08\u684C\u9762\u6446\u4EF6\uFF09", w: 180, d: 180, h: 350, z: 750, color: "#c8d4cf" }, { key: "bookSet", type: "bookSet", name: "\u4E66\u6446\uFF08\u4E00\u6392\u4E66 + \u4E66\u7ACB\uFF09", w: 400, d: 220, h: 260, z: 750, color: "#8a6d55" }] }, { group: "\u522B\u5885 \xB7 \u8F66\u5E93", items: [{ key: "car", type: "car", name: "\u8F7F\u8F66", w: 1850, d: 4800, h: 1450, color: "#5b6b7d" }, { key: "suv", type: "car", name: "SUV", w: 1950, d: 4900, h: 1750, color: "#2f3338" }, { key: "evCharger", type: "evCharger", name: "\u5145\u7535\u6869\uFF08\u58C1\u6302 7kW\uFF09", w: 300, d: 150, h: 450, z: 1100, color: "#f2f3f4", pw: [["socketEV", 1300]] }, { key: "carport", type: "carport", name: "\u8F66\u68DA\uFF08\u5355\u8F66\u4F4D\uFF09", w: 3200, d: 5600, h: 2600, color: "#3b3f46" }, { key: "carport2", type: "carport", name: "\u8F66\u68DA\uFF08\u53CC\u8F66\u4F4D\uFF09", w: 6e3, d: 5600, h: 2600, color: "#3b3f46" }, { key: "garageShelf", type: "garageShelf", name: "\u8F66\u5E93\u50A8\u7269\u67B6", w: 1800, d: 500, h: 2e3, color: "#6b7078" }, { key: "workbench", type: "workbench", name: "\u5DE5\u5177\u53F0 + \u6D1E\u6D1E\u677F", w: 1800, d: 650, h: 1800, color: "#b38b63", pw: [["socket", 1100, -500], ["socket", 1100, 500]] }, { key: "bicycle", type: "bicycle", name: "\u81EA\u884C\u8F66", w: 600, d: 1750, h: 1050, color: "#c8442b" }] }, { group: "\u522B\u5885 \xB7 \u5EAD\u9662", items: [{ key: "pool", type: "pool", name: "\u6CF3\u6C60", w: 3500, d: 8e3, h: 60, color: "#4fb3d9" }, { key: "lawn", type: "lawn", name: "\u8349\u576A", w: 4e3, d: 4e3, h: 15, color: "#7fae5a" }, { key: "stepStones", type: "stepStones", name: "\u6C40\u6B65 / \u77F3\u677F\u8DEF", w: 600, d: 3600, h: 30, color: "#c9c3b8" }, { key: "tree", type: "tree", name: "\u5EAD\u9662\u4E54\u6728", w: 2600, d: 2600, h: 4500, color: "#4f7f45" }, { key: "shrub", type: "shrub", name: "\u704C\u6728\u7403", w: 900, d: 900, h: 800, color: "#5f8f55" }, { key: "gazebo", type: "gazebo", name: "\u51C9\u4EAD", w: 3200, d: 3200, h: 3e3, color: "#8a6a4d" }, { key: "parasol", type: "parasol", name: "\u906E\u9633\u4F1E + \u684C\u6905", w: 2800, d: 2800, h: 2500, color: "#efe8dc" }, { key: "sunLounger", type: "sunLounger", name: "\u6CF3\u6C60\u8EBA\u6905", w: 700, d: 1950, h: 450, color: "#f1ece2" }, { key: "swing", type: "swing", name: "\u5EAD\u9662\u79CB\u5343", w: 2e3, d: 1300, h: 2100, color: "#8a6a4d" }, { key: "bbq", type: "bbq", name: "\u6237\u5916\u70E7\u70E4\u53F0", w: 1600, d: 650, h: 950, color: "#7d848c", pw: [["socketW", 1100, 500], ["cold", 500, -500]] }, { key: "waterFeature", type: "waterFeature", name: "\u53E0\u6C34\u666F\u5899", w: 1600, d: 600, h: 1500, color: "#9a948a", pw: [["socketW", 400]] }, { key: "fence", type: "fence", name: "\u5EAD\u9662\u56F4\u680F", w: 2e3, d: 60, h: 1200, color: "#6b5442" }, { key: "gate", type: "gate", name: "\u5EAD\u9662\u5927\u95E8", w: 3e3, d: 150, h: 1800, color: "#2f3338" }, { key: "lawnLamp", type: "lawnLamp", name: "\u8349\u576A\u706F\uFF08\u53EF\u70B9\u4EAE\uFF09", w: 200, d: 200, h: 650, color: "#2f3338" }] }, { group: "\u522B\u5885 \xB7 \u4F11\u95F2 \xB7 \u8BBE\u5907", items: [{ key: "billiards", type: "billiards", name: "\u53F0\u7403\u684C", w: 1600, d: 2850, h: 800, color: "#2f6b45" }, { key: "mahjong", type: "mahjong", name: "\u81EA\u52A8\u9EBB\u5C06\u684C", w: 950, d: 950, h: 780, color: "#3b3f46", pw: [["socketFloor", 0]] }, { key: "teaTable", type: "teaTable", name: "\u8336\u53F0", w: 1800, d: 800, h: 700, color: "#6b4a32", pw: [["socket", 300, -400], ["cold", 300, 200], ["waste", 300, 400]] }, { key: "theaterSofa", type: "theaterSofa", name: "\u5F71\u9662\u6C99\u53D1\uFF08\u4E09\u8FDE\u5EA7\uFF09", w: 2600, d: 1e3, h: 1e3, color: "#4a3a3a", pw: [["socket", 300, -1450], ["socket", 300, 1450]] }, { key: "grandPiano", type: "grandPiano", name: "\u4E09\u89D2\u94A2\u7434", w: 1550, d: 1900, h: 1e3, color: "#1d1f23", pw: [["socket", 300]] }, { key: "barCounter", type: "barCounter", name: "\u5427\u53F0\uFF08\u5E26\u6C34\u69FD\uFF09", w: 2400, d: 650, h: 1100, color: "#3e3a36", pw: [["socket", 1100, -700], ["cold", 500, 300], ["waste", 400, 450]] }, { key: "sauna", type: "sauna", name: "\u6851\u62FF\u623F", w: 1500, d: 1500, h: 2100, color: "#c9a26b", pw: [["socket16", 2200, 500]] }, { key: "chandelier", type: "chandelier", name: "\u6311\u7A7A\u6C34\u6676\u5927\u540A\u706F", w: 1200, d: 1200, h: 1600, color: "#e9e2d0", ceil: true }, { key: "boiler", type: "boiler", name: "\u58C1\u6302\u7089\uFF08\u5730\u6696 + \u70ED\u6C34\uFF09", w: 450, d: 350, h: 750, z: 1300, color: "#f3f4f5", pw: [["gas", 1200, 0], ["cold", 1200, 130], ["hot", 1200, -130], ["socket", 1400, 320]] }, { key: "manifold", type: "manifold", name: "\u5730\u6696\u5206\u96C6\u6C34\u5668", w: 800, d: 120, h: 450, z: 300, color: "#c9a35a", pw: [["hot", 350, -300], ["cold", 350, 300]] }, { key: "waterSoftener", type: "waterSoftener", name: "\u4E2D\u592E\u8F6F\u6C34\u673A", w: 350, d: 450, h: 1100, color: "#e8eaed", pw: [["cold", 500, -100], ["waste", 300, 100], ["socket", 300, 150]] }] }, { group: "\u529E\u516C \xB7 \u57F9\u8BAD \xB7 \u516C\u5171\u7A7A\u95F4", items: [{ key: "trainingTable", type: "trainingTable", name: "\u57F9\u8BAD\u684C", w: 1200, d: 450, h: 750, color: "#dbc9b0" }, { key: "curveTrainingTable", type: "curveTrainingTable", name: "\u5F27\u5F62\u57F9\u8BAD\u684C", w: 3e3, d: 600, h: 750, color: "#c9ae8b" }, { key: "conferenceTable", type: "diningTable", name: "\u4F1A\u8BAE\u684C", w: 3600, d: 1200, h: 750, color: "#b99772", pw: [["socketFloor", 0], ["net", 300]] }, { key: "trainingChair", type: "chair", name: "\u57F9\u8BAD\u6905", w: 500, d: 500, h: 830, color: "#637b8c" }, { key: "lectern", type: "lectern", name: "\u53EF\u5347\u964D\u8BB2\u53F0", w: 900, d: 650, h: 1100, color: "#b99270", pw: [["socketFloor", 0], ["net", 300]] }, { key: "stage", type: "stage", name: "\u57F9\u8BAD\u5BA4\u5730\u53F0", w: 6e3, d: 2400, h: 300, color: "#b69a7a" }, { key: "slidingBoard", type: "slidingBoard", name: "\u4E0A\u4E0B\u5347\u964D\u9ED1\u677F", w: 4e3, d: 180, h: 2300, color: "#31564c", pw: [["socket", 300]] }, { key: "mobileDisplay", type: "mobileDisplay", name: "\u79FB\u52A8\u4F1A\u8BAE\u5E73\u677F", w: 1700, d: 650, h: 1850, color: "#343d48", pw: [["socketFloor", 0], ["net", 300]] }, { key: "printer", type: "printer", name: "\u529E\u516C\u590D\u5408\u6253\u5370\u673A", w: 650, d: 650, h: 1100, color: "#e2e5e7", pw: [["socket", 300], ["net", 300]] }, { key: "coffeeMachine", type: "coffeeMachine", name: "\u5496\u5561\u673A", w: 450, d: 450, h: 550, z: 850, color: "#3b4148", pw: [["socket", 1100]] }, { key: "urinal", type: "urinal", name: "\u58C1\u6302\u5C0F\u4FBF\u5668", w: 410, d: 360, h: 650, z: 450, color: "#f1f3f2", pw: [["cold", 1e3], ["waste", 400]] }, { key: "serviceSink", type: "serviceSink", name: "\u6E05\u6D01\u62D6\u5E03\u6C60", w: 600, d: 500, h: 600, color: "#e6e9e7", pw: [["cold", 750], ["waste", 150]] }, { key: "wifiAP", type: "wifiAP", name: "\u5438\u9876\u65E0\u7EBF AP", w: 220, d: 220, h: 45, color: "#f7f7f5", ceil: true, pw: [["net", 2700]] }, { key: "ceilingSpeaker", type: "ceilingSpeaker", name: "\u5D4C\u5165\u5F0F\u626C\u58F0\u5668", w: 240, d: 240, h: 70, color: "#e8e9e7", ceil: true }, { key: "supplyVent", type: "airVent", name: "\u7A7A\u8C03\u9001\u98CE\u53E3 A/S", w: 600, d: 300, h: 60, color: "#eef0ed", ceil: true }, { key: "returnVent", type: "airVent", name: "\u7A7A\u8C03\u56DE\u98CE\u53E3 A/R", w: 600, d: 300, h: 60, color: "#dce2e3", ceil: true, opt: { return: true } }] }, { group: "\u5065\u8EAB \xB7 \u5BA0\u7269 \xB7 \u6237\u5916", items: [{ key: "outdoorSet", type: "outdoorSet", name: "\u6237\u5916\u684C\u6905", w: 1600, d: 1600, h: 750, color: "#6b5442" }, { key: "plantShelf", type: "plantShelf", name: "\u82B1\u67B6", w: 1e3, d: 350, h: 1200, color: "#8a7d6e" }, { key: "bike", type: "bike", name: "\u52A8\u611F\u5355\u8F66", w: 550, d: 1100, h: 1200, color: "#2b2e33" }, { key: "yogaMat", type: "yogaMat", name: "\u745C\u4F3D\u57AB", w: 610, d: 1830, h: 6, color: "#8fa58a" }, { key: "catTree", type: "catTree", name: "\u732B\u722C\u67B6", w: 600, d: 600, h: 1600, color: "#d8c7ae" }, { key: "petBed", type: "petBed", name: "\u5BA0\u7269\u7A9D", w: 700, d: 550, h: 250, color: "#c96f4a" }] }, { group: "\u66F4\u591A\u5BB6\u5177", items: [{ key: "fourSofa", type: "sofa", name: "\u56DB\u4EBA\u6C99\u53D1", w: 2800, d: 1e3, h: 820, color: "#9aa3ad", pw: [["socket", 300, -1550], ["socket", 300, 1550]] }, { key: "singleSofa", type: "sofa", name: "\u5355\u4EBA\u4F4D\u6C99\u53D1", w: 1e3, d: 900, h: 820, color: "#a3aeb8" }, { key: "chaiseSofa", type: "lSofa", name: "\u8D35\u5983\u4F4D\u6C99\u53D1\uFF082.6m\uFF09", w: 2600, d: 1600, h: 820, color: "#c8c0b4", pw: [["socket", 300, -1450], ["socket", 300, 1450]] }, { key: "readingChair", type: "armchair", name: "\u9605\u8BFB\u6905", w: 750, d: 800, h: 950, color: "#7d8f73" }, { key: "nestTables", type: "roundTable", name: "\u7EC4\u5408\u5706\u8336\u51E0\uFF08\u5C0F\uFF09", w: 600, d: 600, h: 450, color: "#c9b29a" }, { key: "diningTable4", type: "diningTable", name: "\u56DB\u4EBA\u9910\u684C", w: 1200, d: 800, h: 750, color: "#b98c5f" }, { key: "diningTable6", type: "diningTable", name: "\u516D\u4EBA\u9910\u684C", w: 1800, d: 900, h: 750, color: "#a8805a" }, { key: "roundTable10", type: "roundTable", name: "\u5706\u9910\u684C\uFF0810 \u4EBA\uFF09", w: 1800, d: 1800, h: 760, color: "#8e6a4a" }, { key: "barTable", type: "diningTable", name: "\u5427\u53F0\u684C\uFF08\u9AD8\u684C\uFF09", w: 1400, d: 500, h: 1050, color: "#6f5a48" }, { key: "armDiningChair", type: "chair", name: "\u6276\u624B\u9910\u6905", w: 560, d: 560, h: 820, color: "#7f6a58" }, { key: "kingBed", type: "bed", name: "\u53CC\u4EBA\u5E8A 2.2m\uFF08King\uFF09", w: 2200, d: 2200, h: 1100, color: "#b4a89a" }, { key: "kidsBed", type: "bed", name: "\u513F\u7AE5\u5E8A 1.0m", w: 1e3, d: 1900, h: 900, color: "#9cc0d6" }, { key: "dayBed", type: "chaise", name: "\u7F57\u6C49\u5E8A / \u5367\u69BB", w: 1900, d: 800, h: 750, color: "#7a5a42" }, { key: "wardrobe2", type: "wardrobe", name: "\u4E24\u95E8\u8863\u67DC 1.0m", w: 1e3, d: 600, h: 2200, color: "#ece7df" }, { key: "wardrobe3", type: "wardrobe", name: "\u4E09\u95E8\u8863\u67DC 1.5m", w: 1500, d: 600, h: 2300, color: "#ece7df" }, { key: "toyCabinet", type: "chest", name: "\u513F\u7AE5\u73A9\u5177\u67DC", w: 900, d: 350, h: 800, color: "#f0d9b5" }, { key: "playMat", type: "rug", name: "\u513F\u7AE5\u722C\u884C\u57AB", w: 1800, d: 1500, h: 15, color: "#c8dcc2" }, { key: "standingDesk", type: "desk", name: "\u5347\u964D\u4E66\u684C 1.4m", w: 1400, d: 700, h: 750, color: "#d2b48c", pw: [["socket", 300], ["net", 300]] }, { key: "bookshelfLow", type: "bookshelf", name: "\u77EE\u4E66\u67B6", w: 1200, d: 300, h: 900, color: "#c9ab88" }, { key: "officeDesk", type: "desk", name: "\u529E\u516C\u684C 1.4m", w: 1400, d: 700, h: 750, color: "#d8cfc2", pw: [["socketFloor", 0], ["net", 300]] }, { key: "deskBench2", type: "trainingTable", name: "\u5DE5\u4F4D\uFF08\u4E24\u4EBA\u4F4D\uFF09", w: 2400, d: 700, h: 750, color: "#e3ddd3", pw: [["socketFloor", 0], ["net", 300]] }, { key: "deskBench4", type: "trainingTable", name: "\u5DE5\u4F4D\uFF08\u56DB\u4EBA\u4F4D\u5BF9\u5750\uFF09", w: 2400, d: 1400, h: 750, color: "#e3ddd3", pw: [["socketFloor", 0], ["net", 300]] }, { key: "bossDesk", type: "lDesk", name: "\u5927\u73ED\u53F0", w: 2200, d: 1900, h: 760, color: "#5f4636", pw: [["socket", 300], ["net", 300]] }, { key: "roundMeeting", type: "roundTable", name: "\u5706\u5F62\u6D3D\u8C08\u684C", w: 1e3, d: 1e3, h: 750, color: "#d9d2c5" }, { key: "reception", type: "barCounter", name: "\u524D\u53F0\u63A5\u5F85\u53F0", w: 2400, d: 800, h: 1100, color: "#e8e4dc", pw: [["socketFloor", 0], ["net", 300]] }, { key: "lockers", type: "cabinet", name: "\u50A8\u7269\u67DC / \u66F4\u8863\u67DC", w: 1200, d: 450, h: 1850, color: "#cfd4d9", cab: { kind: "tall", door: "swing", cols: ["door", "door", "door"], plinth: 60 } }, { key: "officeSofa", type: "sofa", name: "\u529E\u516C\u63A5\u5F85\u6C99\u53D1", w: 1800, d: 800, h: 780, color: "#4a5059" }, { key: "whiteboard", type: "slidingBoard", name: "\u79FB\u52A8\u767D\u677F", w: 1800, d: 150, h: 1900, color: "#f4f6f7" }, { key: "pantryCounter", type: "counter", name: "\u8336\u6C34\u95F4\u53F0\u9762\uFF08\u4E00\u5B57\uFF09", w: 2e3, d: 600, h: 850, color: "#f0ede8" }, { key: "shoeBench", type: "entryBench", name: "\u7A7F\u978B\u51F3\uFF08\u957F\uFF09", w: 1200, d: 380, h: 450, color: "#b48a62" }, { key: "wineFridge", type: "fridge", name: "\u7EA2\u9152\u67DC / \u5D4C\u5165\u51B0\u5427", w: 600, d: 600, h: 850, color: "#3a3d42" }, { key: "kitchenTrolley", type: "shelfRack", name: "\u53A8\u623F\u5C0F\u63A8\u8F66", w: 450, d: 350, h: 800, color: "#d9dde1" }, { key: "arcLamp", type: "floorLamp", name: "\u9493\u9C7C\u706F\uFF08\u843D\u5730\uFF09", w: 450, d: 1300, h: 1900, color: "#2b2d31" }] }, { group: "\u4E2D\u592E\u7A7A\u8C03 \xB7 \u65B0\u98CE \xB7 \u6696\u901A", items: [{ key: "ductAC", type: "ductAC", name: "\u98CE\u7BA1\u673A\u5185\u673A\uFF08\u85CF\u540A\u9876\u5185\uFF09", w: 1e3, d: 500, h: 250, color: "#e4e7ea", ceil: true }, { key: "linearVent", type: "linearVent", name: "\u7EBF\u6027\u51FA\u98CE\u53E3\uFF08\u4E0B\u51FA\u98CE\uFF09", w: 1500, d: 150, h: 40, color: "#f3f4f2", ceil: true }, { key: "linearVentSide", type: "linearVent", name: "\u4FA7\u51FA\u98CE\u53E3\uFF08\u8FB9\u540A\u4FA7\u9762\uFF09", w: 1500, d: 60, h: 120, color: "#f3f4f2", ceil: true, opt: { side: true } }, { key: "linearReturn", type: "linearVent", name: "\u56DE\u98CE\u53E3\uFF08\u5E26\u68C0\u4FEE\u53E3\uFF09", w: 1200, d: 300, h: 40, color: "#e8eaeb", ceil: true, opt: { return: true } }, { key: "cassetteAC", type: "cassetteAC", name: "\u5929\u82B1\u673A\uFF08\u56DB\u9762\u51FA\u98CE\uFF09", w: 840, d: 840, h: 250, color: "#f4f5f4", ceil: true }, { key: "vrfOutdoor", type: "vrfOutdoor", name: "\u591A\u8054\u673A\u5BA4\u5916\u673A\uFF08\u53CC\u98CE\u6247\uFF09", w: 940, d: 370, h: 1380, color: "#eceef0" }, { key: "freshAirUnit", type: "freshAirUnit", name: "\u65B0\u98CE\u4E3B\u673A\uFF08\u5168\u70ED\u4EA4\u6362\uFF0C\u540A\u9876\u5185\uFF09", w: 800, d: 600, h: 270, color: "#dfe3e6", ceil: true }, { key: "thermostat", type: "thermostat", name: "\u6E29\u63A7\u9762\u677F", w: 86, d: 15, h: 86, z: 1400, color: "#f7f7f5" }, { key: "heatPump", type: "acOutdoor", name: "\u7A7A\u6C14\u80FD\u70ED\u6CF5\u5916\u673A", w: 1e3, d: 400, h: 760, color: "#e9ecee", pw: [["socket16", 1300]] }, { key: "bufferTank", type: "tank", name: "\u7F13\u51B2\u6C34\u7BB1 / \u50A8\u70ED\u6C34\u7BB1", w: 500, d: 500, h: 1500, color: "#e6e8ea" }, { key: "centralPurifier", type: "waterSoftener", name: "\u4E2D\u592E\u51C0\u6C34\u673A", w: 350, d: 300, h: 1200, color: "#eef0f2", pw: [["cold", 500, -100], ["waste", 300, 100], ["socket", 300, 150]] }, { key: "preFilter", type: "preFilter", name: "\u524D\u7F6E\u8FC7\u6EE4\u5668", w: 180, d: 150, h: 450, z: 400, color: "#cfd8dc" }, { key: "dehumidifier", type: "airPurifier", name: "\u9664\u6E7F\u673A", w: 400, d: 300, h: 650, color: "#f2f3f4", pw: [["socket", 300]] }, { key: "floorHeat", type: "floorHeat", name: "\u5730\u6696\u76D8\u7BA1\uFF08\u94FA\u6EE1\u623F\u95F4\uFF0C\u9009\u4E2D\u540E\u62C9\u5927\uFF09", w: 3e3, d: 3e3, h: 5, color: "#e06b4a", opt: { site: true } }] }, { group: "\u706F\u5177 \xB7 \u540A\u706F \xB7 \u5438\u9876", items: [{ key: "linearPendant", type: "linearPendant", name: "\u7EBF\u6027\u540A\u706F\uFF08\u9910\u5385\uFF0C\u53EF\u70B9\u4EAE\uFF09", w: 1200, d: 80, h: 800, color: "#2b2d31", ceil: true }, { key: "ceilLamp", type: "ceilLamp", name: "\u5438\u9876\u706F\uFF08\u5976\u6CB9\u5706\u5F62\uFF0C\u53EF\u70B9\u4EAE\uFF09", w: 600, d: 600, h: 90, color: "#f6f2ea", ceil: true }, { key: "ceilingFan", type: "ceilingFan", name: "\u98CE\u6247\u706F\uFF08\u53EF\u70B9\u4EAE\uFF09", w: 1320, d: 1320, h: 420, color: "#c9a77d", ceil: true }, { key: "bubblePendant", type: "bubblePendant", name: "\u6CE1\u6CE1\u540A\u706F / \u9B54\u8C46\u706F\uFF08\u53EF\u70B9\u4EAE\uFF09", w: 900, d: 900, h: 900, color: "#c8a15a", ceil: true }, { key: "gardenLamp", type: "gardenLamp", name: "\u5EAD\u9662\u706F\uFF082.8m\uFF0C\u53EF\u70B9\u4EAE\uFF09", w: 380, d: 380, h: 2800, color: "#2f3338" }, { key: "inGround", type: "inGround", name: "\u5730\u57CB\u706F\uFF08\u53EF\u70B9\u4EAE\uFF09", w: 140, d: 140, h: 20, color: "#3a3d42" }, { key: "wallWasher", type: "wallWasher", name: "\u6237\u5916\u58C1\u706F\uFF08\u53EF\u70B9\u4EAE\uFF09", w: 160, d: 140, h: 260, z: 2e3, color: "#2f3338" }] }, { group: "\u53A8\u536B\u7535\u5668 \xB7 \u8865\u5145", items: [{ key: "integratedStove", type: "integratedStove", name: "\u96C6\u6210\u7076\uFF08\u4E0B\u6392\u6CB9\u70DF\uFF09", w: 900, d: 600, h: 850, color: "#2f3338", pw: [["socket16", 300, 300], ["gas", 600, -300]] }, { key: "washerTower", type: "washerTower", name: "\u6D17\u70D8\u5957\u88C5\uFF08\u53E0\u653E\uFF09", w: 600, d: 650, h: 1750, color: "#f1f2f3", pw: [["socketW", 1300, 200], ["socketW", 1300, -200], ["cold", 1200, -150]] }, { key: "builtinFridge", type: "fridge", name: "\u5D4C\u5165\u5F0F\u51B0\u7BB1 0.6m", w: 600, d: 600, h: 1780, color: "#e9e5dd", pw: [["socket", 300]] }, { key: "smartToilet", type: "toilet", name: "\u667A\u80FD\u9A6C\u6876\uFF08\u4E00\u4F53\u673A\uFF09", w: 400, d: 700, h: 500, color: "#fafafa", pw: [["socketW", 400, 350], ["cold", 250, -250]] }, { key: "ledMirror", type: "ledMirror", name: "\u667A\u80FD\u6D74\u955C\uFF08\u80CC\u5149\uFF0C\u53EF\u70B9\u4EAE\uFF09", w: 800, d: 40, h: 1e3, z: 1100, color: "#dfe7ec", pw: [["socketW", 1600, 0]] }, { key: "projector", type: "projector", name: "\u540A\u88C5\u6295\u5F71\u4EEA", w: 400, d: 320, h: 130, color: "#f2f2f0", ceil: true }] }, { group: "\u6237\u5916\u666F\u89C2 \xB7 \u8865\u5145", items: [{ key: "hedge", type: "hedge", name: "\u7EFF\u7BF1\uFF08\u4FEE\u526A\u6210\u5F62\uFF09", w: 2e3, d: 600, h: 900, color: "#4d7a3f" }, { key: "flowerBed", type: "flowerBed", name: "\u7816\u780C\u82B1\u575B", w: 1600, d: 800, h: 450, color: "#b9876a" }, { key: "planterBox", type: "planterBox", name: "\u82B1\u7BB1\uFF08\u6728\u8D28\uFF09", w: 1e3, d: 400, h: 500, color: "#8a6a4d" }, { key: "palm", type: "palm", name: "\u68D5\u6988 / \u6930\u6811", w: 2400, d: 2400, h: 5e3, color: "#4f7f45" }, { key: "bamboo", type: "bamboo", name: "\u7AF9\u5B50\uFF08\u4E00\u4E1B\uFF09", w: 1500, d: 600, h: 4e3, color: "#6f9a4a" }, { key: "rock", type: "rock", name: "\u666F\u89C2\u77F3", w: 1200, d: 800, h: 700, color: "#9b968d" }, { key: "pergola", type: "pergola", name: "\u82B1\u67B6\u5ECA / \u8461\u8404\u67B6", w: 3e3, d: 3e3, h: 2600, color: "#8a6a4d" }, { key: "outdoorSofa", type: "outdoorSofa", name: "\u6237\u5916\u85E4\u7F16\u6C99\u53D1\u7EC4", w: 2600, d: 2e3, h: 750, color: "#b89a6e" }, { key: "hammock", type: "hammock", name: "\u540A\u5E8A\uFF08\u5E26\u652F\u67B6\uFF09", w: 3e3, d: 1e3, h: 1200, color: "#e7d6b5" }, { key: "kidsSlide", type: "kidsSlide", name: "\u513F\u7AE5\u6ED1\u68AF", w: 1e3, d: 2600, h: 1500, color: "#f08c00" }, { key: "dogHouse", type: "dogHouse", name: "\u72D7\u5C4B", w: 800, d: 1e3, h: 900, color: "#b48a62" }, { key: "firePit", type: "firePit", name: "\u6237\u5916\u706B\u76C6", w: 1e3, d: 1e3, h: 400, color: "#5f646b" }, { key: "outdoorSink", type: "serviceSink", name: "\u6237\u5916\u6D17\u624B\u6C60", w: 600, d: 500, h: 850, color: "#c9c3b8", pw: [["cold", 750], ["waste", 150]] }, { key: "landLawn", type: "free", name: "\u8349\u576A\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 4e3, d: 3e3, h: 30, color: "#7fae5a", opt: { shape: "extrude", mat: "grass", land: true, site: true } }, { key: "landGravel", type: "free", name: "\u788E\u77F3 / \u783E\u77F3\u94FA\u5730\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 3e3, d: 1500, h: 30, color: "#bdb6aa", opt: { shape: "extrude", mat: "gravel", land: true, site: true } }, { key: "landPaver", type: "free", name: "\u77F3\u6750\u94FA\u88C5\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 3e3, d: 2e3, h: 40, color: "#cfc8bb", opt: { shape: "extrude", mat: "paver", land: true, site: true } }, { key: "landDeck", type: "free", name: "\u6237\u5916\u6728\u5E73\u53F0\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 3e3, d: 2400, h: 150, color: "#8d6a4f", opt: { shape: "extrude", mat: "deck", land: true, site: true, floor: true } }, { key: "landWater", type: "free", name: "\u6C34\u666F / \u9C7C\u6C60\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 2500, d: 1800, h: 20, color: "#4fa3c7", opt: { shape: "extrude", mat: "water", land: true, site: true, outline: "-1250,0|-1000,-700|-200,-900|900,-650|1250,100|700,800|-400,900|-1150,600" } }, { key: "landBed", type: "free", name: "\u82B1\u5883 / \u79CD\u690D\u6C60\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 2400, d: 1200, h: 120, color: "#6b4f3a", opt: { shape: "extrude", mat: "soil", land: true, site: true } }] }, { group: "\u540A\u9876\u9020\u578B\uFF08\u9876\u9762\u56FE\u5C42\uFF09", items: [{ key: "ceilZone", type: "free", name: "\u5C40\u90E8\u540A\u9876\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 2400, d: 1800, h: 150, color: "#f1efea", ceil: true, opt: { shape: "extrude", mat: "paint", zone: true } }, { key: "ceilZoneCove", type: "free", name: "\u5C40\u90E8\u540A\u9876 + \u706F\u5E26\uFF08\u60AC\u6D6E\uFF09", w: 2400, d: 1800, h: 150, color: "#f1efea", ceil: true, opt: { shape: "extrude", mat: "paint", zone: true, cove: true } }, { key: "ceilZoneRound", type: "free", name: "\u5706\u5F62\u540A\u9876\uFF08\u9910\u5385\uFF09", w: 1800, d: 1800, h: 120, color: "#f1efea", ceil: true, opt: { shape: "cyl", mat: "paint", zone: true, cove: true } }, { key: "ceilBeamWood", type: "free", name: "\u6728\u6881 / \u88C5\u9970\u5047\u6881", w: 3600, d: 150, h: 180, color: "#8a6a4d", ceil: true, opt: { shape: "box", mat: "wood", zone: true } }, { key: "ceilSlats", type: "free", name: "\u6728\u683C\u6805\u540A\u9876\u7247", w: 2400, d: 1200, h: 60, color: "#b48a62", ceil: true, opt: { shape: "slats", mat: "wood", zone: true, n: 20, sw: 40, rail: false } }] }, { group: "\u81EA\u7531\u6A21\u578B \xB7 \u9020\u578B", items: [{ key: "freeBox", type: "free", name: "\u7ACB\u65B9\u4F53", w: 1e3, d: 1e3, h: 1e3, color: "#eeeae3", opt: { shape: "box", mat: "paint" } }, { key: "freeRoundBox", type: "free", name: "\u5706\u89D2\u65B9\u5757", w: 1e3, d: 600, h: 450, color: "#e7dccb", opt: { shape: "roundBox", mat: "fabric", r: 80 } }, { key: "freePlatform", type: "free", name: "\u5730\u53F0 / \u69BB\u69BB\u7C73\u53F0", w: 2400, d: 1800, h: 300, color: "#c9a77d", opt: { shape: "box", mat: "wood", floor: true } }, { key: "freeWallBlock", type: "free", name: "\u80CC\u666F\u5899\u51F8\u5757", w: 2400, d: 150, h: 2600, color: "#e9e3da", opt: { shape: "box", mat: "stone" } }, { key: "freeCeilBlock", type: "free", name: "\u540A\u9876\u9020\u578B\u5757", w: 2e3, d: 2e3, h: 150, color: "#f4f3ef", z: 2650, opt: { shape: "box", mat: "paint" } }, { key: "freeCyl", type: "free", name: "\u5706\u67F1", w: 400, d: 400, h: 2700, color: "#eeeae3", opt: { shape: "cyl", mat: "paint" } }, { key: "freeRoundStage", type: "free", name: "\u5706\u5F62\u5730\u53F0", w: 2e3, d: 2e3, h: 200, color: "#c9a77d", opt: { shape: "cyl", mat: "wood", floor: true } }, { key: "freeHalfCyl", type: "free", name: "\u534A\u5706\u67F1 / \u534A\u5706\u5899\u579B", w: 800, d: 400, h: 2700, color: "#eeeae3", opt: { shape: "halfCyl", mat: "paint" } }, { key: "freeTube", type: "free", name: "\u5706\u7BA1 / \u5706\u73AF\u9694\u65AD", w: 1800, d: 1800, h: 2400, color: "#e7e2da", opt: { shape: "tube", mat: "paint", t: 100 } }, { key: "freeSphere", type: "free", name: "\u7403\u4F53", w: 500, d: 500, h: 500, color: "#d9c7b0", opt: { shape: "sphere", mat: "paint" } }, { key: "freeHemi", type: "free", name: "\u534A\u7403 / \u7A79\u9876", w: 1200, d: 1200, h: 600, color: "#f1eee8", opt: { shape: "hemi", mat: "paint" } }, { key: "freeCone", type: "free", name: "\u5706\u9525", w: 500, d: 500, h: 800, color: "#d9c7b0", opt: { shape: "cone", mat: "paint" } }, { key: "freePyramid", type: "free", name: "\u56DB\u68F1\u9525", w: 800, d: 800, h: 800, color: "#d9c7b0", opt: { shape: "pyramid", mat: "paint" } }, { key: "freeWedge", type: "free", name: "\u6954\u5F62 / \u5761\u9053", w: 1200, d: 1500, h: 200, color: "#b9b4ac", opt: { shape: "wedge", mat: "concrete" } }, { key: "freeArch", type: "free", name: "\u62F1\u95E8\u9020\u578B", w: 1400, d: 240, h: 2600, color: "#efe9e0", opt: { shape: "arch", mat: "paint", t: 200 } }, { key: "freeArcWall", type: "free", name: "\u5F27\u5F62\u5899 / \u5F27\u5F62\u9694\u65AD", w: 2400, d: 600, h: 2700, color: "#ece7df", opt: { shape: "arcWall", mat: "paint", t: 120, arc: 90 } }, { key: "freeSlats", type: "free", name: "\u6728\u683C\u6805", w: 1800, d: 60, h: 2700, color: "#b48a62", opt: { shape: "slats", mat: "wood", n: 15, sw: 40 } }, { key: "freeGlassScreen", type: "free", name: "\u957F\u8679\u73BB\u7483\u9694\u65AD", w: 1500, d: 60, h: 2400, color: "#dfe9ee", opt: { shape: "box", mat: "frosted" } }, { key: "freeSteps", type: "free", name: "\u53F0\u9636", w: 1200, d: 900, h: 450, color: "#c9c4bc", opt: { shape: "steps", mat: "stone", n: 3, floor: true } }, { key: "freeTorus", type: "free", name: "\u5706\u73AF / \u73AF\u5F62\u706F", w: 1200, d: 1200, h: 60, color: "#fff3d6", z: 2400, opt: { shape: "torus", mat: "light", t: 30 } }, { key: "freeLightBox", type: "free", name: "\u53D1\u5149\u706F\u5E26 / \u706F\u7BB1", w: 2e3, d: 40, h: 30, color: "#fff3d6", z: 2600, opt: { shape: "box", mat: "light" } }, { key: "freeMirror", type: "free", name: "\u955C\u9762\u677F", w: 900, d: 20, h: 1800, color: "#d9dee3", z: 300, opt: { shape: "box", mat: "mirror" } }, { key: "freeVase", type: "free", name: "\u65CB\u8F6C\u4F53 \xB7 \u82B1\u74F6", w: 350, d: 350, h: 600, color: "#c9b8a6", opt: { shape: "lathe", mat: "stone", preset: "vase" } }, { key: "freeColumn", type: "free", name: "\u65CB\u8F6C\u4F53 \xB7 \u7F57\u9A6C\u67F1", w: 450, d: 450, h: 2700, color: "#eeeae3", opt: { shape: "lathe", mat: "stone", preset: "column" } }, { key: "freeExtrude", type: "free", name: "\u62C9\u4F38\u4F53\uFF08\u753B\u8F6E\u5ED3\uFF09", w: 1500, d: 1e3, h: 300, color: "#eeeae3", opt: { shape: "extrude", mat: "paint" } }] }];
const ki = { door: { name: "\u5355\u5F00\u95E8", width: 800, sill: 0, head: 2100 }, double: { name: "\u53CC\u5F00\u95E8", width: 1400, sill: 0, head: 2100 }, unequal: { name: "\u5B50\u6BCD\u95E8", width: 1200, sill: 0, head: 2100 }, sliding: { name: "\u63A8\u62C9\u95E8", width: 1800, sill: 0, head: 2400 }, folding: { name: "\u6298\u53E0\u95E8", width: 1600, sill: 0, head: 2400 }, pocket: { name: "\u9690\u5F62\u63A8\u62C9\u95E8", width: 850, sill: 0, head: 2100 }, hole: { name: "\u95E8\u6D1E / \u57AD\u53E3", width: 900, sill: 0, head: 2100 }, window: { name: "\u5E73\u5F00\u7A97", width: 1500, sill: 900, head: 2400 }, slideWindow: { name: "\u63A8\u62C9\u7A97", width: 1500, sill: 900, head: 2400 }, floorWindow: { name: "\u843D\u5730\u7A97", width: 2400, sill: 0, head: 2500 }, highWindow: { name: "\u9AD8\u7A97", width: 900, sill: 1500, head: 2100 }, bay: { name: "\u98D8\u7A97", width: 1800, sill: 450, head: 2400 }, garage: { name: "\u8F66\u5E93\u95E8\uFF08\u7535\u52A8\u5377\u5E18\uFF09", width: 3e3, sill: 0, head: 2400 }, glassWall: { name: "\u73BB\u7483\u9694\u65AD\uFF08\u5BA4\u5185\u56FA\u5B9A\u73BB\u7483\uFF09", width: 2400, sill: 0, head: 2600 } };
const Lf = 2 / 3;
const cu = (t) => t.status !== "removed";
function Ce(t, e, n = 0) {
  return { x: t.a.x + t.u.x * e + t.n.x * n, y: t.a.y + t.u.y * e + t.n.y * n };
}
;
function V1(t) {
  const e = new Map(t.nodes.map((w) => [w.id, w])), n = /* @__PURE__ */ new Map(), i = [], s = /* @__PURE__ */ new Map();
  for (const w of t.openings) {
    const M = s.get(w.wall) || [];
    M.push(w), s.set(w.wall, M);
  }
  const o = /* @__PURE__ */ new Map(), a = /* @__PURE__ */ new Map(), r = /* @__PURE__ */ new Map();
  for (const w of t.walls) {
    const M = e.get(w.a), S = e.get(w.b);
    if (!M || !S) continue;
    const A = Math.hypot(S.x - M.x, S.y - M.y);
    if (A < 1) continue;
    const T = { x: (S.x - M.x) / A, y: (S.y - M.y) / A };
    r.set(w, { u: T, n: { x: -T.y, y: T.x } });
  }
  for (const w of t.walls) {
    if (!cu(w)) continue;
    for (const T of [w.a, w.b]) {
      const _ = o.get(T) || [];
      _.push(w.t / 2), o.set(T, _);
    }
    const M = r.get(w);
    if (!M) continue;
    const { u: S, n: A } = M;
    for (const [T, _] of [[w.a, S], [w.b, { x: -S.x, y: -S.y }]]) {
      const R = a.get(T) || [];
      R.push({ w, d: _, ht: w.t / 2, n: A, off: 0 }), a.set(T, R);
    }
  }
  const l = /* @__PURE__ */ new Map();
  for (const [w, M] of r) {
    if (!cu(w)) continue;
    const S = [];
    for (const [A, T] of [[w.a, M.u], [w.b, { x: -M.u.x, y: -M.u.y }]]) for (const _ of a.get(A) || []) _.w !== w && T.x * _.d.x + T.y * _.d.y < -0.999 && S.push(_);
    S.length && l.set(w, S);
  }
  const c = /* @__PURE__ */ new Map(), f = (w) => c.get(w) || 0;
  for (let w = 0; w < 12; w++) {
    let M = false;
    for (const [S, A] of l) {
      const T = r.get(S), _ = (D) => D.n.x * T.n.x + D.n.y * T.n.y >= 0 ? 1 : -1, R = A.filter((D) => D.w.t > S.t).sort((D, E) => E.w.t - D.w.t)[0];
      let P = 0;
      if (S.align && R) {
        const D = _(R) * f(R.w), E = S.t / 2;
        P = S.align > 0 ? D + R.ht - E : D - R.ht + E;
      } else for (const D of A) if (D.w.t === S.t && f(D.w)) {
        P = _(D) * f(D.w);
        break;
      }
      Math.abs(P - f(S)) > 0.01 && (c.set(S, P), M = true);
    }
    if (!M) break;
  }
  for (const w of a.values()) for (const M of w) M.off = f(M.w);
  const u = (w, M, S) => {
    const A = w.x * M.n.x + w.y * M.n.y >= 0 ? 1 : -1;
    return { far: Math.max(0, (M.ht - M.off * A) / S), near: Math.max(0, (M.ht + M.off * A) / S) };
  }, h = (w, M, S, A) => {
    let T = 0, _ = 0;
    for (const R of a.get(M) || []) {
      if (R.w === w) continue;
      _++;
      const P = S.x * R.d.x + S.y * R.d.y, D = Math.sqrt(Math.max(0, 1 - P * P));
      D < 0.05 || (T = Math.max(T, Math.min(u(S, R, D).far, A * 4 + R.ht)));
    }
    return { e: T, free: _ === 0 };
  }, d = (w) => {
    const M = e.get(w.a), S = e.get(w.b);
    return w.t * 1e7 + (M && S ? Math.hypot(S.x - M.x, S.y - M.y) : 0) + (w.id < "m" ? 0.1 : 0);
  }, p = (w, M, S, A) => {
    const T = a.get(M) || [];
    if (T.length < 2) return 0;
    const _ = (N) => N.reduce((U, $) => d($.w) > d(U.w) ? $ : U), R = (N) => T.filter((U) => U === N || U.d.x * N.d.x + U.d.y * N.d.y < -0.999);
    let P = _(T), D = R(P);
    if (D.length > 1 && D.some((N) => Math.abs(N.ht - P.ht) > 0.5 || N.off || P.off)) {
      const N = T.filter((U) => !D.includes(U));
      N.length && (P = _(N), D = R(P));
    }
    const E = (N) => {
      const U = S.x * N.d.x + S.y * N.d.y;
      return Math.sqrt(Math.max(0, 1 - U * U));
    };
    if (D.some((N) => N.w === w)) {
      if (D.length > 1) return 0.6;
      let N = 0;
      for (const U of T) {
        if (U.w === w) continue;
        const $ = E(U);
        $ >= 0.05 && (N = Math.max(N, Math.min(u(S, U, $).far, A * 4 + U.ht)));
      }
      return N;
    }
    let I = 0;
    for (const N of D) {
      const U = E(N);
      U >= 0.05 && (I = Math.max(I, Math.min(u(S, N, U).near, A * 4 + N.ht)));
    }
    return I ? -I + 0.5 : 0;
  };
  for (const w of t.walls) {
    const M = e.get(w.a), S = e.get(w.b);
    if (!M || !S) continue;
    const A = S.x - M.x, T = S.y - M.y, _ = Math.hypot(A, T);
    if (_ < 1) continue;
    const R = { x: A / _, y: T / _ }, P = { x: -R.y, y: R.x }, D = w.t / 2, E = (s.get(w.id) || []).map((L) => ({ o: L, s0: L.pos - L.width / 2, s1: L.pos + L.width / 2 })).sort((L, j) => L.s0 - j.s0), I = cu(w), N = I ? h(w, w.a, R, D) : { e: D, free: false }, U = I ? h(w, w.b, { x: -R.x, y: -R.y }, D) : { e: D, free: false }, $ = [];
    let H = -N.e;
    for (const L of E) L.s0 > H + 1 && $.push({ s0: H, s1: L.s0 }), H = Math.max(H, L.s1);
    _ + U.e > H + 1 && $.push({ s0: H, s1: _ + U.e });
    const F = (L) => {
      const j = [...o.get(L) || []];
      if (cu(w)) {
        const X = j.indexOf(D);
        X >= 0 && j.splice(X, 1);
      }
      return j.length ? Math.max(...j) : 0;
    }, G = f(w), Y = G ? { x: M.x + P.x * G, y: M.y + P.y * G } : M, V = G ? { x: S.x + P.x * G, y: S.y + P.y * G } : S, Q = { w, a: Y, b: V, off: G, len: _, u: R, n: P, ht: D, ops: E, solids: $, endA: F(w.a), endB: F(w.b), extA: N.e, extB: U.e, freeA: N.free, freeB: U.free, e3A: I ? p(w, w.a, R, D) : D, e3B: I ? p(w, w.b, { x: -R.x, y: -R.y }, D) : D };
    n.set(w.id, Q), i.push(Q);
  }
  const g = i.filter((w) => cu(w.w)), m = jT(g);
  let y = 1 / 0, b = 1 / 0, x = -1 / 0, v = -1 / 0;
  for (const w of g) for (const [M, S] of [[Ce(w, -w.extA), 0], [Ce(w, w.len + w.extB), 0]]) {
    const A = Math.abs(w.n.x) * w.ht + S, T = Math.abs(w.n.y) * w.ht + S;
    y = Math.min(y, M.x - A), b = Math.min(b, M.y - T), x = Math.max(x, M.x + A), v = Math.max(v, M.y + T);
  }
  return isFinite(y) || (y = 0, b = 0, x = 1e4, v = 8e3), { nodes: e, walls: n, all: i, active: g, bounds: { x: y, y: b, w: x - y, h: v - b, x1: x, y1: v }, miters: m };
}
;
function jT(t) {
  const e = /* @__PURE__ */ new Map();
  for (const o of t) for (const a of ["a", "b"]) {
    const r = a === "a" ? o.w.a : o.w.b, l = e.get(r) || [];
    l.push({ g: o, end: a }), e.set(r, l);
  }
  const n = [], i = (o, a) => o.x * a.y - o.y * a.x, s = (o, a, r, l) => {
    const c = i(a, l);
    return Math.abs(c) < 1e-9 ? null : i({ x: r.x - o.x, y: r.y - o.y }, l) / c;
  };
  for (const o of e.values()) {
    if (o.length !== 2) continue;
    const [a, r] = o.map(({ g: T, end: _ }) => {
      const R = _ === "a" ? T.a : Ce(T, T.len), P = _ === "a" ? T.u : { x: -T.u.x, y: -T.u.y };
      return { g: T, end: _, base: R, d: P };
    }), l = a.d.x * r.d.x + a.d.y * r.d.y;
    if (Math.abs(l) < 0.035 || Math.abs(l) > 0.995) continue;
    const c = (T, _) => {
      const R = T.g.n.x * _.d.x + T.g.n.y * _.d.y > 0 ? 1 : -1;
      return { inn: { x: T.base.x + T.g.n.x * T.g.ht * R, y: T.base.y + T.g.n.y * T.g.ht * R }, out: { x: T.base.x - T.g.n.x * T.g.ht * R, y: T.base.y - T.g.n.y * T.g.ht * R } };
    }, f = c(a, r), u = c(r, a), h = s(f.inn, a.d, u.inn, r.d), d = s(u.inn, r.d, f.inn, a.d), p = s(f.out, a.d, u.out, r.d), g = s(u.out, r.d, f.out, a.d);
    if (h === null || d === null || p === null || g === null) continue;
    const m = Math.max(h, p), y = Math.max(d, g), b = (T, _) => _ > -T.g.ht * 6 && _ < T.g.len * 0.45;
    if (!b(a, m) || !b(r, y)) continue;
    const x = { x: f.inn.x + a.d.x * h, y: f.inn.y + a.d.y * h }, v = { x: f.out.x + a.d.x * p, y: f.out.y + a.d.y * p }, w = { x: f.out.x + a.d.x * m, y: f.out.y + a.d.y * m }, M = { x: u.out.x + r.d.x * y, y: u.out.y + r.d.y * y }, S = { x: f.inn.x + a.d.x * m, y: f.inn.y + a.d.y * m }, A = { x: u.inn.x + r.d.x * y, y: u.inn.y + r.d.y * y };
    for (const [T, _] of [[a, m], [r, y]]) T.end === "a" ? T.g.mA = _ : T.g.mB = T.g.len - _;
    n.push({ poly: [S, w, v, M, A, x], edges: [[w, v], [v, M], [S, x], [x, A]], gs: [a.g, r.g] });
  }
  return n;
}
;
function km(t) {
  var a;
  const e = String(((a = t.opt) == null ? void 0 : a.outline) || "").split("|").map((r) => r.split(",").map(Number));
  if (e.length < 4 || e.length % 2 || !e.every((r) => r.length === 2 && r.every(Number.isFinite))) return [];
  const n = e.map((r) => r[0]), i = e.map((r) => r[1]), s = Math.max(...n) - Math.min(...n), o = Math.max(...i) - Math.min(...i);
  return s <= 0 || o <= 0 ? [] : e.map(([r, l]) => [r * t.w / s, l * t.d / o]);
}
;
const Ml = (t, e, n, i) => ({ x0: Math.min(t, n), y0: Math.min(e, i), x1: Math.max(t, n), y1: Math.max(e, i) });
const XT = ["counter", "lCounter", "uCounter"];
const is = (t) => XT.includes(t.type);
function bo(t) {
  var a, r, l, c, f, u, h, d, p, g, m, y, b, x, v, w, M, S, A;
  const e = ((a = t.kit) == null ? void 0 : a.shape) ?? (t.type === "uCounter" ? "U" : t.type === "lCounter" ? "L" : "I"), n = R6(((r = t.kit) == null ? void 0 : r.depth) ?? (e === "I" ? Math.min(t.d, 650) : 600), 350, 900), i = { shape: e, corner: ((l = t.kit) == null ? void 0 : l.corner) ?? "left", depth: n, sink: { leg: 0, at: 0, w: e === "I" && t.w < 2600 ? 600 : 800, bowls: 1, ...((c = t.kit) == null ? void 0 : c.sink) || {}, ...((f = t.kit) == null ? void 0 : f.sink) === false ? { off: true } : {} }, hob: { leg: 0, at: 0, w: 750, burners: 2, ...((u = t.kit) == null ? void 0 : u.hob) || {}, ...((h = t.kit) == null ? void 0 : h.hob) === false ? { off: true } : {} }, wallLegs: (d = t.kit) == null ? void 0 : d.wallLegs, wall: ((p = t.kit) == null ? void 0 : p.wall) ?? true, wallH: ((g = t.kit) == null ? void 0 : g.wallH) ?? 700, wallD: ((m = t.kit) == null ? void 0 : m.wallD) ?? 350, wallZ: ((y = t.kit) == null ? void 0 : y.wallZ) ?? 1550, hood: ((b = t.kit) == null ? void 0 : b.hood) ?? true, top: ((x = t.kit) == null ? void 0 : x.top) ?? "#eceae6", thick: ((v = t.kit) == null ? void 0 : v.thick) ?? 40, tall: ((w = t.kit) == null ? void 0 : w.tall) ?? "none", tallW: ((M = t.kit) == null ? void 0 : M.tallW) ?? 600, tallH: ((S = t.kit) == null ? void 0 : S.tallH) ?? 2200 }, s = Wi(t, i), o = (T, _) => {
    s[T.leg] || (T.leg = 0);
    const R = s[T.leg], P = R.usable[0] + T.w / 2, D = R.usable[1] - T.w / 2;
    (!t.kit || !t.kit[T === i.sink ? "sink" : "hob"]) && (T.at = e === "I" ? T === i.sink ? R.usable[0] + 100 + T.w / 2 : R.usable[1] - 150 - T.w / 2 : R.usable[0] + (R.usable[1] - R.usable[0]) * _), T.at = D < P ? (R.usable[0] + R.usable[1]) / 2 : R6(T.at, P, D);
  };
  return !((A = t.kit) != null && A.sink) && e !== "I" && (i.sink.leg = 1), i.hob.off && (i.hood = false), o(i.sink, e === "I" ? 0.22 : 0.5), o(i.hob, e === "I" ? 0.75 : 0.62), i;
}
;
function Wi(t, e) {
  const n = t.w / 2, i = t.d / 2, s = Math.min(e.depth, t.d, t.w / 2), o = [], a = e.shape === "U" ? ["left", "right"] : e.shape === "L" ? [e.corner || "left"] : [], r = { dir: "x", s0: 0, s1: t.w, back: -i, front: 1, depth: s, rect: Ml(-n, -i, n, -i + s), usable: [0, t.w], name: "\u4E3B\u6BB5\uFF08\u9760\u80CC\u5899\uFF09" };
  a.includes("left") && (r.usable[0] = s + 50), a.includes("right") && (r.usable[1] = t.w - s - 50), o.push(r);
  for (const c of a) {
    const f = c === "left" ? -n : n - s, u = c === "right" && e.shape === "U" && e.d2 ? Math.max(s + 300, Math.min(t.d, e.d2)) : t.d;
    o.push({ dir: "y", s0: s, s1: u, back: c === "left" ? -n : n, front: c === "left" ? 1 : -1, depth: s, rect: Ml(f, -i + s, f + s, -i + u), usable: [s + 50, u], name: c === "left" ? "\u5DE6\u4FA7\u6BB5" : "\u53F3\u4FA7\u6BB5" });
  }
  const l = tx(o, e);
  if (e.tall && e.tall !== "none") {
    const c = l[e.tall === "start" ? 0 : 1], f = o[c.leg], u = e.tallW || 600;
    c.atStart ? f.usable[0] = Math.max(f.usable[0], f.s0 + u + 50) : f.usable[1] = Math.min(f.usable[1], f.s1 - u - 50);
  }
  return o;
}
;
function tx(t, e) {
  return e.shape === "I" ? [{ leg: 0, atStart: true }, { leg: 0, atStart: false }] : e.shape === "L" ? e.corner === "right" ? [{ leg: 0, atStart: true }, { leg: 1, atStart: false }] : [{ leg: 1, atStart: false }, { leg: 0, atStart: false }] : [{ leg: 1, atStart: false }, { leg: 2, atStart: false }];
}
;
function of(t, e, n, i) {
  const s = t.w / 2, o = t.d / 2;
  return e.dir === "x" ? { x: -s + n, y: e.back + i } : { x: e.back + e.front * i, y: -o + n };
}
;
function Xt(t, e, n, i, s, o) {
  const a = of(t, e, n, s), r = of(t, e, i, o);
  return Ml(a.x, a.y, r.x, r.y);
}
;
function Pm(t, e) {
  if (!e.tall || e.tall === "none") return null;
  const n = Wi(t, e), i = tx(n, e)[e.tall === "start" ? 0 : 1], s = n[i.leg], o = e.tallW || 600;
  return i.atStart ? Xt(t, s, s.s0, s.s0 + o, 0, s.depth) : Xt(t, s, s.s1 - o, s.s1, 0, s.depth);
}
;
function nx(t, e) {
  const n = t.w / 2, i = t.d / 2, s = Math.min(e.depth, t.d, t.w / 2);
  if (e.shape === "I") return [{ x: -n, y: -i }, { x: n, y: -i }, { x: n, y: -i + s }, { x: -n, y: -i + s }];
  if (e.shape === "L" && e.corner !== "right") return [{ x: -n, y: -i }, { x: n, y: -i }, { x: n, y: -i + s }, { x: -n + s, y: -i + s }, { x: -n + s, y: i }, { x: -n, y: i }];
  if (e.shape === "L") return [{ x: -n, y: -i }, { x: n, y: -i }, { x: n, y: i }, { x: n - s, y: i }, { x: n - s, y: -i + s }, { x: -n, y: -i + s }];
  const o = e.d2 ? -i + Math.max(s + 300, Math.min(t.d, e.d2)) : i;
  return [{ x: -n, y: -i }, { x: n, y: -i }, { x: n, y: o }, { x: n - s, y: o }, { x: n - s, y: -i + s }, { x: -n + s, y: -i + s }, { x: -n + s, y: i }, { x: -n, y: i }];
}
;
function gh(t, e, n) {
  const i = t.length;
  if (!e || e.length !== i || e.some((o) => !(o > 0))) return t.map(() => n / i);
  const s = e.reduce((o, a) => o + a, 0);
  return e.map((o) => o * n / s);
}
;
function Dl(t) {
  var r;
  const e = t.cab, n = t.w / 2, i = t.d / 2;
  if (e.shape !== "L") return [{ run: { dir: "x", s0: 0, s1: t.w, back: -i, front: 1, depth: t.d, rect: Ml(-n, -i, n, i) }, cols: e.cols, ws: e.ws }];
  const s = Math.min(e.depth || 600, t.d - 200, t.w - 200), o = e.corner !== "right", a = o ? -n : n - s;
  return [{ run: { dir: "x", s0: 0, s1: t.w, back: -i, front: 1, depth: s, rect: Ml(-n, -i, n, -i + s) }, cols: e.cols, ws: e.ws, corner: o ? "start" : "end" }, { run: { dir: "y", s0: s, s1: t.d, back: o ? -n : n, front: o ? 1 : -1, depth: s, rect: Ml(a, -i + s, a + s, i) }, cols: (r = e.cols2) != null && r.length ? e.cols2 : ["door", "door"], ws: void 0 }];
}
;
function JT(t) {
  const e = t.cab;
  return e.shape !== "L" ? null : nx(t, { shape: "L", corner: e.corner, depth: Math.min(e.depth || 600, t.d - 200, t.w - 200) });
}
;
const p0 = (t, e, n) => {
  var i;
  return ((i = t.opt) == null ? void 0 : i[e]) ?? n;
};
function R6(t, e, n) {
  return Math.max(e, Math.min(n, t));
}
;
function qL(t, e, n) {
  var p;
  const i = e.w, s = e.d, o = i / 2, a = s / 2, r = e.color, l = Math.min(i, s), c = (g, m, y, b, x, v) => {
    t.beginPath(), fs(t, g, m, y, b, x), v && (t.fillStyle = v, t.fill()), t.stroke();
  }, f = (g, m, y, b) => {
    t.beginPath(), t.moveTo(g, m), t.lineTo(y, b), t.stroke();
  }, u = (g, m, y, b) => {
    t.beginPath(), t.arc(g, m, Math.max(1, y), 0, Math.PI * 2), b && (t.fillStyle = b, t.fill()), t.stroke();
  }, h = () => {
    f(-o, -a, o, a), f(o, -a, -o, a);
  }, d = (g) => t.setLineDash(g ? [n * 6, n * 4] : []);
  switch (e.type) {
    case "ductAC":
      return d(true), c(-o, -a, i, s, 0, "rgba(228,231,234,.6)"), d(false), f(-o, 0, o * 0.4, 0), c(o * 0.4, -a * 0.9, i * 0.3, s * 0.9 * 2, 0, null), h(), true;
    case "linearVent":
      if (c(-o, -a, i, s, 0, r), (p = e.opt) != null && p.return) for (let g = -o + 30; g < o; g += 30) f(g, -a + 15, g, a - 15);
      else f(-o + 20, -a / 3, o - 20, -a / 3), f(-o + 20, a / 3, o - 20, a / 3);
      return true;
    case "cassetteAC":
      c(-o, -a, i, s, 20, r), c(-i * 0.25, -s * 0.25, i * 0.5, s * 0.5, 4, "#e9ebec");
      for (const g of [-1, 1]) f(-i * 0.3, g * s * 0.36, i * 0.3, g * s * 0.36), f(g * i * 0.36, -s * 0.3, g * i * 0.36, s * 0.3);
      return true;
    case "vrfOutdoor":
      return c(-o, -a, i, s, 10, r), u(-i * 0.22, 0, Math.min(i * 0.2, s * 0.42)), u(i * 0.22, 0, Math.min(i * 0.2, s * 0.42)), true;
    case "freshAirUnit":
      d(true), c(-o, -a, i, s, 0, "rgba(223,227,230,.6)"), d(false);
      for (const [g, m] of [[-i * 0.3, -a], [i * 0.3, -a], [-i * 0.3, a], [i * 0.3, a]]) u(g, m, 60);
      return t.font = `600 ${l * 0.22}px system-ui`, t.fillStyle = "#495057", t.textAlign = "center", t.textBaseline = "middle", t.fillText("\u65B0\u98CE", 0, 0), true;
    case "thermostat":
      return c(-o, -a, i, s, 4, r), true;
    case "tank":
      return u(0, 0, l / 2, r), u(0, 0, l * 0.3), true;
    case "preFilter":
      return u(0, 0, l / 2, "#cfe3ea"), f(-o, 0, o, 0), true;
    case "floorHeat": {
      t.save(), t.strokeStyle = "rgba(224,107,74,.55)", t.lineWidth = n * 1.2;
      for (let g = o - 100, m = a - 100; g > 100 && m > 100; g -= 200, m -= 200) t.strokeRect(-g, -m, g * 2, m * 2);
      return t.restore(), true;
    }
    case "linearPendant":
      return c(-o, -a, i, s, s / 2, "#fff3bf"), f(-o * 0.8, 0, -o * 0.8 + 1, 0), u(-o * 0.8, 0, 20), u(o * 0.8, 0, 20), true;
    case "ceilLamp":
      return u(0, 0, l / 2, "#fff8e6"), u(0, 0, l * 0.35), true;
    case "ceilingFan": {
      u(0, 0, l * 0.12, r);
      for (let g = 0; g < 5; g++) {
        const m = g * Math.PI * 2 / 5;
        t.save(), t.rotate(m), c(l * 0.1, -70, l * 0.38, 140, 60, "rgba(138,106,77,.5)"), t.restore();
      }
      return true;
    }
    case "bubblePendant": {
      u(0, 0, l * 0.12, r);
      for (let g = 0; g < 10; g++) {
        const m = g * 0.628, y = l * 0.38;
        f(0, 0, Math.cos(m) * y, Math.sin(m) * y), u(Math.cos(m) * y, Math.sin(m) * y, l * 0.05, "#fff3bf");
      }
      return true;
    }
    case "gardenLamp":
    case "inGround":
      return u(0, 0, l / 2, "#3a3d42"), u(0, 0, l * 0.3, "#ffe8a3"), true;
    case "wallWasher":
      return c(-o, -a, i, s, 10, "#3a3d42"), u(0, a * 0.2, l * 0.28, "#ffe8a3"), true;
    case "integratedStove":
      return c(-o, -a, i, s, 10, "#2f3338"), t.strokeStyle = "#9aa1a8", u(-i * 0.25, s * 0.1, l * 0.17), u(i * 0.25, s * 0.1, l * 0.17), c(-i * 0.15, -a + 40, i * 0.3, s * 0.25, 4, null), true;
    case "washerTower":
      return c(-o, -a, i, s, 20, r), u(0, s * 0.05, l * 0.3), u(0, s * 0.05, l * 0.18), f(-o, -a + 60, o, -a + 60), true;
    case "ledMirror":
      return c(-o, -a, i, s, 2, "#dfe7ec"), t.save(), t.strokeStyle = "#fab005", f(-o, -a, o, -a), t.restore(), true;
    case "projector":
      return c(-o, -a, i, s, 20, r), u(-i * 0.25, a - 40, 40, "#1b1e22"), true;
    case "hedge": {
      t.fillStyle = r, t.beginPath();
      const g = Math.max(3, Math.round(i / 300));
      for (let m = 0; m <= g; m++) {
        const y = -o + i * m / g;
        t.arc(y, 0, a, 0, Math.PI * 2);
      }
      return t.fill(), c(-o, -a, i, s, a, null), true;
    }
    case "flowerBed":
    case "planterBox": {
      c(-o, -a, i, s, 4, r);
      const g = e.type === "flowerBed" ? 120 : 30;
      c(-o + g, -a + g, i - 2 * g, s - 2 * g, 2, "#5a4030");
      const m = ["#e64980", "#f59f00", "#ffffff", "#be4bdb"];
      let y = 0;
      for (let b = -o + g + 80; b < o - g; b += 160) for (let x = -a + g + 80; x < a - g; x += 160) t.fillStyle = m[y++ % 4], t.beginPath(), t.arc(b, x, 35, 0, 7), t.fill();
      return true;
    }
    case "palm": {
      u(0, 0, l * 0.07, "#8c7258");
      for (let g = 0; g < 9; g++) {
        const m = g * 0.698;
        t.save(), t.rotate(m), t.beginPath(), t.ellipse(l * 0.25, 0, l * 0.25, l * 0.05, 0, 0, 7), t.fillStyle = "rgba(79,127,69,.75)", t.fill(), t.stroke(), t.restore();
      }
      return true;
    }
    case "bamboo": {
      t.fillStyle = "rgba(111,154,74,.35)", t.beginPath(), t.ellipse(0, 0, o, a, 0, 0, 7), t.fill(), t.stroke();
      for (let g = 0; g < 12; g++) u(Math.cos(g * 2.4) * o * 0.6 * (g % 3 / 3 + 0.3), Math.sin(g * 2.4) * a * 0.6 * (g % 3 / 3 + 0.3), 25, "#7f9a4a");
      return true;
    }
    case "rock": {
      t.beginPath();
      const g = 9;
      for (let m = 0; m < g; m++) {
        const y = m / g * Math.PI * 2, b = 0.8 + m * 37 % 7 / 30, x = Math.cos(y) * o * b, v = Math.sin(y) * a * b;
        m ? t.lineTo(x, v) : t.moveTo(x, v);
      }
      return t.closePath(), t.fillStyle = r, t.fill(), t.stroke(), true;
    }
    case "pergola": {
      d(true), c(-o, -a, i, s, 0, null), d(false);
      for (let g = -o; g <= o + 1; g += 350) f(g, -a - 150, g, a + 150);
      for (const g of [-1, 1]) for (const m of [-1, 1]) c(g * (o - 60) - 60, m * (a - 60) - 60, 120, 120, 0, r);
      return true;
    }
    case "outdoorSofa":
      return c(-o, -a, i, 800, 60, r), c(-o, -a + 800, 800, s - 800 - 300, 60, r), c(-o + 950, -a + 1050, 900, 600, 20, _e(r, 0.25)), true;
    case "hammock":
      return f(-o, 0, o, 0), t.beginPath(), t.ellipse(0, 0, o - 300, a * 0.7, 0, 0, 7), t.fillStyle = r, t.fill(), t.stroke(), true;
    case "kidsSlide":
      return c(-o, -a, i, 900, 6, "#ffd43b"), c(-i * 0.35, -a + 900, i * 0.7, s - 900, 30, r), true;
    case "dogHouse":
      return c(-o, -a, i, s, 6, r), f(0, -a, 0, a), c(-i * 0.2, a - 30, i * 0.4, 30, 0, "#2b2e33"), true;
    case "firePit":
      return u(0, 0, l / 2, r), u(0, 0, l * 0.38, "#2b2e33"), u(0, 0, l * 0.15, "#ff922b"), true;
  }
  return false;
}
;
const Lt = (t, e, n) => t.opt && t.opt[e] !== void 0 ? t.opt[e] : n;
const ql = (t) => String(Lt(t, "shape", "box"));
const d8 = (t) => String(t || "").split("|").map((e) => e.split(",").map(Number)).filter((e) => e.length === 2 && e.every(Number.isFinite));
function g5(t) {
  const e = d8(String(Lt(t, "outline", "")));
  if (e.length < 3) return [[-t.w / 2, -t.d / 2], [t.w / 2, -t.d / 2], [t.w / 2, t.d / 2], [-t.w / 2, t.d / 2]];
  const n = e.map((l) => l[0]), i = e.map((l) => l[1]), s = Math.max(...n) - Math.min(...n) || 1, o = Math.max(...i) - Math.min(...i) || 1, a = (Math.max(...n) + Math.min(...n)) / 2, r = (Math.max(...i) + Math.min(...i)) / 2;
  return e.map(([l, c]) => [(l - a) * t.w / s, (c - r) * t.d / o]);
}
;
function ga(t) {
  const e = ql(t), n = t.w / 2, i = t.d / 2, s = (o = 40, a = 0, r = Math.PI * 2, l = i, c = 0) => Array.from({ length: o + 1 }, (f, u) => {
    const h = a + (r - a) * u / o;
    return [Math.cos(h) * n, c + Math.sin(h) * l];
  });
  switch (e) {
    case "extrude":
      return g5(t);
    case "model": {
      const o = d8(String(Lt(t, "fp", ""))), a = Number(Lt(t, "mw", t.w)) || t.w, r = Number(Lt(t, "md", t.d)) || t.d;
      return o.length >= 3 ? o.map(([l, c]) => [l * t.w / a, c * t.d / r]) : [[-n, -i], [n, -i], [n, i], [-n, i]];
    }
    case "cyl":
    case "tube":
    case "sphere":
    case "hemi":
    case "cone":
    case "torus":
    case "lathe":
      return s();
    case "halfCyl":
      return [...s(24, Math.PI, Math.PI * 2, t.d, i), [n, i]];
    case "arcWall": {
      const o = Math.max(10, Math.min(359, Number(Lt(t, "arc", 90)))) * Math.PI / 180, a = Number(Lt(t, "t", 120)), r = n / Math.max(0.05, Math.sin(Math.min(o, Math.PI) / 2)) || n, l = [], c = 24, f = r - i * 0;
      for (let d = 0; d <= c; d++) {
        const p = -Math.PI / 2 - o / 2 + o * d / c;
        l.push([Math.cos(p) * r, Math.sin(p) * r + f]);
      }
      for (let d = c; d >= 0; d--) {
        const p = -Math.PI / 2 - o / 2 + o * d / c;
        l.push([Math.cos(p) * (r - a), Math.sin(p) * (r - a) + f]);
      }
      const u = l.map((d) => d[1]), h = (Math.max(...u) + Math.min(...u)) / 2;
      return l.map(([d, p]) => [d, p - h]);
    }
    default:
      return [[-n, -i], [n, -i], [n, i], [-n, i]];
  }
}
;
const m8 = 170;
const qw = (t) => {
  var n;
  const e = Math.round(+(((n = t.opt) == null ? void 0 : n.steps) || 0));
  return e >= 1 ? e : Math.max(2, Math.round(Math.abs(t.h) / m8));
};
function Xw(t) {
  var m;
  const e = (m = t.opt) == null ? void 0 : m.winder;
  if (typeof e != "string" || !e.includes("|")) return null;
  const n = e.split("|").map((y) => {
    const [b, x] = y.split(",").map(Number);
    return { x: b, y: x };
  });
  if (n.length < 3 || n.some((y) => !isFinite(y.x) || !isFinite(y.y))) return null;
  const [i, ...s] = n, o = t.w / 2, a = t.d / 2, r = (y) => Math.atan2(y.y - i.y, y.x - i.x), l = r(s[0]), c = (y) => {
    for (; y <= -Math.PI; ) y += 2 * Math.PI;
    for (; y > Math.PI; ) y -= 2 * Math.PI;
    return y;
  }, f = Math.sign(c(r(s[1]) - l)) || 1, u = (y) => {
    let b = f * c(r(y) - l);
    return b < -1e-6 && (b += 2 * Math.PI), b;
  }, h = [{ x: -o, y: -a }, { x: o, y: -a }, { x: o, y: a }, { x: -o, y: a }].filter((y) => Math.hypot(y.x - i.x, y.y - i.y) > 1), d = s.map(u), p = [];
  for (let y = 0; y + 1 < s.length; y++) {
    const b = h.filter((x) => {
      const v = u(x);
      return v > d[y] + 1e-6 && v < d[y + 1] - 1e-6;
    }).sort((x, v) => u(x) - u(v));
    p.push([i, s[y], ...b, s[y + 1]]);
  }
  const g = [...s, ...h.filter((y) => {
    const b = u(y);
    return b > 1e-6 && b < d[d.length - 1] - 1e-6 && !s.some((x) => Math.hypot(x.x - y.x, x.y - y.y) < 1);
  })].sort((y, b) => u(y) - u(b));
  return { pv: i, rays: s, treads: p, path: g, rayAt: d };
}
;
function Pr(t) {
  const e = t.w, n = t.d, i = t.h, s = e / 2, o = n / 2, a = t.opt || {}, r = [], l = [], c = [], f = [];
  if (t.type === "stage") return c.push({ x0: -s, y0: -o, x1: s, y1: o - 400, top: i }), r.push({ x0: -s, y0: o - 400, x1: s, y1: o - 200, top: i * 2 / 3 }, { x0: -s, y0: o - 200, x1: s, y1: o, top: i / 3 }), { steps: r, flights: l, landings: c, rails: f };
  if (t.type === "stairRun") {
    if (a.flat) return c.push({ x0: -s, y0: -o, x1: s, y1: o, top: i }), { steps: r, flights: l, landings: c, rails: f };
    const N = Xw(t);
    if (N) {
      const F = i / N.treads.length;
      return N.treads.forEach((G, Y) => r.push({ x0: Math.min(...G.map((V) => V.x)), x1: Math.max(...G.map((V) => V.x)), y0: Math.min(...G.map((V) => V.y)), y1: Math.max(...G.map((V) => V.y)), top: (Y + 1) * F, poly: G })), { steps: r, flights: l, landings: c, rails: f };
    }
    const U = qw(t), $ = i / U, H = n / U;
    for (let F = 0; F < U; F++) r.push({ x0: -s, x1: s, y1: o - F * H, y0: o - (F + 1) * H, top: (F + 1) * $ });
    l.push({ pts: [{ x: 0, y: o - H / 2 }, { x: 0, y: -o + H / 2 }], z0: $, z1: i });
    for (const F of a.rail === "both" ? [-1, 1] : a.rail === "left" ? [-1] : a.rail === "right" ? [1] : []) f.push([{ x: F * (s - 40), y: o, z: $ }, { x: F * (s - 40), y: -o, z: i }]);
    return { steps: r, flights: l, landings: c, rails: f };
  }
  if (t.type === "stairDogleg") return WI(t);
  const { run: u, land: h, r: d, n1: p, n2: g, k: m, sgn: y } = Zw(t), b = n - h, x = e - 2 * u, v = Math.max(1, Math.round(i / d) - p - g - 2 * m), w = (N) => N * y, M = (N, U, $, H, F) => ({ x0: Math.min(w(N), w(U)), x1: Math.max(w(N), w(U)), y0: Math.min($, H), y1: Math.max($, H), top: F }), S = b / p;
  for (let N = 0; N < p; N++) r.push(M(s - u, s, o - N * S, o - (N + 1) * S, (N + 1) * d));
  if (m) {
    const N = h / m;
    for (let U = 0; U < m; U++) r.push(M(s - u, s, -o + h - U * N, -o + h - (U + 1) * N, (p + U + 1) * d));
  } else c.push(M(s - u, s, -o, -o + h, p * d));
  if (g) {
    const N = x / g;
    for (let U = 0; U < g; U++) r.push(M(s - u - U * N, s - u - (U + 1) * N, -o, -o + h, (p + m + U + 1) * d));
  }
  if (m) {
    const N = h / m;
    for (let U = 0; U < m; U++) r.push(M(-s, -s + u, -o + U * N, -o + (U + 1) * N, (p + m + g + U + 1) * d));
  } else c.push(M(-s, -s + u, -o, -o + h, (p + g) * d));
  const A = p + g + 2 * m, T = b / v;
  for (let N = 0; N < v; N++) r.push(M(-s, -s + u, -o + h + N * T, -o + h + (N + 1) * T, (A + N + 1) * d));
  const _ = w(s - u / 2), R = w(-s + u / 2), P = -o + h / 2;
  l.push({ pts: [{ x: _, y: o - S / 2 }, { x: _, y: P }, { x: R, y: P }, { x: R, y: o - T / 2 }], z0: d, z1: i });
  const D = w(s - u - 40), E = w(-s + u + 40), I = -o + h + 40;
  return f.push([{ x: D, y: o, z: d }, { x: D, y: I, z: p * d }, { x: E, y: I, z: (p + 2 * m + g) * d }, { x: E, y: o, z: i }]), { steps: r, flights: l, landings: c, rails: f };
}
;
function Kw(t) {
  const e = t.w, n = t.d, i = t.h, s = e / 2, o = n / 2, a = t.opt || {}, r = Math.max(0, +(a.gap ?? 120)), l = (e - r) / 2, c = Math.min(l, n * 0.5), f = Math.max(6, Math.round(i / m8)), u = i / f, h = Math.max(3, Math.min(Math.round(+(a.winders ?? 7)), f - 4)), d = Math.ceil((f - h) / 2), p = f - h - d, g = a.start === "left" ? -1 : 1, m = { x: 0, y: -o + c };
  return { W: e, D: n, H: i, hw: s, hd: o, gap: r, run: l, turn: c, N: f, r: u, k: h, n1: d, n3: p, sgn: g, pv: m };
}
;
function WI(t) {
  const { hw: e, hd: n, gap: i, run: s, turn: o, r: a, k: r, n1: l, n3: c, sgn: f, pv: u, H: h } = Kw(t), d = [], p = [], g = [], m = [], y = (P) => P * f, b = 2 * n - o, x = (P, D, E, I, N) => ({ x0: Math.min(y(P), y(D)), x1: Math.max(y(P), y(D)), y0: Math.min(E, I), y1: Math.max(E, I), top: N }), v = b / l;
  for (let P = 0; P < l; P++) d.push(x(i / 2, e, n - P * v, n - (P + 1) * v, (P + 1) * a));
  const w = (P) => {
    const D = Math.cos(P) * f, E = -Math.sin(P);
    let I = 1 / 0;
    return D > 1e-9 && (I = Math.min(I, (e - u.x) / D)), D < -1e-9 && (I = Math.min(I, (-e - u.x) / D)), E < -1e-9 && (I = Math.min(I, (-n - u.y) / E)), { x: u.x + D * I, y: u.y + E * I };
  }, M = [{ a: Math.atan2(o, e), p: { x: y(e), y: -n } }, { a: Math.PI - Math.atan2(o, e), p: { x: y(-e), y: -n } }];
  for (let P = 0; P < r; P++) {
    const D = Math.PI * P / r, E = Math.PI * (P + 1) / r, I = [u, w(D), ...M.filter((N) => N.a > D + 1e-6 && N.a < E - 1e-6).map((N) => N.p), w(E)];
    d.push({ x0: Math.min(...I.map((N) => N.x)), x1: Math.max(...I.map((N) => N.x)), y0: Math.min(...I.map((N) => N.y)), y1: Math.max(...I.map((N) => N.y)), top: (l + P + 1) * a, poly: I });
  }
  const S = b / c;
  for (let P = 0; P < c; P++) d.push(x(-e, -i / 2, u.y + P * S, u.y + (P + 1) * S, (l + r + P + 1) * a));
  const A = y(i / 2 + s / 2), T = y(-i / 2 - s / 2);
  p.push({ pts: [{ x: A, y: n - v / 2 }, { x: A, y: u.y }, { x: y(0), y: u.y - o / 2 }, { x: T, y: u.y }, { x: T, y: n - S / 2 }], z0: a, z1: h });
  const _ = i / 2 + 40, R = [{ x: y(_), y: n, z: a }];
  for (let P = 0; P <= 12; P++) {
    const D = Math.PI * P / 12;
    R.push({ x: u.x + Math.cos(D) * _ * f, y: u.y - Math.sin(D) * _, z: (l + r * P / 12) * a });
  }
  return R.push({ x: y(-_), y: n, z: h }), m.push(R), { steps: d, flights: p, landings: g, rails: m };
}
;
function Zw(t) {
  const e = t.w, n = t.d, i = t.h, s = t.opt || {}, o = Math.min(+(s.run || e * 0.32), e * 0.5), a = Math.min(+(s.land || 1050), n * 0.6), r = n - a, l = e - 2 * o, c = 2 * r + l, f = Math.max(6, Math.round(i / m8)), u = i / f, h = Math.max(0, Math.min(Math.round(+(s.winders || 0)), Math.floor((f - 2) / 2))), d = Math.max(l > 200 ? 1 : 0, Math.round((f - 2 * h) * l / c)), p = Math.max(1, Math.round((f - d - 2 * h) / 2));
  return { run: o, land: a, N: f, r: u, n1: p, n2: d, k: h, sgn: s.start === "left" ? -1 : 1 };
}
;
function f3(t, e, n) {
  var h, d, p, g, m, y, b, x, v, w, M, S, A, T, _, R, P, D;
  if (is(e)) {
    $I(t, e, n);
    return;
  }
  const i = e.w, s = e.d, o = i / 2, a = s / 2, r = e.color;
  t.lineWidth = n * 1.1, t.strokeStyle = "#4b525d", t.lineJoin = "round", t.setLineDash([]);
  const l = (E, I, N, U, $, H) => {
    t.beginPath(), fs(t, E, I, N, U, $), H && (t.fillStyle = H, t.fill()), t.stroke();
  }, c = (E, I, N, U) => {
    t.beginPath(), t.moveTo(E, I), t.lineTo(N, U), t.stroke();
  }, f = (E, I, N, U) => {
    t.beginPath(), t.arc(E, I, Math.max(1, N), 0, Math.PI * 2), U && (t.fillStyle = U, t.fill()), t.stroke();
  }, u = (E, I, N, U, $) => {
    t.beginPath(), t.ellipse(E, I, Math.max(1, N), Math.max(1, U), 0, 0, Math.PI * 2), $ && (t.fillStyle = $, t.fill()), t.stroke();
  };
  switch (e.type) {
    case "free": {
      const E = ga(e), I = ql(e), N = String(((h = e.opt) == null ? void 0 : h.mat) || "paint"), U = N === "glass" || N === "frosted";
      if (t.beginPath(), E.forEach(([$, H], F) => F ? t.lineTo($, H) : t.moveTo($, H)), t.closePath(), t.fillStyle = U ? "rgba(188,216,234,.35)" : N === "water" ? "rgba(79,163,199,.55)" : r, t.fill(), ["grass", "gravel", "pebble", "paver", "bluestone", "deck", "soil"].includes(N) && (t.save(), t.clip(), t.fillStyle = h8(t, { paver: "paving" }[N] || N), t.fillRect(-o, -a, i, s), t.restore()), (d = e.opt) != null && d.zone) {
        t.save(), t.clip(), t.strokeStyle = "rgba(90,98,112,.35)", t.lineWidth = n, t.beginPath();
        for (let $ = -o - s; $ < o; $ += 120) t.moveTo($, a), t.lineTo($ + s, -a);
        t.stroke(), t.restore();
      }
      if (t.stroke(), (p = e.opt) != null && p.zone && ((g = e.opt) != null && g.cove) && (t.save(), t.setLineDash([n * 8, n * 5]), t.strokeStyle = "#f08c00", t.lineWidth = n * 1.8, t.beginPath(), E.forEach(([$, H], F) => F ? t.lineTo($, H) : t.moveTo($, H)), t.closePath(), t.stroke(), t.restore()), I === "slats") {
        const $ = Math.max(2, Number((m = e.opt) == null ? void 0 : m.n) || Math.round(i / 120));
        for (let H = 1; H < $; H++) c(-o + i * H / $, -a, -o + i * H / $, a);
      }
      if (I === "steps") {
        const $ = Math.max(1, Number((y = e.opt) == null ? void 0 : y.n) || 3);
        for (let H = 1; H < $; H++) c(-o, -a + s * H / $, o, -a + s * H / $);
      }
      if (I === "arch") {
        const $ = Number((b = e.opt) == null ? void 0 : b.t) || 200;
        l(-o + $, -a, i - 2 * $, s, 0, "#ffffff");
      }
      if (I === "tube") {
        const $ = Number((x = e.opt) == null ? void 0 : x.t) || 100;
        u(0, 0, Math.max(1, o - $), Math.max(1, a - $), "#ffffff");
      }
      I === "wedge" && (c(-o, -a, o, a), c(o, -a, -o, a)), I === "pyramid" && (c(-o, -a, o, a), c(o, -a, -o, a)), (I === "cone" || I === "hemi" || I === "sphere") && f(0, 0, Math.min(i, s) * 0.06);
      break;
    }
    case "airVent":
      l(-o, -a, i, s, 0, r);
      for (let E = -o + 40; E < o; E += 50) c(E, -a + 20, E, a - 20);
      break;
    case "curveTrainingTable": {
      const E = km(e);
      E.length >= 3 && E.every((I) => I.length === 2 && I.every(Number.isFinite)) ? (t.beginPath(), E.forEach(([I, N], U) => U ? t.lineTo(I, N) : t.moveTo(I, N)), t.closePath(), t.fillStyle = r, t.fill(), t.stroke()) : l(-o, -a, i, s, 20, r);
      break;
    }
    case "trainingTable":
      l(-o, -a, i, s, 12, r), c(-o + 60, a - 50, o - 60, a - 50);
      break;
    case "stage":
      l(-o, -a, i, s, 2, r), c(-o, a - 180, o, a - 180), c(-o, a - 360, o, a - 360);
      break;
    case "lectern":
      l(-o, -a, i, s, 15, r), l(-o + 70, -a + 70, i - 140, s * 0.45, 5, "#414a53"), c(-o + 40, a - 90, o - 40, a - 90);
      break;
    case "slidingBoard":
      l(-o, -a, i, s, 0, r);
      for (let E = 1; E < 3; E++) c(-o + i * E / 3, -a, -o + i * E / 3, a);
      break;
    case "mobileDisplay":
      l(-o, -a, i, Math.min(100, s), 4, "#293443"), c(0, -a + 100, 0, a), c(-o * 0.65, a - 30, o * 0.65, a - 30);
      break;
    case "printer":
      l(-o, -a, i, s, 20, r), l(-o + 60, -a + 60, i - 120, s * 0.45, 12, "#4e5966"), l(-o + 80, a - 150, i - 160, 100, 4, "#f9f9f5");
      break;
    case "coffeeMachine":
      l(-o, -a, i, s, 15, r), f(-i * 0.2, -s * 0.2, 50), l(-o + 60, 0, i - 120, s * 0.4, 3, "#87909b");
      break;
    case "urinal":
      l(-o, -a, i, s, Math.min(i, s) * 0.2, r), u(0, 15, i * 0.32, s * 0.32, "#d3e5e7"), f(0, s * 0.18, 18);
      break;
    case "serviceSink":
      l(-o, -a, i, s, 10, r), l(-o + 55, -a + 70, i - 110, s - 120, 20, "#cbdde0"), f(0, -a + 40, 20);
      break;
    case "wifiAP":
      f(0, 0, Math.min(i, s) * 0.48, r), f(0, 0, 18, "#50b5b0");
      break;
    case "ceilingSpeaker":
      f(0, 0, Math.min(i, s) * 0.48, r);
      for (let E = 30; E < Math.min(i, s) * 0.42; E += 30) f(0, 0, E);
      break;
    case "bed": {
      l(-o, -a, i, s, 30, "#f4efe8"), l(-o, -a, i, 100, 20, _e(r, -0.3));
      const E = i > 1300 ? 2 : 1, I = 60, N = (i - 160 - (E - 1) * I) / E;
      for (let U = 0; U < E; U++) l(-o + 80 + U * (N + I), -a + 160, N, 360, 70, "#ffffff");
      l(-o + 15, -a + s * 0.4, i - 30, s * 0.6 - 15, 30, r), c(-o + 15, -a + s * 0.4 + 200, o - 15, -a + s * 0.4 + 200);
      break;
    }
    case "nightstand":
      l(-o, -a, i, s, 20, r), f(0, 0, Math.min(i, s) * 0.28, "#f7f1e3"), f(0, 0, Math.min(i, s) * 0.07);
      break;
    case "wardrobe": {
      l(-o, -a, i, s, 8, r), t.setLineDash([n * 5, n * 4]), c(-o + 50, 0, o - 50, 0), t.setLineDash([]);
      for (let E = -o + 160; E < o - 80; E += 200) c(E - 50, -s * 0.3, E + 50, s * 0.3);
      c(-o, a - 40, o, a - 40);
      break;
    }
    case "sofa":
    case "armchair":
    case "lounge": {
      const E = Math.min(230, s * 0.26), I = e.type === "lounge" ? 90 : Math.min(180, i * 0.14), N = String(p0(e, "arms", "both")), U = N === "both" || N === "left" ? I : 0, $ = N === "both" || N === "right" ? I : 0;
      l(-o, -a, i, s, 70, _e(r, -0.15)), l(-o + U, -a + E, i - U - $, s - E - 25, 45, r);
      const H = e.type !== "sofa" ? 1 : N === "both" ? i > 1700 ? 3 : 2 : Math.max(1, Math.round((i - U - $) / 750)), F = (i - U - $) / H;
      for (let G = 1; G < H; G++) c(-o + U + F * G, -a + E, -o + U + F * G, a - 25);
      break;
    }
    case "coffeeTable":
      l(-o, -a, i, s, Math.min(i, s) * 0.2, r), l(-o + 50, -a + 50, i - 100, s - 100, Math.min(i, s) * 0.16, null);
      break;
    case "tvCabinet":
      l(-o, -a, i, s, 8, r), l(-Math.min(i * 0.36, 800), -a + 40, Math.min(i * 0.72, 1600), 55, 10, "#2a2d33");
      for (let E = 1; E < 3; E++) c(-o + i * E / 3, 0, -o + i * E / 3, a);
      break;
    case "diningTable":
      l(-o, -a, i, s, 40, r), l(-o + 40, -a + 40, i - 80, s - 80, 30, null);
      break;
    case "desk":
      l(-o, -a, i, s, 12, r), l(-Math.min(280, i * 0.3), -a + 60, Math.min(560, i * 0.6), 50, 10, "#2a2d33"), l(-Math.min(220, i * 0.25), 20, Math.min(440, i * 0.5), 140, 12, "#eceae6");
      break;
    case "sideTable":
      f(0, 0, Math.min(i, s) / 2, r), f(0, 0, Math.min(i, s) * 0.38);
      break;
    case "chair":
      l(-o, -a + 40, i, s - 40, 70, r), l(-o, -a, i, 90, 40, _e(r, -0.3));
      break;
    case "officeChair":
      f(0, 30, Math.min(i, s) * 0.38, r), l(-o + 50, -a, i - 100, 120, 55, _e(r, -0.3)), l(-o, -40, 70, 260, 30, _e(r, -0.2)), l(o - 70, -40, 70, 260, 30, _e(r, -0.2));
      break;
    case "bookshelf":
      l(-o, -a, i, s, 6, r);
      for (let E = -o + 300; E < o - 50; E += 300) c(E, -a, E, a);
      break;
    case "counter": {
      l(-o, -a, i, s, 8, r), c(-o, -a + 40, o, -a + 40);
      const E = Math.min(750, i * 0.3);
      l(-o + i * 0.12, -a + 90, E, s - 180, 50, "#dfe3e6"), f(-o + i * 0.12 + E / 2, -a + 150, 22);
      const I = o - Math.min(i * 0.25, 600);
      l(I - 320, -a + 70, 640, s - 140, 16, "#2b2e33"), t.strokeStyle = "#9aa1ab", f(I - 160, 0, 95), f(I + 160, 0, 95);
      break;
    }
    case "fridge":
      l(-o, -a, i, s, 20, r), c(-o, a - 90, o, a - 90), c(0, a - 90, 0, a);
      break;
    case "shoeCabinet":
    case "island": {
      l(-o, -a, i, s, 10, r);
      const E = Math.max(1, Math.round(i / 400));
      for (let I = 1; I < E; I++) c(-o + I * i / E, -a + 30, -o + I * i / E, a - 30);
      break;
    }
    case "rug": {
      t.globalAlpha = 0.85, l(-o, -a, i, s, 30, r), t.globalAlpha = 1, t.setLineDash([n * 6, n * 4]), t.strokeStyle = _e(r, -0.3), l(-o + 120, -a + 120, i - 240, s - 240, 20, null), t.setLineDash([]);
      break;
    }
    case "plant": {
      const E = Math.min(i, s) / 2;
      t.strokeStyle = "#3f5f38";
      for (let I = 0; I < 8; I++) {
        const N = I / 8 * Math.PI * 2;
        f(Math.cos(N) * E * 0.5, Math.sin(N) * E * 0.5, E * 0.45, I % 2 ? _e(r, 0.15) : r);
      }
      f(0, 0, E * 0.35, _e(r, -0.1));
      break;
    }
    case "toilet":
      l(-o, -a, i, s * 0.26, 40, r), u(0, -a + s * 0.63, o * 0.9, s * 0.37, r), u(0, -a + s * 0.65, o * 0.6, s * 0.27, "#eef3f6");
      break;
    case "vanity": {
      p0(e, "hang", false) && t.setLineDash([n * 6, n * 4]), l(-o, -a, i, s, 20, r), t.setLineDash([]);
      const E = p0(e, "basins", i >= 1200 ? 2 : 1);
      for (let I = 0; I < E; I++) {
        const N = -o + i * (I + 0.5) / E;
        u(N, 20, Math.min(i / E * 0.3, 250), s * 0.3, "#ffffff"), f(N, -a + 70, 18);
      }
      p0(e, "mirror", true) && (t.strokeStyle = "#7fb0cc", c(-o * 0.85, -a - 25, o * 0.85, -a - 25));
      break;
    }
    case "shower": {
      const E = p0(e, "shape", "square"), I = Math.min(i, s) * 0.38;
      t.beginPath(), E === "diamond" ? (t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, a - I), t.lineTo(o - I, a), t.lineTo(-o, a), t.closePath()) : E === "arc" ? (t.moveTo(-o, -a), t.lineTo(o, -a), t.ellipse(-o, -a, i, s, 0, 0, Math.PI / 2), t.closePath()) : t.rect(-o, -a, i, s), t.fillStyle = "#eef3f6", t.fill(), t.stroke(), f(-o + Math.min(i, s) * 0.35, -a + Math.min(i, s) * 0.35, 40, "#fff"), t.lineWidth = n * 3, t.strokeStyle = "#7fb0cc", E === "diamond" ? (t.beginPath(), t.moveTo(-o, a), t.lineTo(o - I, a), t.lineTo(o, a - I), t.lineTo(o, -a), t.stroke()) : E === "arc" ? (t.beginPath(), t.ellipse(-o, -a, i, s, 0, 0, Math.PI / 2), t.stroke()) : E === "line" ? c(-o, a, o, a) : (c(-o, a, o, a), c(o, -a, o, a));
      break;
    }
    case "bathtub":
      l(-o, -a, i, s, s * 0.25, r), l(-o + 70, -a + 70, i - 140, s - 140, s * 0.3, "#e3f1f7"), f(-o + 220, 0, 28);
      break;
    case "washer":
      l(-o, -a, i, s, 40, r), f(0, 40, Math.min(i, s) * 0.3, "#dfe6ea"), c(-o + 40, -a + 90, o - 40, -a + 90);
      break;
    case "bunkBed": {
      l(-o, -a, i, s, 20, "#f4efe8"), l(-o, -a, i, 80, 10, _e(r, -0.2)), l(-o, a - 80, i, 80, 10, _e(r, -0.2)), l(-o + 60, -a + 140, i - 120, 300, 60, "#ffffff"), l(-o + 15, -a + s * 0.35, i - 30, s * 0.65 - 95, 30, r), t.setLineDash([n * 5, n * 3]), c(-o, -a, o, a), t.setLineDash([]), l(o - 120, -a + s * 0.3, 100, s * 0.4, 10, _e(r, -0.25));
      break;
    }
    case "crib": {
      l(-o, -a, i, s, 20, r), l(-o + 50, -a + 50, i - 100, s - 100, 16, "#ffffff");
      for (let E = -o + 100; E < o - 60; E += 90) c(E, -a + 10, E, -a + 45);
      for (let E = -o + 100; E < o - 60; E += 90) c(E, a - 45, E, a - 10);
      break;
    }
    case "tatami": {
      l(-o, -a, i, s, 10, r);
      const E = Math.max(1, Math.round(i / 900)), I = Math.max(1, Math.round(s / 900));
      for (let N = 1; N < E; N++) c(-o + i * N / E, -a, -o + i * N / E, a);
      for (let N = 1; N < I; N++) c(-o, -a + s * N / I, o, -a + s * N / I);
      l(-o + 80, -a + 80, Math.min(600, i * 0.3), Math.min(400, s * 0.2), 40, "#ffffff");
      break;
    }
    case "bedBench":
    case "entryBench":
      l(-o, -a, i, s, 40, r), l(-o + 40, -a + 40, i - 80, s - 80, 30, _e(r, 0.15));
      break;
    case "dresser":
      l(-o, -a, i, s, 12, r), l(-Math.min(300, i * 0.3), -a + 10, Math.min(600, i * 0.6), 40, 10, "#dfe9ef"), f(0, 60, Math.min(i, s) * 0.18);
      break;
    case "mirror":
      l(-o, -a, i, s, 6, "#dfe9ef"), c(-o + 40, a, o - 40, a);
      break;
    case "lSofa": {
      const N = Math.min(950, s * 0.56), U = _e(r, -0.15);
      t.beginPath(), t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, -a + N), t.lineTo(-o + N, -a + N), t.lineTo(-o + N, a), t.lineTo(-o, a), t.closePath(), t.fillStyle = U, t.fill(), t.stroke(), l(-o + 230, -a + 230, i - 230 - 160, N - 230 - 25, 40, r), l(-o + 230, -a + N - 30, N - 230 - 25, s - N - 160 + 30, 40, r);
      const $ = 3, H = (i - 230 - 160) / $;
      for (let F = 1; F < $; F++) c(-o + 230 + H * F, -a + 230, -o + 230 + H * F, -a + N - 25);
      break;
    }
    case "sideboard":
      l(-o, -a, i, s, 6, r), c(-o, -a, o, a), c(o, -a, -o, a);
      for (let E = 1; E < 4; E++) c(-o + i * E / 4, a - 60, -o + i * E / 4, a);
      break;
    case "kitchenIsland": {
      const E = p0(e, "seat", 0);
      l(-o, -a, i, s, 20, r), l(-o + 30, -a + 30, i - 60, s - 60, 14, null), E > 0 && (t.setLineDash([n * 5, n * 3]), c(-o, a - E, o, a - E), t.setLineDash([]));
      const I = s - Math.max(0, E);
      if (p0(e, "sink", true) && (l(-o + i * 0.14, -a + 90, Math.min(600, i * 0.3), Math.max(200, I - 180), 30, "#dfe3e6"), f(-o + i * 0.14 + Math.min(300, i * 0.15), -a + 130, 20)), p0(e, "hob", false)) {
        const N = o - Math.min(i * 0.25, 450);
        l(N - 300, -a + 80, 600, Math.max(200, I - 160), 14, "#2b2e33"), t.strokeStyle = "#9aa1ab", f(N - 140, -a + I / 2, 80), f(N + 140, -a + I / 2, 80);
      }
      break;
    }
    case "barStool":
      f(0, 0, Math.min(i, s) * 0.42, r), f(0, 0, Math.min(i, s) * 0.25);
      break;
    case "piano":
      l(-o, -a, i, s, 12, r), l(-o + 60, a - 220, i - 120, 160, 8, "#f6f6f2");
      for (let E = -o + 110; E < o - 70; E += 70) c(E, a - 220, E, a - 60);
      break;
    case "acWall":
    case "acFloor": {
      t.setLineDash(e.type === "acWall" ? [n * 5, n * 3] : []), l(-o, -a, i, s, 20, r), t.setLineDash([]), t.strokeStyle = "#7fa4c4";
      for (let E = 1; E <= 3; E++) c(-o + 60, -a + s * E / 4, o - 60, -a + s * E / 4);
      break;
    }
    case "waterHeater":
    case "gasHeater": {
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, s, e.type === "waterHeater" ? s / 2 : 20, r), t.setLineDash([]), t.strokeStyle = "#e03131", f(-i * 0.15, 0, Math.min(i, s) * 0.12), t.strokeStyle = "#1c7ed6", f(i * 0.15, 0, Math.min(i, s) * 0.12);
      break;
    }
    case "waterDispenser":
    case "purifier":
    case "airPurifier":
      l(-o, -a, i, s, 30, r), f(0, 0, Math.min(i, s) * 0.28, "#dbe8f2");
      break;
    case "dishwasher":
    case "dryer":
    case "tallOven":
      l(-o, -a, i, s, 16, r), l(-o + 50, -a + 70, i - 100, 60, 8, "#9aa1ab"), e.type === "dryer" ? f(0, 40, Math.min(i, s) * 0.3, "#e6eaee") : c(-o + 50, a - 60, o - 50, a - 60);
      break;
    case "hood":
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, s, 16, r), c(-o, -a, o, a), c(o, -a, -o, a), t.setLineDash([]);
      break;
    case "microwave":
      l(-o, -a, i, s, 12, r), l(-o + 30, -a + 40, i * 0.65, s - 80, 8, "#2b2e33");
      break;
    case "wallTV":
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, Math.max(s, 40), 4, "#2a2d33"), t.setLineDash([]);
      break;
    case "robotVac":
      l(-o, -a, i, s, 30, r), f(0, s * 0.1, Math.min(i, s) * 0.36, "#55595f");
      break;
    case "treadmill":
      l(-o, -a, i, s, 30, r), l(-o + 80, -a + 260, i - 160, s - 360, 40, "#4a4e55"), l(-o + 40, -a + 20, i - 80, 180, 30, "#3b3f46");
      break;
    case "floorLamp":
    case "deskLamp":
      f(0, 0, Math.min(i, s) / 2, "#fff8e6"), f(0, 0, Math.min(i, s) * 0.18, r), c(-o * 0.7, 0, o * 0.7, 0), c(0, -a * 0.7, 0, a * 0.7);
      break;
    case "curtain": {
      t.strokeStyle = _e(r, -0.35), c(-o, -a + 20, o, -a + 20), t.beginPath();
      const E = Math.max(6, Math.round(i / 120));
      for (let I = 0; I <= E; I++) {
        const N = -o + i * I / E, U = I % 2 ? a : -a + 50;
        I ? t.lineTo(N, U) : t.moveTo(N, U);
      }
      t.stroke();
      break;
    }
    case "showerScreen":
      t.lineWidth = n * 3, t.strokeStyle = "#7fb0cc", c(-o, 0, o, 0), t.lineWidth = n * 1.1, t.strokeStyle = "#4b525d", f(-o, 0, 20);
      break;
    case "showerSet": {
      const E = Math.min(260, i * 0.3);
      l(-o, -a, i, s, 6, r), l(o - E, -a, E, s, 4, _e(r, -0.12)), c(o - E + 20, a - 10, o - 30, -a + 15);
      const I = Math.min(60, s * 0.35, (i - E) / 8);
      for (let N = 0; N < 3; N++) f(-o + (i - E) * (N + 1) / 4, 0, I);
      break;
    }
    case "towelWarmer":
      l(-o, -a, i, s, 10, r);
      for (let E = -o + 60; E < o - 30; E += 90) c(E, -a, E, a);
      break;
    case "mirrorCabinet":
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, s, 6, "#dfe9ef"), t.setLineDash([]), c(0, -a, 0, a);
      break;
    case "bathHeater":
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, s, 20, r), t.setLineDash([]), f(0, 0, Math.min(i, s) * 0.3);
      for (let E = 0; E < 4; E++) {
        const I = E * Math.PI / 2 + 0.6;
        c(0, 0, Math.cos(I) * i * 0.28, Math.sin(I) * s * 0.28);
      }
      break;
    case "clothesRack":
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, s, 20, null), t.setLineDash([]), t.strokeStyle = "#7d8793";
      for (const E of [-s * 0.3, 0, s * 0.3]) c(-o + 40, E, o - 40, E);
      break;
    case "laundrySink":
      l(-o, -a, i, s, 16, r), l(-o + 60, -a + 60, i - 120, s - 140, 40, "#dfe3e6"), f(0, -a + 100, 20);
      break;
    case "roundBed": {
      const E = Math.min(i, s) / 2;
      f(0, 0, E, "#f4efe8"), t.beginPath(), t.arc(0, 0, E, Math.PI * 1.15, Math.PI * 1.85), t.lineWidth = n * 6, t.strokeStyle = _e(r, -0.3), t.stroke(), t.lineWidth = n * 1.1, t.strokeStyle = "#4b525d", f(0, E * 0.2, E * 0.72, r), l(-E * 0.45, -E * 0.62, E * 0.4, E * 0.22, 30, "#fff"), l(E * 0.05, -E * 0.62, E * 0.4, E * 0.22, 30, "#fff");
      break;
    }
    case "chest":
      l(-o, -a, i, s, 8, r);
      for (let E = 1; E < 4; E++) c(-o + 30, -a + s * E / 4, o - 30, -a + s * E / 4);
      break;
    case "coatRack":
      f(0, 0, Math.min(i, s) * 0.35, r);
      for (let E = 0; E < 3; E++) {
        const I = E * 2.09;
        c(0, 0, Math.cos(I) * o, Math.sin(I) * a);
      }
      break;
    case "stool":
    case "ottoman":
      f(0, 0, Math.min(i, s) / 2, r), f(0, 0, Math.min(i, s) * 0.36);
      break;
    case "bayCushion":
      l(-o, -a, i, s, 30, r);
      for (let E = 0; E < 3; E++) l(-o + 100 + E * 500, -a + 30, 420, 120, 40, _e(r, -0.1));
      break;
    case "lDesk": {
      const E = Math.min(600, i * 0.4);
      t.beginPath(), t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, a), t.lineTo(o - E, a), t.lineTo(o - E, -a + 600), t.lineTo(-o, -a + 600), t.closePath(), t.fillStyle = r, t.fill(), t.stroke(), l(-o + 200, -a + 60, 560, 50, 10, "#2a2d33");
      break;
    }
    case "uSofa": {
      const E = Math.min(950, s * 0.48), I = _e(r, -0.15);
      t.beginPath(), t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, a), t.lineTo(o - E, a), t.lineTo(o - E, -a + E), t.lineTo(-o + E, -a + E), t.lineTo(-o + E, a), t.lineTo(-o, a), t.closePath(), t.fillStyle = I, t.fill(), t.stroke(), l(-o + 200, -a + 230, i - 400, E - 250, 40, r), l(-o + 200, -a + E - 20, E - 220, s - E - 30, 40, r), l(o - E + 20, -a + E - 20, E - 220, s - E - 30, 40, r);
      break;
    }
    case "curvedSofa":
    case "bendSofa": {
      const E = V3(e), I = (N, U) => {
        t.beginPath(), N.forEach(($, H) => H ? t.lineTo($.x, $.y) : t.moveTo($.x, $.y)), t.closePath(), t.fillStyle = U, t.fill(), t.stroke();
      };
      I(E.outline, _e(r, -0.14)), I(E.seat, r), E.back.length && I(E.back, _e(r, -0.24));
      for (const N of E.splits) {
        const U = Jv(E, N), $ = N >= E.open && E.back.length ? U.d / 2 - E.bk : U.d / 2 - 40;
        c(U.p.x + U.n.x * $, U.p.y + U.n.y * $, U.p.x - U.n.x * (U.d / 2 - 30), U.p.y - U.n.y * (U.d / 2 - 30));
      }
      break;
    }
    case "chaise":
      l(-o, -a, i, s, 60, _e(r, -0.12)), l(-o + 60, -a + 60, i - 120, s - 120, 50, r), l(-o + 40, -a + 40, 420, s - 80, 60, _e(r, -0.2));
      break;
    case "beanbag":
      t.beginPath(), t.ellipse(0, 0, o, a, 0.3, 0, Math.PI * 2), t.fillStyle = r, t.fill(), t.stroke(), t.beginPath(), t.ellipse(0, -a * 0.3, o * 0.55, a * 0.4, 0.3, 0, Math.PI * 2), t.stroke();
      break;
    case "roundTable":
      f(0, 0, Math.min(i, s) / 2, r), f(0, 0, Math.min(i, s) / 2 - 50);
      break;
    case "ovalTable":
      u(0, 0, o, a, r), u(0, 0, o - 50, a - 50);
      break;
    case "booth":
      l(-o, -a, i, s, 20, _e(r, -0.15)), l(-o + 20, -a + 160, i - 40, s - 180, 20, r);
      break;
    case "wineCabinet":
    case "displayCabinet":
      l(-o, -a, i, s, 6, r), t.strokeStyle = "#7fb0cc", c(-o + 30, a - 25, o - 30, a - 25), t.strokeStyle = "#4b525d", c(0, a - 60, 0, a);
      break;
    case "consoleTable":
      l(-o, -a, i, s, 12, r), f(-o + 250, 0, Math.min(s * 0.25, 90), "#d9cdb8");
      break;
    case "rockingChair":
      l(-o, -a + 100, i, s - 200, 60, r), t.lineWidth = n * 3, c(-o + 40, -a, -o + 40, a), c(o - 40, -a, o - 40, a), t.lineWidth = n * 1.1;
      break;
    case "hangingChair": {
      const E = Math.min(i, s) / 2;
      t.setLineDash([n * 5, n * 3]), f(0, 0, E * 0.9), t.setLineDash([]), f(0, 0, E * 0.55, r), f(0, 0, E * 0.3, "#f2ede4");
      break;
    }
    case "fireplace":
      l(-o, -a, i, s, 8, r), l(-i * 0.3, a - 90, i * 0.6, 70, 6, "#2b2e33");
      break;
    case "fishTank":
      l(-o, -a, i, s, 8, r), l(-o + 30, -a + 30, i - 60, s - 60, 6, "#bfe3ef");
      break;
    case "projScreen":
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, Math.max(s, 40), 4, "#f4f4f2"), t.setLineDash([]);
      break;
    case "speaker":
      l(-o, -a, i, s, 20, r), f(0, 30, Math.min(i, s) * 0.3, "#555");
      break;
    case "screenDivider": {
      t.lineWidth = n * 3, t.strokeStyle = _e(r, -0.2);
      const E = Math.max(3, Math.round(i / 450));
      t.beginPath();
      for (let I = 0; I <= E; I++) {
        const N = -o + i * I / E, U = I % 2 ? 60 : -60;
        I ? t.lineTo(N, U) : t.moveTo(N, U);
      }
      t.stroke(), t.lineWidth = n * 1.1;
      break;
    }
    case "hangingPlant": {
      t.setLineDash([n * 5, n * 3]), f(0, 0, Math.min(i, s) / 2), t.setLineDash([]);
      const E = Math.min(i, s) / 2;
      t.strokeStyle = "#3f5f38";
      for (let I = 0; I < 6; I++) {
        const N = I / 6 * Math.PI * 2;
        f(Math.cos(N) * E * 0.5, Math.sin(N) * E * 0.5, E * 0.3, I % 2 ? _e(r, 0.15) : r);
      }
      break;
    }
    case "vase":
      f(0, 0, Math.min(i, s) / 2, r), f(0, 0, Math.min(i, s) * 0.2, _e(r, -0.2));
      break;
    case "wallPanel": {
      l(-o, -a, i, s, 4, r);
      const E = String(p0(e, "style", "slat"));
      if (E === "slat") for (let I = -o + 120; I < o - 60; I += 120) c(I, -a, I, a);
      else {
        const I = Math.max(1, Math.round(i / (E === "soft" ? 500 : 1200)));
        for (let N = 1; N < I; N++) c(-o + i * N / I, -a, -o + i * N / I, a);
      }
      break;
    }
    case "wallArt": {
      t.setLineDash([n * 5, n * 3]);
      const E = i > 1200 ? 3 : 1, I = (i - (E - 1) * 60) / E;
      for (let N = 0; N < E; N++) l(-o + N * (I + 60), -a, I, Math.max(s, 40), 2, r);
      t.setLineDash([]);
      break;
    }
    case "clock":
      t.setLineDash([n * 5, n * 3]), l(-o, -a, i, Math.max(s, 40), 20, r), t.setLineDash([]);
      break;
    case "rugRound": {
      t.globalAlpha = 0.85, f(0, 0, Math.min(i, s) / 2, r), t.globalAlpha = 1, t.setLineDash([n * 6, n * 4]), t.strokeStyle = _e(r, -0.3), f(0, 0, Math.min(i, s) / 2 - 150), t.setLineDash([]);
      break;
    }
    case "fan":
      f(0, 0, Math.min(i, s) / 2, r);
      for (let E = 0; E < 3; E++) {
        const I = E * 2.09;
        u(Math.cos(I) * i * 0.2, Math.sin(I) * i * 0.2, i * 0.14, i * 0.07, "#dfe3e6");
      }
      break;
    case "radiator":
      t.setLineDash([n * 4, n * 3]), l(-o, -a, i, Math.max(s, 40), 4, r), t.setLineDash([]);
      for (let E = -o + 80; E < o; E += 80) c(E, -a, E, a);
      break;
    case "lCounter": {
      t.beginPath(), t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, -a + 600), t.lineTo(-o + 600, -a + 600), t.lineTo(-o + 600, a), t.lineTo(-o, a), t.closePath(), t.fillStyle = r, t.fill(), t.stroke(), l(-o + 650, -a + 90, 700, 420, 50, "#dfe3e6");
      const I = o - 640;
      l(I - 320, -a + 70, 640, 460, 16, "#2b2e33"), t.strokeStyle = "#9aa1ab", f(I - 160, -a + 300, 95), f(I + 160, -a + 300, 95);
      break;
    }
    case "freezer":
      l(-o, -a, i, s, 20, r), c(-o + 40, -a + 40, o - 40, -a + 40);
      break;
    case "bin":
      f(0, 0, Math.min(i, s) / 2, r), f(0, 0, Math.min(i, s) * 0.3);
      break;
    case "squat":
      l(-o, -a, i, s, 30, "#eef3f6"), u(0, 30, o * 0.7, a * 0.7, r), u(0, 50, o * 0.4, a * 0.45, "#dfe9ef");
      break;
    case "pedestalSink":
      u(0, 0, o, a, r), u(0, 20, o * 0.6, a * 0.55, "#eef3f6"), f(0, -a + 60, 18);
      break;
    case "freeTub":
      u(0, 0, o, a, r), u(0, 0, o - 80, a - 80, "#e3f1f7"), f(o + 100, 0, 25);
      break;
    case "shelfRack":
      l(-o, -a, i, s, 4, r), c(-o, -a, o, a);
      break;
    case "outdoorSet":
      f(0, 0, 400, r), l(-o + 20, -250, 500, 500, 30, _e(r, 0.2)), l(o - 520, -250, 500, 500, 30, _e(r, 0.2)), t.setLineDash([n * 5, n * 3]), f(0, 0, Math.min(i, s) / 2 - 50), t.setLineDash([]);
      break;
    case "plantShelf":
      l(-o, -a, i, s, 6, r), t.strokeStyle = "#3f5f38";
      for (let E = -o + 150; E < o - 50; E += 300) f(E, 0, 90, "#6f9a5f");
      break;
    case "bike":
      l(-o, -a, i, s, 40, r), l(-60, -a + 60, 120, s - 120, 30, "#555"), c(-o + 60, a - 150, o - 60, a - 150);
      break;
    case "yogaMat":
      l(-o, -a, i, s, 30, r), f(0, -a + 40, 45, _e(r, -0.15));
      break;
    case "catTree":
      l(-o, -a, i, s, 20, r), f(-i * 0.2, -s * 0.2, 60, "#c9b28c"), f(i * 0.22, s * 0.2, 60, "#c9b28c"), l(-i * 0.4, -s * 0.3, i * 0.45, s * 0.4, 20, null);
      break;
    case "petBed":
      u(0, 0, o, a, r), u(0, 0, o * 0.7, a * 0.7, _e(r, 0.3));
      break;
    case "cabinet": {
      const E = e.cab, I = (E == null ? void 0 : E.kind) === "wall";
      if (!E) {
        l(-o, -a, i, s, 6, r);
        break;
      }
      I && t.setLineDash([n * 6, n * 4]);
      const N = JT(e);
      N ? (t.beginPath(), N.forEach((U, $) => $ ? t.lineTo(U.x, U.y) : t.moveTo(U.x, U.y)), t.closePath(), I || (t.fillStyle = r, t.fill()), t.stroke()) : l(-o, -a, i, s, 6, I ? null : r);
      for (const { run: U, cols: $, ws: H } of Dl(e)) {
        const F = U.rect, G = F.x1 - F.x0, Y = F.y1 - F.y0;
        (E.kind === "tall" || I) && (c(F.x0, F.y0, F.x1, F.y1), c(F.x1, F.y0, F.x0, F.y1));
        const V = gh($, H, U.dir === "x" ? G : Y);
        let Q = 0;
        for (let L = 0; L < V.length - 1; L++) if (Q += V[L], U.dir === "x") c(F.x0 + Q, F.y1 - Math.min(80, Y * 0.2), F.x0 + Q, F.y1);
        else {
          const j = U.front > 0 ? F.x1 : F.x0;
          c(j - U.front * Math.min(80, G * 0.2), F.y0 + Q, j, F.y0 + Q);
        }
        if (U.dir === "x") c(F.x0, F.y1 - 30, F.x1, F.y1 - 30);
        else {
          const L = U.front > 0 ? F.x1 - 30 : F.x0 + 30;
          c(L, F.y0, L, F.y1);
        }
      }
      t.setLineDash([]);
      break;
    }
    case "model": {
      const E = e.modelId ? II(e.modelId) : null;
      E ? (t.drawImage(E, -o, -a, i, s), t.strokeStyle = "rgba(75,82,93,.6)", t.strokeRect(-o, -a, i, s)) : (l(-o, -a, i, s, 10, "#eceae6"), c(-o, -a, o, a), c(o, -a, -o, a)), c(-o * 0.3, -a + 30, o * 0.3, -a + 30);
      break;
    }
    case "elevator": {
      l(-o, -a, i, s, 0, "#eef0f3"), c(-o, -a, o, a), c(o, -a, -o, a), t.lineWidth = n * 2.4, c(-o * 0.8, a - 20, o * 0.8, a - 20), t.lineWidth = n * 1.1, t.save(), t.font = `700 ${Math.min(220, i * 0.2)}px sans-serif`, t.textAlign = "center", t.textBaseline = "middle", t.fillStyle = "#2f6fed", t.fillStyle = "rgba(255,255,255,.9)", t.fillRect(-i * 0.22, -i * 0.13, i * 0.44, i * 0.26), t.fillStyle = "#2f6fed", t.fillText("\u7535\u68AF", 0, 0), t.restore();
      break;
    }
    case "stairU":
    case "stairRun":
    case "stairDogleg": {
      const { steps: E, flights: I, landings: N } = Pr(e), U = ((v = e.opt) == null ? void 0 : v.view) === "below", $ = e.z || 0, H = +(((w = e.opt) == null ? void 0 : w.cut) ?? 1500), F = (W) => {
        var te;
        return e.type === "stairRun" && !U && ((te = e.opt) == null ? void 0 : te.label) !== "\u4E0B" && $ + W.top > H;
      };
      t.lineWidth = n * 0.9;
      for (const W of [...N, ...E]) t.beginPath(), W.poly ? (W.poly.forEach((te, se) => se ? t.lineTo(te.x, te.y) : t.moveTo(te.x, te.y)), t.closePath()) : t.rect(W.x0, W.y0, W.x1 - W.x0, W.y1 - W.y0), F(W) ? (t.setLineDash([n * 6, n * 4]), t.strokeStyle = "#9aa1ab", t.stroke(), t.setLineDash([])) : (t.fillStyle = "#f3f1ec", t.fill(), t.strokeStyle = "#7d8793", t.stroke());
      const G = E.filter((W) => !F(W)), Y = e.type === "stairRun" && E.length > 0 && !G.length, V = e.type === "stairRun" && G.length && G.length < E.length ? Math.min(...G.map((W) => W.y0)) : null;
      if (t.strokeStyle = "#4b525d", t.lineWidth = n * 1.3, Y || e.type === "stairRun" && ((M = e.opt) != null && M.flat) && F({ top: e.h || 0 })) t.setLineDash([n * 6, n * 4]), t.strokeStyle = "#9aa1ab", t.strokeRect(-o, -a, i, s), t.setLineDash([]);
      else if (V === null) t.strokeRect(-o, -a, i, s);
      else {
        t.beginPath(), t.moveTo(-o, V), t.lineTo(-o, a), t.lineTo(o, a), t.lineTo(o, V), t.stroke(), t.setLineDash([n * 6, n * 4]), t.strokeStyle = "#9aa1ab", t.beginPath(), t.moveTo(-o, V), t.lineTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, V), t.stroke(), t.setLineDash([]);
        const W = Math.min(o, 400), te = Math.min(90, i * 0.06);
        t.strokeStyle = "#1f2329", t.lineWidth = n * 1.2, t.beginPath(), t.moveTo(-o, V + W), t.lineTo(-te * 1.5, V + te * 1.5 * W / o), t.lineTo(te, V + te * 2.5), t.lineTo(-te, V - te * 2.5), t.lineTo(te * 1.5, V - te * 1.5 * W / o), t.lineTo(o, V - W), t.stroke();
      }
      const Q = (e.rot || 0) * Math.PI / 180, L = Math.max(200, Math.min(260, i * 0.1)), j = (S = e.opt) == null ? void 0 : S.label, X = (W, te) => {
        if (W.length < 2) return;
        t.strokeStyle = "#1f2329", t.lineWidth = n * 1.2, t.beginPath(), W.forEach((de, Ee) => Ee ? t.lineTo(de.x, de.y) : t.moveTo(de.x, de.y)), t.stroke();
        const se = W[W.length - 2], re = W[W.length - 1], z = Math.hypot(re.x - se.x, re.y - se.y) || 1, ne = (re.x - se.x) / z, ie = (re.y - se.y) / z, le = Math.min(240, i * 0.1);
        if (t.fillStyle = "#1f2329", t.beginPath(), t.moveTo(re.x, re.y), t.lineTo(re.x - ne * le - ie * le * 0.4, re.y - ie * le + ne * le * 0.4), t.lineTo(re.x - ne * le + ie * le * 0.4, re.y - ie * le - ne * le * 0.4), t.closePath(), t.fill(), f(W[0].x, W[0].y, Math.min(60, i * 0.025), "#1f2329"), !te) return;
        const ce = W[0], be = W[1], we = Math.hypot(be.x - ce.x, be.y - ce.y) || 1, K = ce.x - (be.x - ce.x) / we * L * 1.1, q = ce.y - (be.y - ce.y) / we * L * 1.1;
        t.save(), t.translate(K, q), t.rotate(-Q), t.font = `700 ${L}px sans-serif`, t.textAlign = "center", t.textBaseline = "middle", t.fillStyle = "rgba(255,255,255,.85)", t.fillRect(-L * 0.6, -L * 0.6, L * 1.2, L * 1.2), t.fillStyle = "#2f6fed", t.fillText(te, 0, 0), t.restore();
      };
      if (e.type === "stairU") {
        const W = I[0].pts, te = { x: (W[1].x + W[2].x) / 2, y: W[1].y }, se = Math.min(+(((A = e.opt) == null ? void 0 : A.land) || 1050), s * 0.6), re = -a, z = -a + se, ne = Math.min(120, i * 0.04);
        t.strokeStyle = "#1f2329", t.lineWidth = n * 1.1, t.beginPath(), t.moveTo(te.x - ne, re), t.lineTo(te.x - ne, (re + z) / 2 - ne), t.lineTo(te.x + ne, (re + z) / 2 - ne * 0.3), t.lineTo(te.x - ne * 0.2, (re + z) / 2 + ne * 0.6), t.lineTo(te.x + ne, z), t.stroke(), X([W[0], W[1], { x: te.x + (W[1].x > W[2].x ? ne * 2 : -ne * 2), y: te.y }], "\u4E0A"), ((T = e.opt) == null ? void 0 : T.down) !== false && X([W[3], { x: W[3].x, y: W[2].y + (W[3].y > W[2].y ? 1 : -1) * 120 }], "\u4E0B");
      } else for (const W of I) {
        const te = W.pts;
        if (U) {
          const se = te[te.length - 1], re = te[0], z = Math.hypot(re.x - se.x, re.y - se.y) || 1, ne = (re.x - se.x) / z, ie = (re.y - se.y) / z;
          X([{ x: se.x + ne * L * 1.6, y: se.y + ie * L * 1.6 }, re], ""), t.save(), t.translate(se.x + ne * L * 0.7, se.y + ie * L * 0.7), t.rotate(-Q), t.font = `700 ${L}px sans-serif`, t.textAlign = "center", t.textBaseline = "middle", t.fillStyle = "rgba(255,255,255,.85)", t.fillRect(-L * 0.6, -L * 0.6, L * 1.2, L * 1.2), t.fillStyle = "#2f6fed", t.fillText("\u4E0B", 0, 0), t.restore();
        } else j === "\u4E0B" ? X([te[te.length - 1], te[0]], "\u4E0B") : Y || V !== null && V >= te[0].y - 1 || X(V !== null ? [te[0], { x: te[0].x, y: V + Math.min(250, i * 0.25) }] : te, j === "" || j === "none" ? "" : "\u4E0A");
      }
      break;
    }
    case "car": {
      l(-o, -a, i, s, Math.min(i, s) * 0.22, r), l(-o + 120, a * 0.05, i - 240, s * 0.16, 120, "#cfd8e0"), l(-o + 140, -a * 0.62, i - 280, s * 0.12, 100, "#cfd8e0"), l(-o + 160, -a * 0.45, i - 320, s * 0.5, 80, _e(r, 0.12));
      for (const E of [-1, 1]) for (const I of [-1, 1]) l(E * o - (E > 0 ? 90 : -10) - 40, I * (a - 850) - 330, 120, 660, 40, "#2b2e33");
      break;
    }
    case "evCharger":
      l(-o, -a, i, s, 20, r), t.beginPath(), t.moveTo(30, -a + 20), t.lineTo(-40, 10), t.lineTo(20, 10), t.lineTo(-30, a - 20), t.stroke();
      break;
    case "carport": {
      t.setLineDash([n * 6, n * 4]), l(-o, -a, i, s, 0, null), c(-o, -a, o, a), c(o, -a, -o, a), t.setLineDash([]);
      const E = o - 100, I = a - 200;
      for (const N of [-1, 1]) for (const U of [-1, 1]) l(N * E - 50, U * I - 50, 100, 100, 0, "#3b3f46");
      break;
    }
    case "garageShelf":
      l(-o, -a, i, s, 6, r);
      for (let E = -o + 500; E < o - 50; E += 500) c(E, -a, E, a);
      c(-o, 0, o, 0);
      break;
    case "workbench":
      l(-o, -a, i, s, 8, r), l(-o, -a, i, 40, 0, "#d9cdb8"), l(-o + 200, -a + 120, 380, 160, 10, "#c8442b");
      break;
    case "bicycle":
      f(0, -a + 330, 300), f(0, a - 330, 300), c(0, -a + 330, 0, a - 330), c(-250, a - 450, 250, a - 450);
      break;
    case "pool": {
      l(-o, -a, i, s, 60, "#e6e1d6"), l(-o + 300, -a + 300, i - 600, s - 600, 40, r), t.strokeStyle = "rgba(255,255,255,.8)";
      for (let E = -a + 700; E < a - 400; E += 700) {
        t.beginPath();
        for (let I = -o + 400; I <= o - 400; I += 100) {
          const N = E + Math.sin(I / 160) * 60;
          I === -o + 400 ? t.moveTo(I, N) : t.lineTo(I, N);
        }
        t.stroke();
      }
      t.strokeStyle = "#4b525d";
      for (let E = 0; E < 3; E++) c(-o + 320, -a + 450 + E * 250, -o + 820, -a + 450 + E * 250);
      break;
    }
    case "lawn": {
      l(-o, -a, i, s, 30, r), t.fillStyle = _e(r, -0.2);
      for (let E = -o + 150; E < o; E += 300) for (let I = -a + 150; I < a; I += 300) t.fillRect(E + I / 300 % 2 * 120, I, 30, 30);
      break;
    }
    case "stepStones": {
      const E = Math.max(2, Math.round(s / 600));
      for (let I = 0; I < E; I++) l(-o * 0.9 + (I % 2 ? 0.05 : -0.05) * i, -a + s / E * I + s / E * 0.15, i * 0.85, s / E * 0.7, 40, r);
      break;
    }
    case "tree": {
      const E = Math.min(i, s) / 2;
      t.fillStyle = r, t.globalAlpha = 0.55, t.beginPath();
      for (let I = 0; I <= 24; I++) {
        const N = I / 24 * Math.PI * 2, U = E * (I % 2 ? 0.82 : 1);
        I ? t.lineTo(Math.cos(N) * U, Math.sin(N) * U) : t.moveTo(Math.cos(N) * U, Math.sin(N) * U);
      }
      t.closePath(), t.fill(), t.globalAlpha = 1, t.stroke(), f(0, 0, E * 0.12, "#6b5442"), c(-E * 0.5, 0, E * 0.5, 0), c(0, -E * 0.5, 0, E * 0.5);
      break;
    }
    case "shrub": {
      const E = Math.min(i, s) / 2;
      t.globalAlpha = 0.7, f(0, 0, E, r), t.globalAlpha = 1, f(-E * 0.3, -E * 0.2, E * 0.35), f(E * 0.3, E * 0.15, E * 0.3);
      break;
    }
    case "gazebo": {
      l(-o, -a, i, s, 0, "#e6e1d6"), c(-o, -a, o, a), c(o, -a, -o, a);
      for (const E of [-1, 1]) for (const I of [-1, 1]) f(E * (o - 120), I * (a - 120), 80, r);
      break;
    }
    case "parasol": {
      const E = Math.min(i, s) / 2;
      t.globalAlpha = 0.5, f(0, 0, E, r), t.globalAlpha = 1;
      for (let I = 0; I < 8; I++) {
        const N = I * Math.PI / 4;
        c(0, 0, Math.cos(N) * E, Math.sin(N) * E);
      }
      f(0, 0, 450, "#e9e4dc");
      break;
    }
    case "sunLounger":
      l(-o, -a, i, s, 60, r), c(-o, -a + s * 0.35, o, -a + s * 0.35);
      for (let E = -a + s * 0.45; E < a - 50; E += 180) c(-o + 60, E, o - 60, E);
      break;
    case "swing":
      l(-o, -a, i, s, 0, null), c(-o, 0, o, 0), l(-550, -230, 1100, 460, 40, r);
      break;
    case "bbq":
      l(-o, -a, i, s, 12, r), l(-o + i * 0.15, -a + 80, i * 0.4, s - 160, 10, "#2b2e33");
      for (let E = -o + i * 0.18; E < -o + i * 0.53; E += 80) c(E, -a + 100, E, a - 100);
      l(i * 0.15, -a + 120, i * 0.25, s - 240, 30, "#e3e7ea");
      break;
    case "waterFeature":
      l(-o, -a, i, s, 10, r), l(-o + 50, -a + 250, i - 100, s - 300, 10, "#a9d8ea");
      break;
    case "fence":
      l(-o, -a, i, s, 0, r);
      for (let E = -o + 140; E < o; E += 140) c(E, -a, E, a);
      break;
    case "gate": {
      l(-o, -a, 200, s, 0, "#cfc8bb"), l(o - 200, -a, 200, s, 0, "#cfc8bb"), t.lineWidth = n * 2, c(-o + 200, 0, o - 200, 0), t.lineWidth = n * 1.1, t.setLineDash([n * 4, n * 3]), t.beginPath(), t.arc(-o + 200, 0, (i - 400) / 2, 0, Math.PI / 2), t.stroke(), t.beginPath(), t.arc(o - 200, 0, (i - 400) / 2, Math.PI / 2, Math.PI), t.stroke(), t.setLineDash([]);
      break;
    }
    case "lawnLamp":
      f(0, 0, Math.min(i, s) / 2, "#fff3d6"), c(-60, -60, 60, 60), c(60, -60, -60, 60);
      break;
    case "billiards": {
      l(-o, -a, i, s, 60, "#5a3b26"), l(-o + 120, -a + 120, i - 240, s - 240, 20, r);
      for (const E of [-1, 1]) for (const I of [-1, 0, 1]) f(E * (o - 120), I * (a - 120), 55, "#111");
      break;
    }
    case "mahjong": {
      l(-o, -a, i, s, 30, r), l(-o + 80, -a + 80, i - 160, s - 160, 20, "#2f6b45");
      for (const [E, I] of [[0, -a - 300], [0, a + 300], [-o - 300, 0], [o + 300, 0]]) l(E - 225, I - 225, 450, 450, 60, "#d6d9dd");
      break;
    }
    case "teaTable":
      l(-o, -a, i, s, 30, r), l(-i * 0.35, -a + 120, i * 0.3, s * 0.5, 10, "#2b2e33"), f(i * 0.25, -a + s * 0.45, 70, "#c7ccd2");
      for (const E of [-1, 0, 1]) l(E * i * 0.32 - 225, a + 130, 450, 450, 40, _e(r, 0.15));
      break;
    case "theaterSofa": {
      l(-o, -a, i, s, 40, r);
      const E = i / 3;
      for (let I = 1; I < 3; I++) l(-o + E * I - 70, -a, 140, s, 20, _e(r, -0.15));
      l(-o + 30, -a, i - 60, 250, 30, _e(r, -0.1));
      break;
    }
    case "grandPiano": {
      t.beginPath(), t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, s * 0.05), t.bezierCurveTo(o, s * 0.35, i * 0.1, s * 0.2, 0, a), t.bezierCurveTo(-i * 0.3, s * 0.55, -o, s * 0.4, -o, s * 0.2), t.closePath(), t.fillStyle = r, t.fill(), t.stroke(), l(-o + 50, -a - 200, i - 100, 200, 0, "#f6f6f2"), l(-o + 50, -a - 120, i - 100, 60, 0, "#2b2e33");
      break;
    }
    case "barCounter":
      l(-o, -a, i, s, 8, r), l(-o, a - 120, i, 420, 20, "#e8e3da"), l(i * 0.2 - 225, -a + 150, 450, 350, 30, "#dfe6ea");
      for (let E = 0; E < 3; E++) f(-o + 450 + E * (i - 900) / 2, a + 500, 190, "#3b3f46");
      break;
    case "sauna":
      l(-o, -a, i, s, 0, r), l(-o + 50, -a + 50, i - 100, 400, 0, _e(r, 0.15)), l(-o + 50, -a + 50, 400, s - 100, 0, _e(r, 0.15)), c(-o * 0.3, a, o * 0.5, a - 300);
      break;
    case "chandelier": {
      const E = Math.min(i, s) / 2;
      t.setLineDash([n * 3, n * 3]), f(0, 0, E), f(0, 0, E * 0.7), t.setLineDash([]), c(-E, 0, E, 0), c(0, -E, 0, E), f(0, 0, E * 0.15, "#e9e2d0");
      break;
    }
    case "riser": {
      const E = Math.min(i, s) / 2;
      f(0, 0, E, "#ffffff"), t.save(), t.beginPath(), t.arc(0, 0, E, 0, Math.PI * 2), t.clip();
      for (let I = -E; I < E; I += Math.max(15, E / 3)) c(I - E, E, I + E, -E);
      t.restore(), f(0, 0, E);
      break;
    }
    case "acOutdoor":
      l(-o, -a, i, s, 10, r), f(-i * 0.12, 0, Math.min(s * 0.4, i * 0.28));
      for (let E = 1; E < 4; E++) c(i * 0.22, -a + s * E / 4, o - 30, -a + s * E / 4);
      break;
    case "louver":
      l(-o, -a, i, s, 0, "#ffffff");
      for (let E = -o + 40; E < o; E += 80) c(E - 30, a, E + 30, -a);
      break;
    case "meterBox":
      l(-o, -a, i, s, 0, r), c(-o, -a, o, a), c(o, -a, -o, a);
      break;
    case "cornerShelf": {
      const E = ((_ = e.opt) == null ? void 0 : _.corner) !== "right";
      t.beginPath(), E ? (t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(-o, a)) : (t.moveTo(-o, -a), t.lineTo(o, -a), t.lineTo(o, a)), t.closePath(), t.fillStyle = r, t.fill(), t.stroke();
      const I = Math.max(2, +(((R = e.opt) == null ? void 0 : R.shelves) || 5));
      for (let N = 1; N < I; N++) {
        const U = N / I;
        E ? c(-o, -a + s * U, -o + i * (1 - U), -a + s * U) : c(o - i * (1 - U), -a + s * U, o, -a + s * U);
      }
      break;
    }
    case "modularSofa": {
      const E = Math.max(1, Math.round(+(((P = e.opt) == null ? void 0 : P.n) || 3))), I = i / E;
      for (let N = 0; N < E; N++) l(-o + N * I, -a, I, s, 40, r);
      l(-o, -a, i, s * 0.22, 20, _e(r, -0.12)), (D = e.opt) != null && D.ottoman && l(-I / 2, a + 120, I, I * 0.7, 40, _e(r, 0.08));
      break;
    }
    case "bayDeck":
      l(-o, -a, i, s, 0, r), c(-o, a - 40, o, a - 40);
      break;
    case "plushToy":
      f(0, s * 0.1, Math.min(i, s) * 0.38, r), f(0, -s * 0.25, Math.min(i, s) * 0.25, r);
      break;
    case "tableVase":
      f(0, 0, Math.min(i, s) / 2, r), f(0, 0, Math.min(i, s) * 0.2);
      break;
    case "bookSet": {
      const E = Math.max(3, Math.round(i / 40));
      for (let I = 0; I < E; I++) l(-o + I * i / E, -a, i / E, s, 0, I % 2 ? r : _e(r, 0.2));
      break;
    }
    case "boiler":
      l(-o, -a, i, s, 20, r), l(-i * 0.3, a - 60, i * 0.6, 40, 0, "#3bc3ff");
      break;
    case "manifold":
      l(-o, -a, i, s, 10, r);
      for (let E = -o + 80; E < o - 40; E += 100) c(E, -a, E, a);
      break;
    case "waterSoftener":
      f(-i * 0.15, 0, Math.min(i, s) * 0.3, "#2f6fed"), l(i * 0.2 - i * 0.27, -a + s * 0.1, i * 0.55, s * 0.8, 20, r);
      break;
    default:
      qL(t, e, n) || l(-o, -a, i, s, 20, r);
  }
}
;
function $I(t, e, n) {
  const i = bo(e), s = Wi(e, i), o = nx(e, i), a = e.color;
  t.lineWidth = n * 1.1, t.strokeStyle = "#4b525d", t.lineJoin = "round", t.setLineDash([]);
  const r = (b, x) => {
    t.beginPath(), b.forEach((v, w) => w ? t.lineTo(v.x, v.y) : t.moveTo(v.x, v.y)), t.closePath(), x && (t.fillStyle = x, t.fill()), t.stroke();
  }, l = (b, x, v = 0) => {
    t.beginPath(), fs(t, b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0, v), x && (t.fillStyle = x, t.fill()), t.stroke();
  };
  r(o, i.top), t.strokeStyle = _e(a, -0.35);
  for (const b of s) {
    const x = Xt(e, b, b.s0, b.s1, b.depth - 30, b.depth - 30);
    t.beginPath(), t.moveTo(x.x0, x.y0), t.lineTo(x.x1, x.y1), t.stroke();
  }
  t.strokeStyle = "#4b525d";
  const c = s[i.sink.leg] || s[0], f = i.sink.off ? 0 : i.sink.bowls === 2 ? 2 : 1, u = i.sink.w;
  for (let b = 0; b < f; b++) {
    const x = i.sink.at - u / 2 + u * b / f + 25, v = i.sink.at - u / 2 + u * (b + 1) / f - 25;
    l(Xt(e, c, x, v, 90, c.depth - 90), "#dfe3e6", 40);
    const w = Xt(e, c, (x + v) / 2, (x + v) / 2, c.depth / 2, c.depth / 2);
    t.beginPath(), t.arc(w.x0, w.y0, 22, 0, 7), t.stroke();
  }
  if (!i.sink.off) {
    const b = Xt(e, c, i.sink.at, i.sink.at, 50, 50);
    t.beginPath(), t.arc(b.x0, b.y0, 18, 0, 7), t.fillStyle = "#9aa1ab", t.fill(), t.stroke();
  }
  const h = s[i.hob.leg] || s[0], d = i.hob.w;
  i.hob.off || l(Xt(e, h, i.hob.at - d / 2, i.hob.at + d / 2, 70, h.depth - 70), "#2b2e33", 16), t.strokeStyle = "#9aa1ab";
  const p = i.hob.off ? 0 : i.hob.burners, g = p === 2 ? [[-0.25, 0.5], [0.25, 0.5]] : p === 3 ? [[-0.28, 0.62], [0.28, 0.62], [0, 0.3]] : p === 4 ? [[-0.25, 0.3], [0.25, 0.3], [-0.25, 0.7], [0.25, 0.7]] : [];
  for (const [b, x] of g) {
    const v = Xt(e, h, i.hob.at + b * d, i.hob.at + b * d, 70 + (h.depth - 140) * x, 70 + (h.depth - 140) * x);
    t.beginPath(), t.arc(v.x0, v.y0, Math.min(95, d * 0.13), 0, 7), t.stroke();
  }
  t.strokeStyle = "#4b525d";
  const m = Pm(e, i);
  m && (l(m, _e(a, -0.06)), t.beginPath(), t.moveTo(m.x0, m.y0), t.lineTo(m.x1, m.y1), t.moveTo(m.x1, m.y0), t.lineTo(m.x0, m.y1), t.stroke()), t.setLineDash([n * 6, n * 4]), t.strokeStyle = "#7d8793";
  const y = Math.max(450, d / 2 + 75);
  if (i.wall) for (let b = 0; b < s.length; b++) {
    if (i.wallLegs && !i.wallLegs.includes(b)) continue;
    const x = s[b], v = i.hood && i.hob.leg === b ? [i.hob.at - y, i.hob.at + y] : null, w = v ? [[x.s0, v[0]], [v[1], x.s1]] : [[x.s0, x.s1]];
    for (const [M, S] of w) S - M > 150 && l(Xt(e, x, M, S, 0, i.wallD), null);
  }
  if (i.hood) {
    const b = Xt(e, h, i.hob.at - y, i.hob.at + y, 0, 520);
    l(b, null), t.beginPath(), t.moveTo(b.x0, b.y0), t.lineTo(b.x1, b.y1), t.moveTo(b.x1, b.y0), t.lineTo(b.x0, b.y1), t.stroke();
  }
  t.setLineDash([]);
}
;
const ml = (t, e) => {
  t.beginPath(), e.forEach((n, i) => i ? t.lineTo(n.x, n.y) : t.moveTo(n.x, n.y)), t.closePath();
};
function v8(t, e, n, i, s, o, a) {
  const r = e.ht, l = (p, g) => Ce(e, p, g), c = (p, g, m, y, b) => {
    ml(t, [l(p, m), l(g, m), l(g, y), l(p, y)]), b && (t.fillStyle = b, t.fill()), t.stroke();
  }, f = (p, g, m) => {
    const y = l(p, m), b = l(g, m);
    t.beginPath(), t.moveTo(y.x, y.y), t.lineTo(b.x, b.y), t.stroke();
  }, u = () => {
    t.strokeStyle = "#7d8793", t.lineWidth = o, f(i, i, 0);
    const p = l(i, -r), g = l(i, r), m = l(s, -r), y = l(s, r);
    t.beginPath(), t.moveTo(p.x, p.y), t.lineTo(g.x, g.y), t.moveTo(m.x, m.y), t.lineTo(y.x, y.y), t.stroke();
  };
  t.lineWidth = o, t.strokeStyle = "#4b525d", a && (t.fillStyle = "rgba(47,111,237,.22)", ml(t, [l(i, -r - 60), l(s, -r - 60), l(s, r + 60), l(i, r + 60)]), t.fill());
  const h = (p, g, m, y, b) => {
    const x = l(p, m * r), v = l(p, m * (r + y)), w = l(g, m * r), M = Math.atan2(v.y - x.y, v.x - x.x);
    let A = Math.atan2(w.y - x.y, w.x - x.x) - M;
    for (; A > Math.PI; ) A -= 2 * Math.PI;
    for (; A < -Math.PI; ) A += 2 * Math.PI;
    t.strokeStyle = "#7d8793", t.setLineDash([o * 5, o * 3]), t.beginPath(), t.arc(x.x, x.y, y, M, M + A, A < 0), t.stroke(), t.setLineDash([]);
    const T = 20, _ = { x: -Math.sin(M) * T, y: Math.cos(M) * T };
    t.fillStyle = b ? "#5b6270" : "#ffffff", t.strokeStyle = "#4b525d", ml(t, [{ x: x.x - _.x, y: x.y - _.y }, { x: v.x - _.x, y: v.y - _.y }, { x: v.x + _.x, y: v.y + _.y }, { x: x.x + _.x, y: x.y + _.y }]), t.fill(), t.stroke();
  }, d = n.side || 1;
  switch (n.type) {
    case "window":
    case "bay":
      if (n.type === "bay") {
        const p = lr(e, n.pos), g = 380;
        c(i - 60, s + 60, p * r, p * (r + g), "#ffffff"), f(i - 60, s + 60, p * (r + g - 60)), f(i - 60, s + 60, p * (r + g - 120));
      }
      c(i, s, -r, r, "#ffffff"), t.strokeStyle = "#5c8fb8", f(i, s, -r / 3), f(i, s, r / 3);
      break;
    case "sliding": {
      c(i, s, -r, r, "#ffffff");
      const p = (i + s) / 2;
      t.strokeStyle = "#5c8fb8", c(i, p + 40, -r * 0.55, -r * 0.05, "#e8f2f9"), c(p - 40, s, r * 0.05, r * 0.55, "#e8f2f9");
      break;
    }
    case "door":
      u(), h(n.hinge ? s : i, n.hinge ? i : s, d, s - i, !!n.entry);
      break;
    case "double": {
      u();
      const p = (i + s) / 2;
      h(i, p, d, p - i, !!n.entry), h(s, p, d, s - p, !!n.entry);
      break;
    }
    case "hole":
      u(), t.setLineDash([o * 4, o * 3]), t.strokeStyle = "#7d8793", f(i, s, 0), t.setLineDash([]);
      break;
    case "unequal": {
      u();
      const p = (s - i) * Lf, g = n.hinge ? s - p : i + p;
      n.hinge ? (h(s, g, d, s - g, !!n.entry), h(i, g, d, g - i, !!n.entry)) : (h(i, g, d, g - i, !!n.entry), h(s, g, d, s - g, !!n.entry));
      break;
    }
    case "folding": {
      u();
      const p = Math.max(2, Math.round((s - i) / 420)) * 2, g = (s - i) / p, m = Math.min(260, g * 0.8), y = Array.from({ length: p + 1 }, (b, x) => l(i + g * x, d * (r + (x % 2 ? m : 0))));
      t.strokeStyle = "#4b525d", t.lineWidth = o * 2, t.beginPath(), y.forEach((b, x) => x ? t.lineTo(b.x, b.y) : t.moveTo(b.x, b.y)), t.stroke(), t.lineWidth = o;
      break;
    }
    case "pocket": {
      u();
      const p = s - i, g = !n.hinge;
      t.strokeStyle = "#4b525d", c(i + 20, s - 20, -r * 0.25, r * 0.25, "#ffffff"), t.setLineDash([o * 4, o * 3]), t.strokeStyle = "#7d8793", g ? c(i - p, i, -r * 0.3, r * 0.3, null) : c(s, s + p, -r * 0.3, r * 0.3, null), t.setLineDash([]);
      break;
    }
    case "slideWindow": {
      c(i, s, -r, r, "#ffffff");
      const p = (i + s) / 2;
      t.strokeStyle = "#5c8fb8", f(i, p + 60, -r * 0.3), f(p - 60, s, r * 0.3), f(i, s, -r * 0.7), f(i, s, r * 0.7);
      break;
    }
    case "floorWindow":
      c(i, s, -r, r, "#eef6fc"), t.strokeStyle = "#5c8fb8", f(i, s, -r / 2), f(i, s, 0), f(i, s, r / 2), t.lineWidth = o * 2, f(i, i, 0), c(i, s, -r, r, null), t.lineWidth = o;
      break;
    case "garage": {
      u();
      const p = -lr(e, n.pos), g = 300;
      t.strokeStyle = "#4b525d", c(i + 20, s - 20, -r * 0.3, r * 0.3, "#ffffff"), t.setLineDash([o * 5, o * 3]), t.strokeStyle = "#7d8793", c(i + 40, s - 40, p * r, p * (r + g), null), t.setLineDash([]);
      break;
    }
    case "glassWall": {
      const p = Math.max(1, Math.round((s - i) / 700)), g = Math.min(r, 40);
      c(i, s, -g, g, "#eef6fc"), t.strokeStyle = "#5c8fb8", f(i, s, 0);
      for (let m = 0; m <= p; m++) {
        const y = i + (s - i) * m / p;
        f(y, y, -g);
      }
      break;
    }
    case "highWindow":
      c(i, s, -r, r, "#ffffff"), t.strokeStyle = "#5c8fb8", t.setLineDash([o * 5, o * 3]), f(i, s, -r / 3), f(i, s, r / 3), t.setLineDash([]);
      break;
  }
}
;
function lr(wall) {
  if (![1, -1].includes(wall.exteriorSide)) throw new Error("Explicit exterior_side required for bay/garage");
  return wall.exteriorSide;
}
function h8() {
  throw new Error("Raster material patterns require a separate CAD hatch mapping");
}
function II() {
  throw new Error("External model images require an explicit native CAD component");
}
export {
  f3 as drawFurniture,
  v8 as drawOpening,
  v1 as furnitureCatalog,
  ki as openingCatalog,
  V1 as wallGeometry,
  Ce as wallPoint
};
