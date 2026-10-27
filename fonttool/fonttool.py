"""PlayFirst（Playground 引擎）游戏汉化字体工具

  python fonttool.py scan  游戏assets目录                列出所有 .mvec 字体及其在脚本中的引用
  python fonttool.py init  游戏assets目录 项目目录         备份原版字体，生成项目配置 fonts.json
  python fonttool.py build [字体名…] [-p fonts.json] [--no-install]
                                                         按配置生成中文字体并装进游戏（缺省全部）
  python fonttool.py try   字体名 [--source 字体文件] [--cjk-scale 1.2] [--text 文字] [-p fonts.json]
                                                         试做一版（只含预览文字，几秒完成），出对比图，不装进游戏
  python fonttool.py preview 字体.mvec… [--text 文字] [-o 图片]   渲染预览
  python fonttool.py info  字体.mvec [--has 文字]          查看字体信息 / 是否含某些字

项目配置 fonts.json 中的路径都相对于配置文件所在目录，支持 %LOCALAPPDATA% 这类环境变量。
"""
import argparse, glob, json, os, re, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mvec  # noqa: E402

DEFAULT_PROJECT = 'fonts.json'
SAMPLE = '中文汉化 开始游戏 重新开始 返回 设置 PLAY 12345'


# ---------------------------------------------------------------- 项目配置

class Project:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.dir = os.path.dirname(self.path)
        self.cfg = json.load(open(self.path, encoding='utf-8'))

    def p(self, x):
        """配置里的路径 → 绝对路径（展开环境变量，相对于配置文件）"""
        if not x:
            return None
        x = os.path.expandvars(os.path.expanduser(x))
        return os.path.normpath(x if os.path.isabs(x) else os.path.join(self.dir, x))

    @property
    def fonts(self):
        return {k: v for k, v in self.cfg['fonts'].items() if not k.startswith('_')}

    def charset(self):
        path = self.p(self.cfg.get('charset'))
        text = open(path, encoding='utf-8-sig').read() if path else ''
        return set(text)

    def options(self, name, **override):
        f = dict(self.fonts[name]); f.update({k: v for k, v in override.items() if v is not None})
        fallbacks = f.get('fallback', self.cfg.get('fallback', []))
        return dict(source=self.p(f['source']), base=self.p(f.get('original')),
                    keep_latin=f.get('keep_latin', False), cjk_scale=f.get('cjk_scale', 1.0),
                    zero_space=f.get('zero_space', False), wght=f.get('wght'),
                    fallbacks=[self.p(x) for x in fallbacks if self.p(x) != self.p(f['source'])])


def load_project(args):
    path = args.project or os.path.join(os.getcwd(), DEFAULT_PROJECT)
    if not os.path.exists(path):
        sys.exit(f'找不到项目配置 {path}（用 -p 指定，或先运行 init）')
    return Project(path)


# ---------------------------------------------------------------- 命令

def cmd_scan(args):
    assets = os.path.abspath(args.assets)
    fonts = sorted(glob.glob(os.path.join(assets, '**', '*.mvec'), recursive=True))
    if not fonts:
        print('没有找到 .mvec 字体。若游戏资源还在 .pfp 封包里，需要先解包。')
        return
    srcs = {}
    for f in glob.glob(os.path.join(assets, '**', '*.lua'), recursive=True) + \
             glob.glob(os.path.join(assets, '**', '*.xml'), recursive=True):
        try:
            srcs[f] = open(f, encoding='utf-8', errors='replace').read()
        except OSError:
            pass
    for path in fonts:
        rel = os.path.relpath(path, assets).replace('\\', '/')
        try:
            hdr, g = mvec.read(path)
            H = g.get(ord('H'))
            cjk = sum(1 for c in g if c >= 0x4E00)
            print(f'\n{rel}  {os.path.getsize(path) // 1024}KB  字数 {len(g)}（汉字 {cjk}）'
                  f'  文件头 {hdr}  H高 {-H[0][2] if H else "无"}')
        except Exception as e:
            print(f'\n{rel}  无法读取: {e}'); continue
        name = os.path.basename(path)
        for f, s in srcs.items():
            for m in re.finditer(re.escape(name), s):
                line = s[s.rfind('\n', 0, m.start()) + 1:s.find('\n', m.end())].strip()
                print(f'    {os.path.relpath(f, assets)}: {line[:100]}')


def nice_path(target, start):
    """离得近就写相对路径，否则写绝对路径（避免一长串 ../../..）"""
    try:
        rel = os.path.relpath(target, start)
    except ValueError:              # 不同盘符
        rel = None
    if rel is None or rel.count('..') > 2:
        rel = os.path.realpath(target)
    return rel.replace('\\', '/')


def cmd_init(args):
    assets, proj = os.path.abspath(args.assets), os.path.abspath(args.project_dir)
    orig = os.path.join(proj, 'original')
    os.makedirs(orig, exist_ok=True)
    cfg_path = os.path.join(proj, DEFAULT_PROJECT)
    if os.path.exists(cfg_path):
        sys.exit(f'{cfg_path} 已存在，不覆盖')
    fonts = {}
    for path in sorted(glob.glob(os.path.join(assets, '**', '*.mvec'), recursive=True)):
        name = os.path.basename(path)
        dst = os.path.join(orig, name)
        if not os.path.exists(dst):
            shutil.copy2(path, dst)
        hdr, g = mvec.read(path)
        fonts[os.path.splitext(name)[0]] = {
            'source': '在这里填中文字体文件路径（ttf/otf/ttc）',
            'original': 'original/' + name if ord('H') in g else None,
            'install_as': [os.path.relpath(path, assets).replace('\\', '/')],
            'keep_latin': False, 'cjk_scale': 1.0, 'zero_space': False,
        }
    cfg = {
        '_说明': '路径相对于本文件；original 为原版字体（用于对齐字号和保留英文）；'
                'install_as 相对于 game_assets。zero_space 需配合翻译工具在中文字间插空格。',
        'game_assets': nice_path(assets, proj),
        'charset': 'charset.txt',
        'fallback': [],
        'preview_text': SAMPLE,
        'fonts': fonts,
    }
    json.dump(cfg, open(cfg_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    if not os.path.exists(os.path.join(proj, 'charset.txt')):
        open(os.path.join(proj, 'charset.txt'), 'w', encoding='utf-8').write(
            ''.join(chr(c) for c in range(0x20, 0x7F)) + '，。！？、：；“”‘’（）《》…—')
    print(f'已备份 {len(fonts)} 套原版字体到 {orig}\n已生成 {cfg_path}，请填写各字体的 source，并把译文用字补进 charset.txt')


def cmd_build(args):
    pj = load_project(args)
    names = args.names or list(pj.fonts)
    chars = pj.charset()
    out_dir = pj.p(pj.cfg.get('build_dir', 'build'))
    os.makedirs(out_dir, exist_ok=True)
    assets = pj.p(pj.cfg['game_assets'])
    for name in names:
        if name not in pj.fonts:
            sys.exit(f'配置里没有字体「{name}」，可选：{"、".join(pj.fonts)}')
        t = time.time()
        print(f'【{name}】', end=' ', flush=True)
        hdr, glyphs, st = mvec.convert(chars=chars, **pj.options(name))
        out = os.path.join(out_dir, name + '.mvec')
        size = mvec.write(out, hdr, glyphs)
        print(f'{st["字数"]} 字（保留原版 {st["保留原版"]}），{size // 1024}KB，{time.time() - t:.0f}秒')
        for path, n in st['后备补字'].items():
            print(f'    从 {os.path.basename(path)} 补了 {n} 字')
        if st['缺字']:
            print(f'    ⚠ 所有字体都缺: {st["缺字"][:60]}')
        if not args.no_install:
            for rel in pj.fonts[name]['install_as']:
                shutil.copy2(out, os.path.join(assets, rel))
                print(f'    → {rel}')


def cmd_try(args):
    pj = load_project(args)
    name = args.name
    if name not in pj.fonts:
        sys.exit(f'配置里没有字体「{name}」，可选：{"、".join(pj.fonts)}')
    text = args.text or pj.cfg.get('preview_text', SAMPLE)
    opts = pj.options(name, source=args.source, cjk_scale=args.cjk_scale)
    if args.source:
        opts['source'] = os.path.abspath(os.path.expandvars(args.source))
    hdr, glyphs, st = mvec.convert(chars=set(text) | set('H'), log=lambda *a: None, **opts)
    rows = []
    if opts['base']:
        rows.append(('原版', mvec.read(opts['base'])))
    cur = os.path.join(pj.p(pj.cfg['game_assets']), pj.fonts[name]['install_as'][0])
    if os.path.exists(cur):
        rows.append(('游戏里现在的', mvec.read(cur)))
    label = f'试做：{os.path.basename(opts["source"])}  ×{opts["cjk_scale"]}'
    rows.append((label, (hdr, glyphs)))
    out = args.output or os.path.join(pj.p(pj.cfg.get('build_dir', 'build')), f'try_{name}.png')
    stack(rows, text, out, args.px)
    print('对比图:', out)


def cmd_preview(args):
    rows = [(os.path.basename(f), mvec.read(f)) for f in args.fonts]
    out = args.output or 'preview.png'
    stack(rows, args.text or SAMPLE, out, args.px)
    print('预览:', out)


def cmd_info(args):
    hdr, g = mvec.read(args.font)
    H = g.get(ord('H'))
    print(f'{args.font}\n  字数 {len(g)}，其中汉字 {sum(1 for c in g if 0x4E00 <= c <= 0x9FFF)}')
    print(f'  文件头 ascent/descent/linegap = {hdr}{"（全 0：Font Maker 风格）" if not any(hdr) else ""}')
    if H:
        print(f'  H 高 {-H[0][2]}，空格宽 {g[0x20][0][4] if 0x20 in g else "无"}'
              f'{"（零宽空格模式）" if 0x20 in g and g[0x20][0][4] <= 1 else ""}')
    if args.has:
        miss = [c for c in dict.fromkeys(args.has) if ord(c) not in g and c not in '\r\n']
        print('  缺字:', ''.join(miss) if miss else '无')


def stack(rows, text, out, px=48):
    """把多行预览上下拼成一张图，每行上方标注名称"""
    from PIL import Image, ImageDraw, ImageFont
    imgs = [(lab, mvec.render(f, text, px, space_px=px // 3)) for lab, f in rows]
    try:
        lab_font = ImageFont.truetype('msyh.ttc', 18)
    except OSError:
        lab_font = ImageFont.load_default()
    W = max(i.width for _, i in imgs) + 20
    H = sum(i.height + 28 for _, i in imgs)
    sheet = Image.new('RGB', (W, H), 'white')
    d, y = ImageDraw.Draw(sheet), 0
    for lab, im in imgs:
        d.text((10, y + 4), lab, font=lab_font, fill=(200, 60, 60))
        sheet.paste(im.convert('RGB'), (0, y + 28)); y += im.height + 28
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser(description='PlayFirst 游戏汉化字体工具（.mvec）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan', help='列出游戏里的 .mvec 字体及引用'); s.add_argument('assets')
    s = sub.add_parser('init', help='备份原版字体并生成项目配置'); s.add_argument('assets'); s.add_argument('project_dir')
    s = sub.add_parser('build', help='按配置生成并安装字体')
    s.add_argument('names', nargs='*'); s.add_argument('-p', '--project'); s.add_argument('--no-install', action='store_true')
    s = sub.add_parser('try', help='试做一版并出对比图（不安装）')
    s.add_argument('name'); s.add_argument('-p', '--project'); s.add_argument('--source')
    s.add_argument('--cjk-scale', type=float); s.add_argument('--text'); s.add_argument('-o', '--output')
    s.add_argument('--px', type=int, default=48)
    s = sub.add_parser('preview', help='渲染 mvec 预览')
    s.add_argument('fonts', nargs='+'); s.add_argument('--text'); s.add_argument('-o', '--output')
    s.add_argument('--px', type=int, default=48)
    s = sub.add_parser('info', help='查看 mvec 信息'); s.add_argument('font'); s.add_argument('--has')
    a = ap.parse_args()
    {'scan': cmd_scan, 'init': cmd_init, 'build': cmd_build, 'try': cmd_try,
     'preview': cmd_preview, 'info': cmd_info}[a.cmd](a)


if __name__ == '__main__':
    main()
