"""PlayFirst Playground 引擎 .mvec 矢量字体（MVC4）读写、转换与预览

格式（逆向自原版 mvec）
  文件头 12 字节: "MVC4" u16 字数, u16 ascent, u16 descent, u16 linegap
                 （Playmate Font Maker 生成的三个度量全为 0，引擎也能用）
  字符表 每项 18 字节: u32 码位, i16 xmin xmax ymin ymax advance, u32 字形数据偏移
  字形数据（命令流）:
      04 x y         moveTo，每个轮廓开头；第一个轮廓之后紧跟 02 01
      05 x y         lineTo
      06 cx cy x y   二次贝塞尔曲线
      08             字形结束（空字形只有这一个字节）
  坐标为 i16，y 轴向下（基线以上为负），轮廓显式闭合回起点。

引擎行为（实测）
  - 渲染字号按大写 H 的高度 × 约 1.666 归一，所以以原版字体的 H 高度为基准缩放即可对齐字号
  - 折行：按空格折行准确；无空格的中文会“超出边界后才折行”，一行多塞一个字。
    对策是把空格做成近乎零宽（zero_space），由翻译工具在中文字间插入空格作为折行点，
    真正要显示的空格改用 U+00A0
"""
import struct
import sys

GLYPH_END = b'\x08'


# ---------------------------------------------------------------- 读写

def read(path):
    """返回 (header(ascent, descent, linegap), {码位: ((xmin, xmax, ymin, ymax, adv), 字形数据)})"""
    b = open(path, 'rb').read()
    if b[:4] != b'MVC4':
        raise ValueError(f'{path} 不是 MVC4 字体')
    n, *hdr = struct.unpack_from('<4H', b, 4)
    recs = [struct.unpack_from('<I5hI', b, 12 + i * 18) for i in range(n)]
    glyphs = {}
    for k, r in enumerate(recs):
        end = recs[k + 1][6] if k + 1 < n else len(b)
        d = b[r[6]:end]
        i = 0                                   # 截到第一个 08（文件末尾可能有填充）
        while d[i] != 8:
            i += {4: 5, 5: 5, 6: 9, 2: 2}[d[i]]
        glyphs[r[0]] = (tuple(r[1:6]), d[:i + 1])
    return tuple(hdr), glyphs


def write(path, header, glyphs):
    cps = sorted(glyphs)
    off = 12 + 18 * len(cps)
    out = bytearray(b'MVC4' + struct.pack('<4H', len(cps), *header))
    for cp in cps:
        out += struct.pack('<I5hI', cp, *glyphs[cp][0], off)
        off += len(glyphs[cp][1])
    for cp in cps:
        out += glyphs[cp][1]
    open(path, 'wb').write(out)
    return len(out)


# ---------------------------------------------------------------- 转换

def _pen_class():
    from fontTools.pens.basePen import BasePen

    class MvecPen(BasePen):
        """把 fontTools 的轮廓输出成 MVC4 命令流"""

        def __init__(self, glyphset, s, k=1.0, cy=0.0):
            super().__init__(glyphset)
            self.s, self.k, self.cy = s, k, cy   # 缩放 s；额外倍数 k（竖直方向围绕 cy 缩放）
            self.out, self.pts = bytearray(), []
            self.first, self.start, self.cur = True, None, None

        def pt(self, p):
            x = round(p[0] * self.s * self.k)
            y = round(self.cy + (-p[1] * self.s - self.cy) * self.k)
            if not (-32768 <= x <= 32767 and -32768 <= y <= 32767):
                raise OverflowError('坐标超出 i16 范围')
            self.pts.append((x, y))
            return x, y

        def _moveTo(self, p):
            self.start = self.cur = self.pt(p)
            self.out += struct.pack('<Bhh', 4, *self.start)
            if self.first:
                self.out += b'\x02\x01'
                self.first = False

        def _lineTo(self, p):
            q = self.pt(p)
            if q != self.cur:
                self.out += struct.pack('<Bhh', 5, *q)
                self.cur = q

        def _qCurveToOne(self, c, p):
            c, q = self.pt(c), self.pt(p)
            self.out += struct.pack('<Bhhhh', 6, *c, *q)
            self.cur = q

        def _curveToOne(self, c1, c2, p):
            raise RuntimeError('三次曲线应已由 Cu2QuPen 转成二次')

        def _closePath(self):
            if self.cur != self.start:
                self.out += struct.pack('<Bhh', 5, *self.start)
            self.cur = self.start

        _endPath = _closePath

    return MvecPen


def _open_font(path, chars, wght=None):
    """打开 TTF/OTF/TTC，先子集化（加速），可变字体取实例，并去除轮廓重叠"""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    f = TTFont(path, fontNumber=0)
    cmap = f.getBestCmap()
    opts = subset.Options()
    opts.notdef_outline, opts.layout_features, opts.hinting, opts.name_IDs = True, [], False, ['*']
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=[ord(c) for c in chars if ord(c) in cmap] + [ord('H'), ord('中')])
    sub.subset(f)
    if 'fvar' in f:
        from fontTools.varLib import instancer
        axes = {a.axisTag: a.defaultValue for a in f['fvar'].axes}
        if wght is not None and 'wght' in axes:
            axes['wght'] = wght
        f = instancer.instantiateVariableFont(f, axes)
    try:
        from fontTools.ttLib.removeOverlaps import removeOverlaps
        removeOverlaps(f)
    except Exception as e:  # 需要 skia-pathops
        print('  警告: 去除轮廓重叠失败（可能出现镂空）:', e, file=sys.stderr)
    return f


def _bounds(f, ch):
    from fontTools.pens.boundsPen import BoundsPen
    gs = f.getGlyphSet()
    bp = BoundsPen(gs)
    gs[f.getBestCmap()[ord(ch)]].draw(bp)
    return bp.bounds


def convert(source, chars, base=None, keep_latin=False, fallbacks=(), cjk_scale=1.0,
            zero_space=False, wght=None, em=2048, log=print):
    """TTF/OTF → MVC4 字形表。返回 (header, glyphs, 统计信息 dict)

    source      主字体文件
    chars       要包含的字符（可迭代）
    base        原版 .mvec：以其 H 高度为基准缩放，并沿用其文件头度量（字号与原版一致）
    keep_latin  与 base 一起用：原版里已有的字（英文、数字、符号）保留原版字形
    fallbacks   主字体缺字时依次从这些字体补
    cjk_scale   中日韩字符（≥U+2E80）额外放大倍数，竖直方向围绕“中”字中心缩放
    zero_space  空格做成近乎零宽（中文折行点），U+00A0 作可见空格
    """
    from fontTools.pens.cu2quPen import Cu2QuPen
    MvecPen = _pen_class()
    chars = set(chars) - set('\r\n\t﻿') | {' '}

    header, base_glyphs = (0, 0, 0), {}
    if base:
        header, base_glyphs = read(base)
    kept = dict(base_glyphs) if keep_latin else {}
    glyphs = dict(kept)
    todo = sorted((chars | ({chr(c) for c in kept})) - {chr(c) for c in kept}, key=ord)

    main_s = main_upem = None
    filled = {}
    for idx, path in enumerate((source, *fallbacks)):
        if not todo:
            break
        f = _open_font(path, todo, wght if idx == 0 else None)
        upem = f['head'].unitsPerEm
        if main_s is None:
            main_s = (-base_glyphs[ord('H')][0][2] / _bounds(f, 'H')[3]) if base else em / upem
            main_upem = upem
        s = main_s * main_upem / upem
        cmap, gs, hmtx = f.getBestCmap(), f.getGlyphSet(), f['hmtx']
        cy = 0.0
        if cjk_scale != 1.0 and ord('中') in cmap:
            b = _bounds(f, '中')
            cy = -(b[1] + b[3]) / 2 * s
        left = []
        for ch in todo:
            gname = cmap.get(ord(ch))
            if gname is None:
                left.append(ch)
                continue
            k = cjk_scale if ord(ch) >= 0x2E80 else 1.0
            adv = round(hmtx[gname][0] * s * k)
            pen = MvecPen(gs, s, k, cy)
            gs[gname].draw(Cu2QuPen(pen, max_err=upem / 1000 * 0.75, reverse_direction=False))
            if pen.pts:
                xs = [p[0] for p in pen.pts]; ys = [p[1] for p in pen.pts]
                # xmin 最大取 0：只扩大边界框，不影响字形（保险起见，避免引擎量宽偏小）
                box = (min(min(xs), 0), max(xs), min(ys), max(ys), adv)
                glyphs[ord(ch)] = (box, bytes(pen.out) + GLYPH_END)
            else:
                glyphs[ord(ch)] = ((0, adv, 0, 0, adv), GLYPH_END)
        if idx > 0 and len(todo) > len(left):
            filled[path] = len(todo) - len(left)
        todo = left

    if zero_space and 0x20 in glyphs:
        adv = glyphs[0x20][0][4]
        glyphs[0xA0] = ((0, adv, 0, 0, adv), GLYPH_END)
        glyphs[0x20] = ((0, 1, 0, 0, 1), GLYPH_END)

    stats = {'字数': len(glyphs), '保留原版': len(kept), '缩放': main_s, '后备补字': filled, '缺字': ''.join(todo)}
    return header, glyphs, stats


# ---------------------------------------------------------------- 预览

def _contours(data):
    i, cs, cur = 0, [], None
    while True:
        op = data[i]; i += 1
        if op == 8:
            return cs
        if op == 2:
            i += 1
        elif op == 4:
            cur = [struct.unpack_from('<hh', data, i)]; cs.append(cur); i += 4
        elif op == 5:
            cur.append(struct.unpack_from('<hh', data, i)); i += 4
        elif op == 6:
            cx, cy, x, y = struct.unpack_from('<hhhh', data, i); i += 8
            x0, y0 = cur[-1]
            for t in (j / 8 for j in range(1, 9)):
                cur.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x,
                            (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y))


def render(font, text, px=48, space_px=None):
    """把文字用 mvec 字形渲染成灰度 PIL 图像。font 为路径或 read() 的结果。
    字号按引擎规则：size 对应 H 高度 × 1.666。零宽空格字体可用 space_px 指定预览中空格宽度。"""
    from PIL import Image, ImageDraw
    header, glyphs = read(font) if isinstance(font, str) else font
    s = px / (-glyphs[ord('H')][0][2] * 1.666)
    asc = (header[0] or -min(g[0][2] for g in glyphs.values())) * s
    desc = (header[1] or max(g[0][3] for g in glyphs.values())) * s
    W = int(sum(glyphs[ord(c)][0][4] * s if ord(c) in glyphs else px for c in text) + (space_px or 0) * text.count(' ')) + 20
    H = int(asc + desc) + 20
    mask = Image.new('1', (W, H), 0)
    x = 10.0
    for c in text:
        if c == ' ' and space_px is not None:
            x += space_px; continue
        g = glyphs.get(ord(c))
        if g is None:                         # 缺字画个框
            ImageDraw.Draw(mask).rectangle([x + 2, 10, x + px * 0.8, 10 + asc], outline=1)
            x += px; continue
        for cs in _contours(g[1]):            # 逐轮廓异或 = 奇偶填充
            layer = Image.new('1', (W, H), 0)
            ImageDraw.Draw(layer).polygon([(x + p[0] * s, 10 + asc + p[1] * s) for p in cs], fill=1)
            mask = Image.frombytes('1', (W, H), bytes(a ^ b for a, b in zip(mask.tobytes(), layer.tobytes())))
        x += g[0][4] * s
    img = Image.new('L', (W, H), 255)
    img.paste(0, mask=mask)
    return img
