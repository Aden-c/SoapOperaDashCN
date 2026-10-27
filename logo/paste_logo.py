"""把画好的 logo 贴回主菜单图集

  python paste_logo.py 你的logo.png
    → 以 hanhua/backup/sod_mainmenu_pieces01.png（原版图集）为底，把 logo 贴到原位 (0, 246)，
      写入 Game Files/assets/animfx/mainmenu/sod_mainmenu_pieces01.png

你的 logo 必须是 259×223、带透明通道的 PNG（建议直接在 logo_blank.png 上画）。
只替换 logo 精灵自己的区域；新画的内容若伸进相邻精灵（右边紧挨着聚光灯）会报错提醒。
"""
import os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS_SRC = os.path.join(HERE, '..', 'backup', 'sod_mainmenu_pieces01.png')
ATLAS_DST = os.path.join(HERE, '..', '..', 'Game Files', 'assets', 'animfx', 'mainmenu', 'sod_mainmenu_pieces01.png')
X0, Y0, W, H = 0, 246, 259, 223

import subprocess, tempfile
# 先清掉牌子轮廓外的零散像素（原版文字光晕残留），存到临时文件再用
tmp = os.path.join(tempfile.gettempdir(), 'logo_clean_tmp.png')
subprocess.run([sys.executable, '-X', 'utf8', os.path.join(HERE, 'clean_strays.py'), os.path.abspath(sys.argv[1]), tmp],
               cwd=HERE, check=True)
logo = Image.open(tmp).convert('RGBA')
if logo.size != (W, H):
    sys.exit(f'尺寸应为 {W}×{H}，实际 {logo.size[0]}×{logo.size[1]}')
atlas = Image.open(ATLAS_SRC).convert('RGBA')
A = np.array(atlas)
region = A[Y0:Y0 + H, X0:X0 + W]
orig = np.array(Image.open(os.path.join(HERE, 'logo_orig.png')).convert('RGBA'))
new = np.array(logo)

# 原 logo 精灵占的像素 = 区域内与 logo_orig 一致且不透明的部分；其余不透明像素属于相邻精灵
mine = (orig[..., 3] > 0)
others = (region[..., 3] > 0) & ~mine
clash = others & (new[..., 3] > 0)
if clash.any():
    ys, xs = np.nonzero(clash)
    sys.exit(f'新 logo 有 {clash.sum()} 个像素压到了相邻精灵（如 x={xs[0]}, y={ys[0]}），请收回到原轮廓附近')

region[~others] = new[~others]
A[Y0:Y0 + H, X0:X0 + W] = region
Image.fromarray(A).save(ATLAS_DST)
print('已写入游戏图集:', os.path.normpath(ATLAS_DST))
