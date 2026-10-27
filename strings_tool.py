"""strings.xml 翻译工具

  python strings_tool.py export   从 hanhua/backup/strings.xml（英文原版）导出 en.json
  python strings_tool.py apply    把 zh.json 的译文写入游戏的 assets/strings.xml（以英文原版为底）

JSON 里是纯文本：换行写 \n（对应 &#10;），<br> 照写，脚本负责 XML 转义。
zh.json 里没有的 key 保持英文。
"""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'backup', 'strings.xml')
DST = os.path.join(HERE, '..', 'Game Files', 'assets', 'strings.xml')
EN = os.path.join(HERE, 'en.json')
ZH = os.path.join(HERE, 'zh.json')

ROW = re.compile(r'<Row\b.*?</Row>', re.S)
DATA = re.compile(r'(<Data\b[^>]*>)(.*?)(</Data>)', re.S)


def unesc(s):
    return html.unescape(s)


def esc(s):
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return s.replace('\r\n', '\n').replace('\n', '&#10;')


# ---- 中文折行点 ----
# 引擎对无空格的中文会多塞一个字才折行，但按空格折行是准的。
# 字体里空格做成了零宽（mkmvec --zero-space），这里在字间插入空格作为折行点，
# 原文中真正的空格换成 U+00A0（可见、不折行）。
NO_BREAK_BEFORE = set('，。！？、；：）》」』〕】”’…—～·%,.!?;:)]}>')
NO_BREAK_AFTER = set('（《「『〔【“‘([{<')
TOKEN = re.compile(r'<br>|</?i>|%\d+%|\n|[A-Za-z0-9_\'\-+.,!?:;/&$#@*=()\[\]"]+|.', re.S)
CJK = re.compile(r'[⺀-鿿豈-﫿＀-￯　-〿‐-⁯]')


RAW_KEYS = {'window_title', 'exit_survey_url'}  # 不经过 mvec 字体渲染的，原样写入


def add_breaks(s):
    if not CJK.search(s):
        return s.replace(' ', ' ')  # 纯英文：空格保持可见
    toks = TOKEN.findall(s.replace(' ', ' '))
    out = []
    for i, t in enumerate(toks):
        if i:
            a, b = toks[i - 1], t
            hard = {'\n', '<br>', ' '}
            if not (a in hard or b in hard
                    or b[0] in NO_BREAK_BEFORE or a[-1] in NO_BREAK_AFTER
                    or (a.startswith('<') and a.endswith('>') and a != '<br>')):
                out.append(' ')
        out.append(t)
    return ''.join(out)


def rows(text):
    for m in ROW.finditer(text):
        cells = list(DATA.finditer(m.group(0)))
        if len(cells) >= 2:
            yield m, cells


def export():
    text = open(SRC, encoding='utf-8', newline='').read()
    en = {unesc(c[0].group(2)): unesc(c[1].group(2)) for _, c in rows(text)}
    json.dump(en, open(EN, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(en)} 条 -> {EN}')


def apply():
    text = open(SRC, encoding='utf-8', newline='').read()
    zh = json.load(open(ZH, encoding='utf-8'))
    out, last, n, seen = [], 0, 0, set()
    for m, cells in rows(text):
        key = unesc(cells[0].group(2))
        if key not in zh:
            continue
        seen.add(key)
        c = cells[1]
        a, b = m.start() + c.start(2), m.start() + c.end(2)
        out.append(text[last:a]); out.append(esc(zh[key] if key in RAW_KEYS else add_breaks(zh[key]))); last = b; n += 1
    out.append(text[last:])
    open(DST, 'w', encoding='utf-8', newline='').write(''.join(out))
    unknown = set(zh) - seen
    print(f'写入 {n} 条译文 -> {DST}')
    if unknown:
        print('zh.json 中有未知 key:', ', '.join(sorted(unknown)))


PLACEHOLDER = re.compile(r'%\d+%|\$[a-z]|<br>|</?i>')


def merge(path):
    """把 batches/xxx.py 里的 T = {key: 译文} 并入 zh.json，并做检查"""
    ns = {}
    exec(open(path, encoding='utf-8').read(), ns)
    en = json.load(open(EN, encoding='utf-8'))
    zh = json.load(open(ZH, encoding='utf-8'))
    cs_path = os.path.join(HERE, 'charset.txt')
    charset = set(open(cs_path, encoding='utf-8-sig').read()) | {'\n'}
    bad, newchars = False, set()
    for k, v in ns['T'].items():
        if k not in en:
            print('未知 key:', k); bad = True; continue
        a, b = sorted(PLACEHOLDER.findall(en[k])), sorted(PLACEHOLDER.findall(v))
        if a != b and not re.search(r'[一-鿿]', en[k]):
            print(f'占位符不一致 {k}: 原文 {a} 译文 {b}')
        newchars |= set(v) - charset
    if bad:
        sys.exit('有错误，未合并')
    if newchars:  # 新字补进字符集，之后要重新生成字体
        open(cs_path, 'w', encoding='utf-8').write(''.join(sorted((charset | newchars) - {'\n'}, key=ord)))
        print('字符集新增:', ''.join(sorted(newchars)), '→ 需要运行 build_fonts.sh 重新生成字体')
    zh.update(ns['T'])
    json.dump(zh, open(ZH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'合并 {len(ns["T"])} 条，zh.json 共 {len(zh)} / {len(en)} 条')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'merge':
        merge(sys.argv[2])
    else:
        {'export': export, 'apply': apply}[cmd]()
