"""清掉 logo 上完全落在牌子轮廓以外的零散像素（原版文字光晕的残留）
   python clean_strays.py 输入.png [输出.png]   （缺省覆盖输入）"""
import sys
import cv2
import numpy as np
from PIL import Image

src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else src
im = np.array(Image.open(src).convert('RGBA'))
plate = np.array(Image.open('logo_blank.png').convert('RGBA'))[..., 3] > 128
# 牌子主体 = 空白版里最大的不透明连通块，稍微外扩以包含抗锯齿边缘
n, lab, stats, _ = cv2.connectedComponentsWithStats(plate.astype(np.uint8))
body = lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
body = cv2.dilate(body.astype(np.uint8), np.ones((5, 5))) > 0
n, lab, stats, _ = cv2.connectedComponentsWithStats((im[..., 3] > 0).astype(np.uint8), connectivity=8)
removed = 0
for i in range(1, n):
    comp = lab == i
    if not (comp & body).any():          # 整块都在牌子外面
        im[comp] = 0; removed += int(comp.sum())
Image.fromarray(im).save(dst)
print(f'{src}: 清除牌子外零散像素 {removed} 个')
