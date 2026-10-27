"""校对表导出 / 导入

  python proofread.py export   生成 校对表.xlsx（覆盖前会备份旧表）
  python proofread.py import   读取 校对表.xlsx 中“修改后译文”非空的行 → batches/b_proofread_日期.py → 并入 zh.json
"""
import datetime, glob, json, os, re, shutil, sys
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, '..', 'Game Files', 'assets')
XLSX = os.path.join(HERE, '校对表.xlsx')
EN = json.load(open(os.path.join(HERE, 'en.json'), encoding='utf-8'))
ZH = json.load(open(os.path.join(HERE, 'zh.json'), encoding='utf-8'))

# 分类：按游戏中出现的大致顺序
CATS = [
    ('界面', None),
    ('帮助页', ('lblHelp',)),
    ('教程', ('tutorial',)),
    ('剧情漫画', ('FLASH_',)),
    ('集标题', ('summary_title',)),
    ('关卡开场', ('summary_text',)),
    ('过关台词', ('win_text',)),
    ('失败台词', ('lose_text',)),
    ('小贴士', ('tip_message',)),
    ('场景提示', ('event_',)),
    ('评委要求', ('judge_',)),
    ('小游戏', ('minigame_',)),
    ('商店升级', ('furniture', 'item_', 'rosie_upgrade', 'hungryman', 'writer_', 'auntethel', 'helper_', 'cleaner_')),
    ('装饰升级', ('decorative', 'decupgrade')),
    ('百宝库', ('bonuslevel', 'specialfeature', 'txtBonusStore')),
    ('成就', ('lblThropies',)),
    ('选角与大结局', ('lblCasting', 'lblEndGame', 'lblClimax', 'gift_')),
]
SKIP = {'exit_survey_url'}

GLOSSARY = [
    ('Soap Opera Dash', '美女肥皂剧', '游戏名，呼应《美女餐厅》'), ('As The Burger Turns', '《汉堡风云》', '剧中剧'),
    ('Rosie', '罗希', ''), ('Simon', '西蒙', ''), ('Hal', '哈尔', '摄像师（hungryman）'), ('Flo', '弗洛', ''),
    ('Quinn', '奎因', ''), ('Grandma Florence', '弗洛伦斯奶奶', ''), ('Karma', '卡玛', ''), ('Jo Jogger', '慢跑达人乔', ''),
    ('Barb', '芭布', ''), ('Seymour Senior', '老西摩', ''), ('Colin', '科林', ''), ('Bernie', '伯尼', '编剧'),
    ('Aunt Ethel', '埃塞尔姑妈', '导演'), ('Cookie', '曲奇', '大厨助手'), ('Jerry', '杰瑞', '清洁工'),
    ('Tony', '托尼', '餐厅小镇制片厂高层'), ('Joe', '乔伊', '摄影师，与演员“乔”区分'), ('Rhoda / Roberta', '罗达 / 罗伯塔', '西蒙叫错罗希的名字'),
    ('Rosebud', '小玫瑰', '昵称'), ('Poopsie', '小甜豆', '昵称'),
    ('DinerTown', '餐厅小镇', ''), ('DinerWood', '餐莱坞', '戏仿 Hollywood'), ('DinerTube', '餐管网', '戏仿 YouTube（油管）'),
    ('Thyme Square', '百里香广场', '戏仿 Times Square'), ('Treasure Trove', '百宝库', ''), ('Dinie award', '餐美奖', '戏仿 Emmy 艾美奖'),
    ('Season Finale', '本季大结局', '窄处写“大结局”'), ('Episode / Bonus Episode', '集 / 奖励集', ''),
    ('Hospital Blues', '《医院蓝调》', ''), ("Let's Bake a Cake", '《一起烤蛋糕》', ''), ('Old People Are People, Too', '《老人也是人》', ''),
    ('Soap Opera Monthly', '《肥皂剧月刊》', ''), ('Intern / Producer', '实习生 / 制片人', '难度'),
    ('Expert', '专家分', ''), ('Chain (Combo)', '连锁', ''), ('Color Match', '颜色配对', ''),
]


def category(key):
    for name, prefixes in CATS[1:]:
        if key.startswith(prefixes):
            return name
    return '界面'


def box_sizes():
    """从 lua 布局和漫画 xml 中提取每个 label 的文字框宽度（和字号）"""
    sizes = {}
    for f in glob.glob(os.path.join(ASSETS, 'scripts', '*.lua')):
        src = open(f, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'label\s*=\s*"(\w+)"', src):
            # 截到下一个控件定义为止（font = {...} 可能写在 label 之后）
            rest = src[m.end():m.end() + 600]
            nxt = re.search(r'label\s*=|\b(Text|Bitmap|swt\w+|Button)\s*\{', rest)
            block = rest[:nxt.start()] if nxt else rest
            w = re.search(r'\bw\s*=\s*(\d+)', block)
            if w:
                sizes.setdefault(m.group(1), f'框宽 {w.group(1)}')
    for f in glob.glob(os.path.join(ASSETS, 'comic', '*.xml')):
        for m in re.finditer(r'<text[^>]*w="(\d+)" h="(\d+)"[^>]*text="#(\w+)#"', open(f, encoding='utf-8').read()):
            sizes[m.group(3)] = f'气泡 {m.group(1)}×{m.group(2)}（约每行 {int(m.group(1)) // 12} 字）'
    return sizes


def export():
    keep = {}   # 沿用旧表的“状态”“备注”，校对进度不丢
    if os.path.exists(XLSX):
        ws0 = load_workbook(XLSX)['校对']
        h0 = [c.value for c in ws0[1]]
        for row in ws0.iter_rows(min_row=2, values_only=True):
            keep[row[h0.index('Key')]] = (row[h0.index('状态')], row[h0.index('备注')])
        bak = XLSX.replace('.xlsx', datetime.datetime.now().strftime('_%Y%m%d_%H%M%S.xlsx'))
        shutil.copy(XLSX, bak)
        print('旧表已备份为', os.path.basename(bak))
    sizes = box_sizes()
    order = {name: i for i, (name, _) in enumerate(CATS)}
    keys = [k for k in EN if k not in SKIP and k in ZH]
    keys.sort(key=lambda k: order[category(k)])  # 稳定排序：同类内保持原文件顺序

    F = '微软雅黑'
    font, bold = Font(name=F, size=10), Font(name=F, size=10, bold=True, color='FFFFFF')
    head_fill = PatternFill('solid', fgColor='5B4A8B')
    input_fill = PatternFill('solid', fgColor='FFF2CC')
    thin = Side(style='thin', color='D9D9D9'); border = Border(bottom=thin)
    wrap = Alignment(wrap_text=True, vertical='top')

    wb = Workbook()
    ws = wb.active; ws.title = '校对'
    heads = ['序号', '分类', 'Key', '原文', '当前译文', '修改后译文', '状态', '备注', '显示空间']
    widths = [6, 10, 26, 48, 42, 42, 8, 24, 18]
    for c, (h, w) in enumerate(zip(heads, widths), 1):
        cell = ws.cell(1, c, h); cell.font = bold; cell.fill = head_fill
        cell.alignment = Alignment(vertical='center', horizontal='center')
        ws.column_dimensions[cell.column_letter].width = w
    for r, k in enumerate(keys, 2):
        en = EN[k] if not re.search(r'[一-鿿]', EN[k]) else '（英文原文已丢失）'
        st, note = keep.get(k, (None, None))
        row = [r - 1, category(k), k, en, ZH[k], None, st, note, sizes.get(k, '')]
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v); cell.font = font; cell.alignment = wrap; cell.border = border
            if c in (6, 7, 8):
                cell.fill = input_fill
    ws.freeze_panes = 'F2'
    ws.auto_filter.ref = f'A1:I{len(keys) + 1}'
    dv = DataValidation(type='list', formula1='"已校,有疑问,需改"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(f'G2:G{len(keys) + 1}')

    # 译名表
    g = wb.create_sheet('译名表')
    for c, (h, w) in enumerate(zip(['英文', '译名', '说明'], [28, 20, 36]), 1):
        cell = g.cell(1, c, h); cell.font = bold; cell.fill = head_fill
        g.column_dimensions[cell.column_letter].width = w
    for r, row in enumerate(GLOSSARY, 2):
        for c, v in enumerate(row, 1):
            g.cell(r, c, v).font = font
    g.freeze_panes = 'A2'

    # 说明
    s = wb.create_sheet('说明', 0)
    s.column_dimensions['A'].width = 16; s.column_dimensions['B'].width = 80
    n = len(keys) + 1
    rows = [
        ('美女肥皂剧 汉化校对表', None),
        (None, None),
        ('怎么填', '只在「校对」页的黄色三列里填写：'),
        ('修改后译文', '想改哪条，就把新译文写在这一列；不改的留空。换行直接在单元格里按 Alt+Enter。'),
        ('状态', '下拉选择：已校 / 有疑问 / 需改（可选，方便自己筛选进度）'),
        ('备注', '写给我的说明，例如“这句在游戏里溢出了”“语气太生硬”'),
        ('示例', '原文 “Hurry! Unhappy actors decrease your ratings!” 当前译文 “快点！演员不开心会拉低收视率！”'),
        ('', '→ 修改后译文填 “快！演员不高兴，收视率就会掉！”，状态选“已校”'),
        (None, None),
        ('注意', '<br>、%1%、$i、$c、$s 是游戏里的换行/数字占位符，修改时要原样保留。'),
        ('', '「显示空间」列是文字框宽度（像素），漫画气泡约每行可放的字数仅供参考。'),
        ('', '中文字之间不用加空格，换行由工具自动处理。'),
        (None, None),
        ('进度', None),
        ('总条数', f'=COUNTA(校对!C2:C{n})'),
        ('已填修改', f'=COUNTA(校对!F2:F{n})'),
        ('标为已校', f'=COUNTIF(校对!G2:G{n},"已校")'),
        ('有疑问/需改', f'=COUNTIF(校对!G2:G{n},"有疑问")+COUNTIF(校对!G2:G{n},"需改")'),
    ]
    for r, (a, b) in enumerate(rows, 1):
        ca, cb = s.cell(r, 1, a), s.cell(r, 2, b)
        ca.font = Font(name=F, size=10, bold=True); cb.font = font
        cb.alignment = Alignment(wrap_text=True, vertical='top', horizontal='left')
    s['A1'].font = Font(name=F, size=14, bold=True, color='5B4A8B')
    wb.calculation.fullCalcOnLoad = True  # 说明页的统计公式在 Excel 打开时计算
    wb.save(XLSX)
    print(f'已生成 {os.path.basename(XLSX)}：{len(keys)} 条')


def do_import():
    wb = load_workbook(XLSX)
    ws = wb['校对']
    head = [c.value for c in ws[1]]
    ik, inew = head.index('Key'), head.index('修改后译文')
    T = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[inew] not in (None, ''):
            T[row[ik]] = str(row[inew]).replace('\r\n', '\n').strip()
    if not T:
        print('没有填写修改后译文的行'); return
    path = os.path.join(HERE, 'batches', datetime.datetime.now().strftime('b_proofread_%Y%m%d_%H%M.py'))
    open(path, 'w', encoding='utf-8').write('# 校对表导入\nT = ' + json.dumps(T, ensure_ascii=False, indent=1) + '\n')
    print(f'读取到 {len(T)} 条修改 → {os.path.relpath(path, HERE)}')
    sys.path.insert(0, HERE)
    import strings_tool
    strings_tool.merge(path)


if __name__ == '__main__':
    {'export': export, 'import': do_import}[sys.argv[1]]()
