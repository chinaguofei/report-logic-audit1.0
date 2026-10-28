# -*- coding: utf-8 -*-
"""指标切换图 HTML 页生成器 —— 用户 2026-09-10 提供的定稿模版（皖仪科技688600 样式）；
2026-09-12 用户要求新增第 5 行「股东变化率」（季末股东户数环比，红=增加/分散，绿=减少/集中）。

页面结构（勿改）：
  标题（公司简称（代码））→ 蓝头矩阵表（5 指标行 × N 季，红涨绿跌）→
  「指标」tab 组（激活蓝底白字，默认「营收同比」）→ 蓝色单线折线图（白圈圆点、浅灰网格）

用法：复制本文件为 data/build_matrix_page_{code}.py，只改「配置区」常量后运行。
输出：~/Desktop/WB/{公司简称}{代码}_指标切换图.html
"""
import json
import os

# ============ 配置区（只改这里） ============
TITLE = "皖仪科技（688600）"
OUT = os.path.join(os.path.expanduser("~"), "Desktop", "WB", "皖仪科技688600_指标切换图.html")
SOURCE_NOTE = "数据来源：公司定期报告（东方财富 F10 整理）· 单季度口径"
# 季度，最新在左（与研报矩阵表列序一致）
QUARTERS = ["26Q2", "26Q1", "25Q4", "25Q3", "25Q2", "25Q1", "24Q4", "24Q3",
            "24Q2", "24Q1", "23Q4", "23Q3", "23Q2", "23Q1", "22Q4", "22Q3"]
# 固定 5 行，顺序勿改；数值顺序与 QUARTERS 对应；无数据填 None
ROWS = [
    # (指标名, 数值列表)
    ("毛利率",   [51.68, 49.03, 51.30, 47.98, 49.73, 50.04, 46.84, 46.97,
                  45.77, 46.07, 48.30, 46.17, 48.63, 51.48, 44.22, 48.88]),
    ("营收同比", [21.61, 33.46, -33.62, 32.59, -4.47, 16.87, 1.00, -18.29,
                  3.50, -14.77, 21.18, 12.30, 13.40, 17.57, 7.37, 13.96]),
    ("扣非同比", [124.46, 173.57, -41.26, 682.01, 63.38, 77.31, 140.30, -147.34,
                  -52.17, -2866.52, -23.47, 5.34, 640.79, 91.60, -24.98, 587.50]),
    ("扣非TTM",  [0.53, 0.47, 0.32, 0.47, 0.30, 0.28, -0.02, -0.24,
                  -0.16, -0.13, 0.25, 0.30, 0.29, 0.25, 0.10, None]),
    # 股东变化率 = 季末股东户数环比（%）：红 = 增加/筹码分散，绿 = 减少/筹码集中；
    # 上市前季度或未披露填 None（此处为示例占位，实际使用时从矩阵 JSON 的 h_ratio 读取）
    ("股东变化率", [None] * 16),
]
# ==========================================

FMT_BY_NAME = {"毛利率": "pct1", "扣非TTM": "yi"}   # 其余默认 pct2


def build_html():
    rows_js = [{"name": n, "fmt": FMT_BY_NAME.get(n, "pct2"), "vals": v}
               for n, v in ROWS]
    default_sel = next((i for i, r in enumerate(rows_js)
                        if r["name"] == "营收同比"), 0)
    html = TEMPLATE
    html = html.replace("%%TITLE%%", TITLE)
    html = html.replace("%%QUARTERS%%", json.dumps(QUARTERS, ensure_ascii=False))
    html = html.replace("%%ROWS%%", json.dumps(rows_js, ensure_ascii=False))
    html = html.replace("%%DEFAULT_SEL%%", str(default_sel))
    html = html.replace("%%SOURCE%%", SOURCE_NOTE)
    return html


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%%TITLE%%</title>
<style>
  :root {
    --blue: #1E6FFF; --red: #E64545; --green: #00A65A;
    --ink: #1D2129; --gray: #86909C; --line: #E5E6EB;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    background: #FFFFFF; color: var(--ink); padding: 30px 26px 46px;
  }
  .wrap { max-width: 1080px; margin: 0 auto; }
  h1 { text-align: center; font-size: 24px; letter-spacing: 1px; }
  .tbl-scroll { overflow-x: auto; margin-top: 22px; }
  table.matrix { border-collapse: collapse; width: 100%; min-width: 920px; }
  table.matrix th, table.matrix td {
    border: 1px solid var(--line); text-align: center;
    font-size: 13px; padding: 8px 5px; white-space: nowrap;
  }
  table.matrix thead th { background: var(--blue); color: #fff; font-weight: bold; padding: 9px 5px; }
  table.matrix th.rowname { font-weight: normal; color: var(--ink); cursor: pointer; min-width: 84px; }
  table.matrix tbody tr { cursor: pointer; transition: background .12s; }
  table.matrix tbody tr:hover { background: #F5F8FF; }
  table.matrix tbody tr.sel { background: #F0F6FF; }
  td.pos { color: var(--red); }
  td.neg { color: var(--green); }
  td.plain { color: var(--ink); }
  td.na { color: var(--gray); }
  .sec-label { font-size: 17px; font-weight: bold; margin: 34px 0 14px; }
  .tabs { display: flex; gap: 12px; flex-wrap: wrap; }
  .tab {
    min-width: 96px; text-align: center; padding: 9px 18px;
    font-size: 14px; border-radius: 6px; cursor: pointer; user-select: none;
    background: #F5F6F7; border: 1px solid var(--line); color: var(--ink);
    transition: all .15s;
  }
  .tab:hover { border-color: var(--blue); color: var(--blue); }
  .tab.on { background: var(--blue); border-color: var(--blue); color: #fff; font-weight: bold; }
  #chart-wrap { position: relative; margin-top: 46px; }
  #chart svg { width: 100%; height: auto; display: block; }
  .fade { animation: fadein .3s ease; }
  @keyframes fadein { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  #tip {
    position: absolute; pointer-events: none; display: none;
    background: rgba(29,33,41,.94); color: #fff; font-size: 12.5px;
    padding: 5px 10px; border-radius: 6px; white-space: nowrap; z-index: 9;
  }
  footer { margin-top: 40px; font-size: 12px; color: var(--gray); line-height: 1.8; }
</style>
</head>
<body>
<div class="wrap">
  <h1>%%TITLE%%</h1>
  <div class="tbl-scroll"><table class="matrix" id="mtx"></table></div>
  <div class="sec-label">指标</div>
  <div class="tabs" id="tabs"></div>
  <div id="chart-wrap"><div id="chart"></div><div id="tip"></div></div>
  <footer>%%SOURCE%%。扣非TTM 为滚动四个季度扣非合计；股东变化率为季末股东户数环比（红=增加/筹码分散，绿=减少/筹码集中）；"--" 表示该期无数据。表格红涨绿跌。</footer>
</div>
<script>
"use strict";
const Q_DESC = %%QUARTERS%%;
const Q_ASC  = [...Q_DESC].reverse();
const ROWS = %%ROWS%%;
let sel = %%DEFAULT_SEL%%;

function fmtVal(v, r) {
  if (v === null || v === undefined) return "--";
  if (r.fmt === "pct1") return v.toFixed(2) + "%";
  if (r.fmt === "yi")   return v.toFixed(2) + "亿";
  return v.toFixed(2) + "%";
}
function cls(v, r) {
  if (v === null || v === undefined) return "na";
  if (r.fmt === "pct1") return "plain";
  return v >= 0 ? "pos" : "neg";
}
const mtx = document.getElementById("mtx");
function renderTable() {
  let h = "<thead><tr><th>指标</th>";
  for (const q of Q_DESC) h += "<th>" + q + "</th>";
  h += "</tr></thead><tbody>";
  ROWS.forEach((r, ri) => {
    h += '<tr data-i="' + ri + '" ' + (ri === sel ? "class='sel'" : "") + ">";
    h += '<th class="rowname">' + r.name + "</th>";
    for (const v of r.vals) h += '<td class="' + cls(v, r) + '">' + fmtVal(v, r) + "</td>";
    h += "</tr>";
  });
  h += "</tbody>";
  mtx.innerHTML = h;
  mtx.querySelectorAll("tbody tr").forEach(tr =>
    tr.addEventListener("click", () => select(+tr.dataset.i)));
}
const tabsEl = document.getElementById("tabs");
function renderTabs() {
  tabsEl.innerHTML = ROWS.map((r, i) =>
    '<div class="tab ' + (i === sel ? "on" : "") + '" data-i="' + i + '">' + r.name + "</div>").join("");
  tabsEl.querySelectorAll(".tab").forEach(t =>
    t.addEventListener("click", () => select(+t.dataset.i)));
}
function select(i) {
  sel = i; renderTabs();
  mtx.querySelectorAll("tbody tr").forEach(tr =>
    tr.classList.toggle("sel", +tr.dataset.i === i));
  renderChart();
}
const chart = document.getElementById("chart");
const tip = document.getElementById("tip");
const wrapBox = document.getElementById("chart-wrap");
const BLUE = "#1E6FFF", GRID = "#E5E6EB", ZERO = "#C9CDD4", GRAY = "#86909C";
const W = 1080, H = 470, ML = 74, MR = 30, MT = 24, MB = 40;
const PW = W - ML - MR, PH = H - MT - MB;
const n = Q_ASC.length;
const X = i => ML + (PW * i) / (n - 1);
function niceStep(span, target) {
  const raw = span / target, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * mag) return m * mag;
  return 10 * mag;
}
function yLabel(v, r) {
  if (r.fmt === "yi") return v.toFixed(1) + "亿";
  return (Number.isInteger(v) ? v : v.toFixed(1)) + "%";
}
function renderChart() {
  const r = ROWS[sel];
  const pts = Q_ASC.map((q, i) => ({ q: q, v: r.vals[Q_DESC.indexOf(q)] }))
                   .filter(p => p.v !== null && p.v !== undefined);
  let lo = Math.min.apply(null, pts.map(p => p.v)), hi = Math.max.apply(null, pts.map(p => p.v));
  const pad = (hi - lo) * 0.12 || 1; lo -= pad; hi += pad;
  const step = niceStep(hi - lo, 8);
  const t0 = Math.floor(lo / step) * step, t1 = Math.ceil(hi / step) * step;
  const ticks = []; for (let v = t0; v <= t1 + 1e-9; v += step) ticks.push(+v.toFixed(6));
  const Y = v => MT + PH * (1 - (v - t0) / (t1 - t0));
  let s = '<svg viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg" class="fade">';
  ticks.forEach(t => {
    const isZero = Math.abs(t) < 1e-9;
    s += '<line x1="' + ML + '" y1="' + Y(t) + '" x2="' + (ML+PW) + '" y2="' + Y(t) +
         '" stroke="' + (isZero ? ZERO : GRID) + '" stroke-width="1"/>';
    s += '<text x="' + (ML-10) + '" y="' + (Y(t)+4) + '" text-anchor="end" font-size="12.5" fill="' + GRAY + '">' + yLabel(t, r) + "</text>";
  });
  Q_ASC.forEach((q, i) =>
    s += '<text x="' + X(i) + '" y="' + (MT+PH+26) + '" text-anchor="middle" font-size="12.5" fill="' + GRAY + '">' + q + "</text>");
  let d = "", pen = false;
  Q_ASC.forEach((q, i) => {
    const v = r.vals[Q_DESC.indexOf(q)];
    if (v === null || v === undefined) { pen = false; return; }
    d += (pen ? " L" : " M") + " " + X(i) + " " + Y(v);
    pen = true;
  });
  s += '<path d="' + d + '" fill="none" stroke="' + BLUE + '" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>';
  pts.forEach(p => {
    const cx = X(Q_ASC.indexOf(p.q));
    s += '<circle class="pt" data-q="' + p.q + '" cx="' + cx + '" cy="' + Y(p.v) + '" r="4.6" fill="' + BLUE + '" stroke="#fff" stroke-width="2"/>';
  });
  s += "</svg>";
  chart.innerHTML = s;
  tip.style.display = "none";
  chart.querySelectorAll(".pt").forEach(el => {
    el.addEventListener("mouseenter", ev => {
      const q = el.dataset.q;
      const v = r.vals[Q_DESC.indexOf(q)];
      tip.textContent = q + "：" + fmtVal(v, r);
      const b = wrapBox.getBoundingClientRect();
      tip.style.display = "block";
      tip.style.left = (ev.clientX - b.left + 14) + "px";
      tip.style.top  = (ev.clientY - b.top  - 32) + "px";
    });
    el.addEventListener("mouseleave", () => tip.style.display = "none");
  });
}
renderTable();
renderTabs();
renderChart();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    assert len(ROWS) == 5, "模版固定 5 个指标行，不得增删（2026-09-12 起含股东变化率）"
    assert all(len(v) == len(QUARTERS) for _, v in ROWS), "数值个数须与季度数一致"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_html())
    print("saved:", OUT)
    print("指标行:", [n for n, _ in ROWS], "| 季度:", QUARTERS[0], "→", QUARTERS[-1], f"({len(QUARTERS)}季)")
    print(">>> 提醒：数值顺序必须与 QUARTERS（最新在左）一一对应；无数据填 None <<<")
