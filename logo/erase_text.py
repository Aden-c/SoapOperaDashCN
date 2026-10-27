"""去掉 logo 上的英文字，留下空白场记板（供重绘中文）

输入 logo_orig.png（从图集 sod_mainmenu_pieces01.png 的 x0-259, y246-469 裁出），
输出 logo_blank.png 与 2 倍预览 logo_blank_view.png。

  1. 文字遮罩 M：高饱和像素（蓝字、黄字、暗红描边、™）膨胀 DILATE 像素，盖住白色光晕
  2. 外轮廓 S：原 alpha 减去伸出牌子左右边线的文字（边线用未被压住的行拟合成直线）
  3. 牌子主体 = S 中位于场记板下杆分界线以下的部分
     边缘带（离外轮廓或下杆分界线 < BAND）：被遮像素取“同一距离层”最近的完好像素
     中间大面积：完好像素拟合二维多项式曲面后填充
  4. 下杆条纹被压到的小块：FSR 频域修复
"""
import sys
import cv2
import numpy as np
from PIL import Image

DILATE = int(sys.argv[1]) if len(sys.argv) > 1 else 6
BAND = 14
DEG = 4
SAT = int(sys.argv[2]) if len(sys.argv) > 2 else 25

im = np.array(Image.open('logo_orig.png').convert('RGBA'))
H, W = im.shape[:2]
rgb, a = im[..., :3].astype(np.float32), im[..., 3]
yy, xx = np.mgrid[0:H, 0:W]

# ---- 1. 文字遮罩 ----
sat = rgb.max(-1) - rgb.min(-1)
text = (sat > SAT) & (a > 20)
blue = text & (rgb[..., 2] > rgb[..., 0])          # “Soap Opera”蓝字，带白色光晕
ell = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2)
M = (cv2.dilate(blue.astype(np.uint8), ell(DILATE)) > 0) |     (cv2.dilate((text & ~blue).astype(np.uint8), ell(2)) > 0)   # DASH 只有描边，少扩一点

# ---- 2. 外轮廓 ----
S0 = a > 128
def edge(side, rows):
    ys, xs = [], []
    for y in rows:
        row = np.nonzero(S0[y])[0]
        if len(row) == 0:
            continue
        x = row.min() if side == 'L' else row.max()
        if not M[y, max(x - 3, 0):x + 4].any():
            ys.append(y); xs.append(x)
    return np.poly1d(np.polyfit(ys, xs, 1))
xL = edge('L', list(range(65, 86)) + list(range(135, 196)))
xR = edge('R', list(range(55, 81)) + list(range(120, 196)))
band_rows = (yy > 60) & (yy < 140)
overhang = M & band_rows & ((xx < xL(yy) - 0.5) | (xx > xR(yy) + 0.5))
S = S0 & ~overhang

# ---- 3. 牌子主体 ----
# 场记板下杆底部黑线的下沿（逐列实测；左端随铰链透视下弯，x140-160 被字压住取插值）
LINE_X = [0, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 170, 220, 259]
LINE_Y = [90, 86.5, 84.5, 82.5, 80.5, 78.5, 76.5, 74.5, 72.5, 71.5, 69.5, 68.5, 67.5, 66.5, 67.5, 67.5]
yline = np.interp(xx, LINE_X, LINE_Y)
body = S & (yy > yline)
stick = S & ~body

d_out = cv2.distanceTransform(S.astype(np.uint8), cv2.DIST_L2, 5)
d_edge = d_out   # 下杆下方原图只是平滑渐变，交给曲面拟合
damaged = M & S
out = im.copy()

def band_fill(region, dist, src_ok):
    """region 里被遮的像素，取同一距离层（四舍五入）里最近的完好像素"""
    k_map = np.rint(dist).astype(int)
    for k in range(BAND):
        tgt = damaged & region & (k_map == k)
        src = src_ok & region & (k_map == k)
        if not tgt.any() or not src.any():
            continue
        inv = np.where(src, 0, 255).astype(np.uint8)
        _, labels = cv2.distanceTransformWithLabels(inv, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        ys, xs = np.nonzero(src)
        lut = np.zeros((labels.max() + 1, 2), int)
        lut[labels[ys, xs]] = np.stack([ys, xs], 1)
        ty, tx = np.nonzero(tgt)
        sy, sx = lut[labels[ty, tx]].T
        out[ty, tx] = im[sy, sx]

clean = S & ~cv2.dilate(M.astype(np.uint8), np.ones((7, 7))).astype(bool)   # 取色源避开文字光晕
band_fill(body & (d_edge < BAND), d_edge, clean)

# 中间：二维多项式曲面
inner = body & (d_edge >= BAND)
fit_px = inner & ~cv2.dilate(M.astype(np.uint8), np.ones((5, 5))).astype(bool)
def feats(x, y):
    x = x / W; y = y / H
    return np.stack([x ** i * y ** j for i in range(DEG + 1) for j in range(DEG + 1 - i)], -1)
fy, fx = np.nonzero(fit_px)
A = feats(fx, fy)
coef = np.linalg.lstsq(A, rgb[fy, fx], rcond=None)[0]
# 整片内部用拟合面覆盖（避免与残留原像素拼接出边界），在 BAND~BAND+4 渐变过渡
ty, tx = np.nonzero(inner)
fitted = np.clip(feats(tx, ty) @ coef, 0, 255)
w = np.clip((d_edge[ty, tx] - BAND) / 4.0, 0, 1)[:, None]
keep = (~damaged[ty, tx])[:, None]          # 过渡区里未被遮的像素才与原图混合
base = np.where(keep, out[ty, tx, :3].astype(np.float32), fitted)
out[ty, tx, :3] = np.clip(base * (1 - w) + fitted * w, 0, 255).astype(np.uint8)
out[ty, tx, 3] = 255
print(f'曲面拟合点 {len(fy)}，残差 {np.abs(A @ coef - rgb[fy, fx]).mean():.1f}')

# ---- 4. 下杆条纹：FSR 频域修复 ----
# （试过按条纹周期平移复制：杆子是弧形透视，条纹不等距，单一位移误差太大）
stick_hole = damaged & stick
if stick_hole.any():
    bgr = cv2.cvtColor(out[..., :3], cv2.COLOR_RGB2BGR)
    res = np.zeros_like(bgr)
    cv2.xphoto.inpaint(bgr, np.where(stick_hole, 0, 255).astype(np.uint8), res, cv2.xphoto.INPAINT_FSR_BEST)
    out[stick_hole, :3] = cv2.cvtColor(res, cv2.COLOR_BGR2RGB)[stick_hole]
    out[stick_hole, 3] = 255
print('下杆修补像素', int(stick_hole.sum()))

# ---- 5. 残留色偏（低饱和的光晕边缘像素）：牌子本身是纯灰阶，带色的都补掉 ----
o = out[..., :3].astype(np.int16)
tint = S & ~overhang & ((o.max(-1) - o.min(-1)) > 10)
if tint.any():
    bgr = cv2.cvtColor(out[..., :3], cv2.COLOR_RGB2BGR)
    bgr = cv2.inpaint(bgr, tint.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
    out[tint, :3] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)[tint]
print('残留色偏像素', int(tint.sum()))

out[overhang] = 0      # 伸出牌子的文字光晕 → 透明

Image.fromarray(out).save('logo_blank.png')
bg = Image.new('RGBA', (W, H), (255, 0, 255, 255))
bg.alpha_composite(Image.fromarray(out))
bg.convert('RGB').resize((W * 2, H * 2), Image.NEAREST).save('logo_blank_view.png')
print('ok')
