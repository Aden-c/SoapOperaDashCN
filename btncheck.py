"""按钮字体（ButtonFontNN）下各文字宽度 vs 按钮宽度，比较不同放大倍数
   python btncheck.py 字体1.mvec[=名称] 字体2.mvec[=名称] ..."""
import glob, json, os, re, sys
from fitcheck import load
from strings_tool import add_breaks

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'Game Files', 'assets', 'scripts')
zh = json.load(open(os.path.join(HERE, 'zh.json'), encoding='utf-8'))
style = open(os.path.join(SCRIPTS, 'style.lua'), encoding='utf-8').read()
# ButtonFontNN 的字号；以及样式表（SetStyle 用）里指定的字体
sizes = {m.group(1): int(m.group(2)) for m in re.finditer(r'(ButtonFont\d+)\s*=\s*\{\s*ButtonFont;\s*(\d+)', style)}
styfont = {m.group(1): m.group(2) for m in re.finditer(r'(\w+)\s*=\s*\{[^{}]*?font\s*=\s*(ButtonFont\d+)', style, re.S)}

fonts = {}
for arg in sys.argv[1:]:
    path, _, name = arg.partition('=')
    fonts[name or os.path.basename(path)] = load(path)

def width(font, text, size):
    recs = font[0]
    s = size * 1.2 / (-recs[ord('H')][3] * 1.666)
    lines = add_breaks(text).replace('<br>', '\n').split('\n')
    return max(sum(recs.get(ord(c), recs[ord('H')])[5] for c in ln.replace(' ', '')) * s for ln in lines)

rows = []
for f in glob.glob(os.path.join(SCRIPTS, '*.lua')):
    src = open(f, encoding='utf-8', errors='replace').read()
    cur = None
    for m in re.finditer(r'SetStyle\((\w+)\)|label\s*=\s*"(\w+)"', src):
        if m.group(1):
            cur = m.group(1); continue
        key = m.group(2)
        if key not in zh:
            continue
        rest = src[m.end():m.end() + 700]
        nxt = re.search(r'label\s*=|\b(Text|Bitmap|swt\w+|Button)\s*\{', rest)
        blk = rest[:nxt.start()] if nxt else rest
        head = src[max(0, m.start() - 300):m.start()].split('{')[-1]   # label 之前、同一控件内
        fm = re.search(r'font\s*=\s*(ButtonFont\d+)', blk) or re.search(r'font\s*=\s*(ButtonFont\d+)', head)
        fname = fm.group(1) if fm else styfont.get(cur)
        wm = re.search(r'\bw\s*=\s*(\d+)', blk) or re.search(r'\bw\s*=\s*(\d+)', head)
        if fname not in sizes or not wm:
            continue
        w = int(wm.group(1))
        rows.append((key, os.path.basename(f), fname, w, zh[key],
                     {n: round(width(fo, zh[key], sizes[fname])) for n, fo in fonts.items()}))

last = list(fonts)[-1]
rows.sort(key=lambda r: -r[5][last] / r[3])
print(f"{'key':30s}{'字体':14s}{'按钮宽':>6s}  " + ' '.join(f'{n:>6s}' for n in fonts) + '  文字')
for key, f, fn, w, t, ws in rows[:25]:
    flag = '⚠' if ws[last] > w - 8 else ' '
    print(f"{flag}{key:29s}{fn:14s}{w:6d}  " + ' '.join(f'{ws[n]:6d}' for n in fonts) + f'  {t!r}')
print('共检查', len(rows), '个使用按钮字体的文字')
