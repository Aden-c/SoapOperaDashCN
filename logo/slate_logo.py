"""把中文 logo 换进过场大场记板 animfx/slate_big/atbt_slatebig.png

  python slate_logo.py [logo_cn.png]
以 hanhua/backup/atbt_slatebig.png（原版）为底：
  1. 原版小 logo（模板匹配得出：无旋转、缩放 1.044、左上角 544,339）整块抹掉，
     用周围一圈底色拟合二次曲面补成干净的深色渐变
  2. 中文 logo 按同样比例缩放后叠上去
"""
import os, sys
import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'backup', 'atbt_slatebig.png')
DST = os.path.join(HERE, '..', '..', 'Game Files', 'assets', 'animfx', 'slate_big', 'atbt_slatebig.png')
SCALE, X0, Y0 = 1.044, 544, 339

logo_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'logo_cn.png')
big = np.array(Image.open(SRC).convert('RGBA'))
H, W = big.shape[:2]

def scaled(path):
    im = Image.open(path).convert('RGBA')
    return np.array(im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS))

old = scaled(os.path.join(HERE, 'logo_orig.png'))
new = scaled(logo_path)
h, w = old.shape[:2]

# ---- 1. 抹掉原版小 logo ----
foot = np.zeros((H, W), bool)
foot[Y0:Y0 + h, X0:X0 + w] = old[..., 3] > 0
foot = cv2.dilate(foot.astype(np.uint8), np.ones((5, 5))) > 0          # 连同抗锯齿边缘
ring = (cv2.dilate(foot.astype(np.uint8), np.ones((25, 25))) > 0) & ~foot
ring &= big[..., 3] == 255
yy, xx = np.nonzero(ring)
def feats(x, y):
    x = x / W; y = y / H
    return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], -1)
coef = np.linalg.lstsq(feats(xx, yy), big[yy, xx, :3].astype(np.float32), rcond=None)[0]
ty, tx = np.nonzero(foot)
out = big.copy()
out[ty, tx, :3] = np.clip(feats(tx, ty) @ coef, 0, 255).astype(np.uint8)
out[ty, tx, 3] = 255
print(f'底色拟合残差 {np.abs(feats(xx, yy) @ coef - big[yy, xx, :3]).mean():.1f}')

# ---- 2. 叠上中文 logo ----
canvas = Image.fromarray(out)
canvas.alpha_composite(Image.fromarray(new), (X0, Y0))
canvas.save(DST)
print('已写入', os.path.normpath(DST))
