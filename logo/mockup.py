"""在空白场记板上试排中文 logo（找字体灵感用）

  python mockup.py              → mockup_sheet.png（多种字体组合对比）
上行“美女”仿原版 Soap Opera：蓝色渐变 + 深蓝描边 + 白色光晕
下行“肥皂剧”仿原版 DASH：黄橙渐变 + 暗红描边
"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
WIN = 'C:/Windows/Fonts/'
USR = os.path.expandvars('%LOCALAPPDATA%/Microsoft/Windows/Fonts/')
REF = os.path.join(HERE, '..', '..', 'Game Files', 'pfp', '参考字体')
F = {
    '方正舒体': WIN + 'FZSTK.TTF', '华文行楷': WIN + 'STXINGKA.TTF', '华文新魏': WIN + 'STXINWEI.TTF',
    '方正姚体': WIN + 'FZYTK.TTF', '华文琥珀': WIN + 'STHUPO.TTF', '华康方圆体W7': WIN + '华康方圆体W7.TTC',
    '筑紫明朝H': USR + '方正FW筑紫明朝 简 H.TTF', '黄凯桦律师体': USR + 'huangkaihuaLawyerfont.ttf',
    '张清平硬笔楷书': USR + '瑞美加张清平硬笔楷书.ttf', '方正胖娃': USR + '方正胖娃_GBK.ttf',
    '优设标题黑': USR + '优设标题黑.ttf', 'HONOR Heavy': USR + 'HONORSansCN-Heavy.ttf',
    '站酷快乐体': os.path.join(REF, '站酷快乐体3.53', '站酷快乐体 开源版.ttf'),
    '寒蝉团圆体': os.path.join(REF, '寒蝉团圆圆2.7', 'ChillReunion_Round.otf'),
}
COMBOS = [
    ('方正舒体', '方正胖娃'), ('华文行楷', '华文琥珀'), ('筑紫明朝H', '站酷快乐体'), ('华文新魏', '优设标题黑'),
    ('黄凯桦律师体', '华康方圆体W7'), ('方正姚体', '寒蝉团圆体'), ('张清平硬笔楷书', 'HONOR Heavy'), ('方正舒体', '站酷快乐体'),
]


def gradient(size, top, bottom):
    w, h = size
    g = Image.new('RGBA', (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        g.putpixel((0, y), tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,))
    return g.resize((w, h))


def styled_text(text, font_path, box, fill, outline, ow, glow=0, angle=0):
    """box=(cx, cy, maxw, maxh)：自动选字号放进框里，返回 259×223 图层"""
    cx, cy, mw, mh = box
    size = 120
    while size > 8:
        f = ImageFont.truetype(font_path, size)
        l, t, r, b = f.getbbox(text)
        if r - l <= mw and b - t <= mh:
            break
        size -= 2
    pad = ow + glow * 3 + 4
    W, H = r - l + 2 * pad, b - t + 2 * pad
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), text, font=f, fill=255)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if glow:
        g = mask.filter(ImageFilter.MaxFilter(2 * (ow + glow) + 1)).filter(ImageFilter.GaussianBlur(glow / 1.5))
        layer = Image.composite(Image.new('RGBA', (W, H), (255, 255, 255, 255)), layer, g)
    o = mask.filter(ImageFilter.MaxFilter(2 * ow + 1))
    layer = Image.composite(Image.new('RGBA', (W, H), outline + (255,)), layer, o)
    # 内描边下方加一道深色阴影，模仿原版立体感
    layer = Image.composite(gradient((W, H), *fill), layer, mask)
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    out = Image.new('RGBA', (259, 223), (0, 0, 0, 0))
    out.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))
    return out


def mock(top_font, bottom_font):
    base = Image.open(os.path.join(HERE, 'logo_blank.png')).convert('RGBA')
    bottom = styled_text('肥皂剧', F[bottom_font], (128, 160, 190, 62), ((255, 236, 90), (245, 150, 20)), (110, 20, 50), 3, angle=3)
    top = styled_text('美女', F[top_font], (118, 100, 150, 56), ((190, 240, 255), (40, 110, 230)), (20, 30, 110), 2, glow=2, angle=4)
    base.alpha_composite(bottom)
    base.alpha_composite(top)
    return base


if __name__ == '__main__':
    cell_w, cell_h, scale = 259 * 3 // 2, 223 * 3 // 2 + 34, 1.5
    cols = 4
    rows = (len(COMBOS) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell_w, rows * cell_h), (150, 200, 235))
    lab = ImageFont.truetype(WIN + 'msyh.ttc', 18)
    d = ImageDraw.Draw(sheet)
    for i, (tf, bf) in enumerate(COMBOS):
        m = mock(tf, bf).resize((int(259 * scale), int(223 * scale)), Image.LANCZOS)
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        sheet.paste(m, (x, y + 30), m)
        d.text((x + 10, y + 4), f'{i + 1}. 上:{tf}  下:{bf}', font=lab, fill=(20, 20, 60))
    sheet.save(os.path.join(HERE, 'mockup_sheet.png'))
    print('ok')
