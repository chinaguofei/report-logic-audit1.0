# -*- coding: utf-8 -*-
# ⚠ 本文件是技能模板，文件内示例数据为「海目星 688559」，使用前必须整体替换配置区。
# 用途：图7/图8 行业平均 vs 公司单季净利润（一次出两张：主口径 + 工艺邻接口径）
# 用法：复制到 data/ 后改名 draw_xxx_{code}.py，改配置区常量与 OUT 文件名，再运行。
# 规格：图注必须写清「口径 + 数据源等级（A/B/C/D）」，见 references/chapter-spec.md
双图：图1=激光装备行业(大族/华工/联赢/帝尔)；图2=锂电设备行业(先导/赢合/联赢/杭可)
"""
import os, json, subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ---- 注册中文字体（微软雅黑）----
_fp = fm.FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams['font.sans-serif'] = [_fp.get_name()]
plt.rcParams['axes.unicode_minus'] = False

# 16 个季度，时间顺序（最老在左、最新在右）
QT = [('22Q3', '2022-09-30'), ('22Q4', '2022-12-31'), ('23Q1', '2023-03-31'), ('23Q2', '2023-06-30'),
      ('23Q3', '2023-09-30'), ('23Q4', '2023-12-31'), ('24Q1', '2024-03-31'), ('24Q2', '2024-06-30'),
      ('24Q3', '2024-09-30'), ('24Q4', '2024-12-31'), ('25Q1', '2025-03-31'), ('25Q2', '2025-06-30'),
      ('25Q3', '2025-09-30'), ('25Q4', '2025-12-31'), ('26Q1', '2026-03-31'), ('26Q2', '2026-06-30')]
PREV = {'-06-30': '-03-31', '-09-30': '-06-30', '-12-31': '-09-30'}


def curl_em(report, cols, code, sz=40):
    filt = "(SECUCODE%%3D%%22%s%%22)" % code
    base = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=%s&columns=%s&filter=%s"
            "&sortColumns=REPORT_DATE&sortTypes=-1&pageSize=%d&pageNumber=1&source=WEB&client=WEB"
            % (report, cols, filt, sz))
    out = subprocess.run(["curl", "-s", "--retry", "3", "--connect-timeout", "20",
                          "-H", "User-Agent: Mozilla/5.0", "-H", "Referer: https://emweb.securities.eastmoney.com/",
                          base], capture_output=True, text=True)
    try:
        return json.loads(out.stdout).get('result', {}).get('data') or []
    except Exception:
        return []


def load_mainfin(fn):
    if not os.path.exists(fn):
        return None
    d = json.load(open(fn, encoding='utf-8'))['result']['data']
    return {(r['REPORT_DATE'][:10]): r for r in d}


def single_quarter(by_rd, rd):
    c = by_rd.get(rd, {}).get('PARENTNETPROFIT')
    if c is None:
        return None
    if rd[5:] == '03-31':
        return c
    p = by_rd.get(rd[:4] + PREV[rd[4:]], {}).get('PARENTNETPROFIT')
    if p is None:
        return None
    return c - p


# 海目星（已有24季）
hmg = load_mainfin('hmg_mainfin.json')
hmg_sq = [single_quarter(hmg, ed) for _, ed in QT]


def get_sq(fn, code):
    m = load_mainfin(fn)
    if m is None or len(m) < 16:
        d = curl_em("RPT_F10_FINANCE_MAINFINADATA", "SECUCODE,REPORT_DATE,PARENTNETPROFIT", code, 40)
        json.dump({"result": {"data": d}}, open(fn, 'w'), ensure_ascii=False)
        m = {(r['REPORT_DATE'][:10]): r for r in d}
    return [single_quarter(m, ed) for _, ed in QT]


# 两组同业
laser_peers = {'大族激光': ('002008', 'peer_full_002008.json'), '华工科技': ('000988', 'peer_full_000988.json'),
               '联赢激光': ('688518', 'peer_full_688518.json'), '帝尔激光': ('300776', 'peer_full_300776.json')}
libatt_peers = {'先导智能': ('300450', 'peer_full_300450.json'), '赢合科技': ('300457', 'peer_full_300457.json'),
                '联赢激光': ('688518', 'peer_full_688518.json'), '杭可科技': ('688006', 'peer_full_688006.json')}


def peer_sq_map(peers):
    mp = {}
    for nm, (code, fn) in peers.items():
        mp[nm] = get_sq(fn, code + ('.SH' if code.startswith('688') else '.SZ'))
    return mp


def avg_series(mp):
    out = []
    for i, (_, ed) in enumerate(QT):
        vals = [mp[nm][i] for nm in mp if mp[nm][i] is not None]
        out.append(sum(vals) / len(vals) if vals else None)
    return out


laser_sq = peer_sq_map(laser_peers)
libatt_sq = peer_sq_map(libatt_peers)
laser_avg = avg_series(laser_sq)
libatt_avg = avg_series(libatt_sq)

labels = [q for q, _ in QT]
x = list(range(len(labels)))


def draw_fig(avg, title, fname, legend_ind):
    fig, ax1 = plt.subplots(figsize=(11, 5.4), dpi=150)
    l1, = ax1.plot(x, [v / 1e8 if v is not None else None for v in avg], 'o-',
                   color='#1F4E79', lw=2.4, ms=5, label=legend_ind)
    ax1.axhline(0, color='#999', lw=0.9, ls='--')
    ax1.set_ylabel('行业平均单季归母净利润(亿元)', fontsize=10.5, color='#1F4E79')
    ax1.tick_params(axis='y', labelcolor='#1F4E79')
    ia = [v / 1e8 for v in avg if v is not None]
    ax1.set_ylim(min(ia) * 1.3, max(ia) * 1.2)

    ax2 = ax1.twinx()
    l2, = ax2.plot(x, [v / 1e8 if v is not None else None for v in hmg_sq], 's-',
                   color='#C0392B', lw=2.4, ms=5, label='海目星单季净利润')
    ax2.axhline(0, color='#999', lw=0.9, ls='--')
    ax2.set_ylabel('海目星单季归母净利润(亿元)', fontsize=10.5, color='#C0392B')
    ax2.tick_params(axis='y', labelcolor='#C0392B')
    hmg_abs = [abs(v / 1e8) for v in hmg_sq if v is not None]
    ax2.set_ylim(-max(hmg_abs) * 1.7, max(hmg_abs) * 1.7)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha='right', fontsize=8.5)
    ax1.set_title(title, fontsize=12, fontweight='bold')
    ax1.grid(alpha=0.25)

    # 标注海目星扭亏点(25Q4 起)
    for i, v in enumerate(hmg_sq):
        if v is not None and v > 0 and (i == 0 or hmg_sq[i - 1] is None or hmg_sq[i - 1] <= 0):
            ax2.annotate('25Q4扭亏', xy=(i, v / 1e8), xytext=(i - 1, v / 1e8 + max(hmg_abs) * 0.5),
                         fontsize=8.5, color='#C0392B',
                         arrowprops=dict(arrowstyle='->', color='#C0392B', lw=1))

    ax1.legend(handles=[l1, l2], loc='upper left', fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(fname, dpi=150)
    print('SAVED', fname)


draw_fig(laser_avg, '激光装备行业平均 vs 海目星 单季净利润对比（近16个季度）',
         'ind_vs_hmg_npcmp.png', '激光装备行业平均单季净利润(大族/华工/联赢/帝尔均值)')
draw_fig(libatt_avg, '锂电设备行业平均 vs 海目星 单季净利润对比（近16个季度）',
         'ind_vs_hmg_npcmp_libatt.png', '锂电设备行业平均单季净利润(先导/赢合/联赢/杭可均值)')

print('hmg_sq(亿):', [round(v / 1e8, 2) if v is not None else None for v in hmg_sq])
print('laser_avg(亿):', [round(v / 1e8, 2) if v is not None else None for v in laser_avg])
print('libatt_avg(亿):', [round(v / 1e8, 2) if v is not None else None for v in libatt_avg])
