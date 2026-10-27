# PlayFirst 游戏汉化字体工具（fonttool）

把任意 TTF / OTF / TTC 中文字体转换成 PlayFirst **Playground 引擎**使用的 `.mvec` 矢量字体（MVC4 格式），
用于《美女餐厅》(Diner Dash) 系列等 PlayFirst 游戏的汉化。

在《美女肥皂剧》(Soap Opera Dash, 2010) 上完整验证过；其他游戏请先用 `scan` 确认字体格式一致。

## 为什么需要它

官方的 Playmate Font Maker 有两个问题：

- 它不一定真的用你指定的字体——会悄悄换成系统里的某个黑体；
- 它把空格做成了 `!` 的字形，英文显示成 `Every!now!and!then`。

本工具直接读取字体轮廓、自行写出 `.mvec`，不依赖 Font Maker。

## 安装

需要 Python 3.10 以上：

```
pip install -r requirements.txt
```

`skia-pathops` 用于去除可变字体 / 部分字体的轮廓重叠，没有它也能运行，但个别字可能出现镂空。

## 开新坑的流程

1. **解包**：游戏资源若在 `.pfp` 封包里，先用 pfpextract 解成散文件（引擎也能直接读 `assets/` 下的散文件）。
2. **看看游戏有哪些字体**

   ```
   python fonttool.py scan 游戏目录/assets
   ```

   会列出每个 `.mvec` 的字数、文件头度量、H 字高，以及它在哪个脚本里被引用（通常是 `scripts/style.lua`）。
3. **建项目**

   ```
   python fonttool.py init 游戏目录/assets 我的汉化/字体
   ```

   原版字体会备份到 `original/`，并生成 `fonts.json`。**一定要在替换之前做这一步**，之后对齐字号、保留英文都要用原版。
4. **填写 `fonts.json`**：给每套字体填 `source`（中文字体文件），用不到的字体（如调试控制台字体）可以删掉。
5. **准备字符集 `charset.txt`**：把译文里用到的所有字放进去（建议直接用一份常用字表 + 译文全文）。
6. **试字体**（只生成预览文字，几秒完成，不改游戏）

   ```
   python fonttool.py try 标题 --source 某字体.otf --cjk-scale 1.1 -p fonts.json
   ```

   输出一张对比图：原版 / 游戏里现在的 / 试做的。
7. **生成并装进游戏**

   ```
   python fonttool.py build -p fonts.json          全部
   python fonttool.py build 按钮 -p fonts.json     只做某一套
   ```

## fonts.json

```json
{
  "game_assets": "../Game Files/assets",
  "charset": "charset.txt",
  "build_dir": "build",
  "fallback": ["%LOCALAPPDATA%/Microsoft/Windows/Fonts/某黑体.ttf"],
  "preview_text": "中文汉化 开始游戏 返回 PLAY 12345",
  "fonts": {
    "按钮": {
      "source": "某圆体.otf",
      "original": "original/florastdbold.mvec",
      "keep_latin": true,
      "cjk_scale": 1.07,
      "zero_space": true,
      "install_as": ["font/florastdbold.mvec"]
    }
  }
}
```

| 字段 | 说明 |
|---|---|
| `source` | 中文字体文件（ttf/otf/ttc，可变字体可加 `"wght": 500` 选字重） |
| `original` | 原版 `.mvec`。以它的大写 H 高度为基准缩放，并沿用它的文件头度量，**字号、行距与原版一致**。留空则按 2048 em 生成 |
| `keep_latin` | 原版里已有的字（英文、数字、符号）保留原版字形，只补中文。适合按钮、分数字体 |
| `cjk_scale` | 只放大中文（≥U+2E80），围绕字身中心缩放，按钮里仍居中。不同字体设计比例不同，用 `try` 对比着调 |
| `zero_space` | 空格做成近乎零宽，U+00A0 作可见空格。**必须配合翻译工具**，见下文 |
| `fallback` | 主字体缺字时依次补字的字体（可写在顶层作为默认） |
| `install_as` | 装到游戏 assets 下的哪些文件名（可多个） |

路径都相对于 `fonts.json`，支持 `%LOCALAPPDATA%` 这类环境变量。以 `_` 开头的键是注释。

## 引擎特性（实测，汉化时会踩的坑）

- **字号**：引擎按大写 H 的高度 × 约 1.666 来定字号，所以用 `original` 对齐 H 高即可让中文和原版字号一致。
- **中文折行**：引擎按空格折行是准的；但没有空格的中文会**超出边界后才折行**，每行多塞一个字，居中文本两侧被裁。
  解决办法（`zero_space`）：
  - 字体里空格宽度设为 1（几乎看不见），U+00A0 保留原空格宽度；
  - 写入译文时，在中文字之间插入普通空格作为折行点；
  - 在 `，。！？、；：）》」』”’…—～` 等标点**之前**、`（《「『“‘` **之后**不插，顺便实现避头尾；
  - 原文中真正要显示的空格换成 U+00A0；纯英文字符串的空格也都换成 U+00A0。
- **漫画对白**（Soap Opera Dash 实测）：游戏会优先用 Flash 播放 `comic/*.swf`，swf 内嵌英文字体，中文气泡全空。
  把 swf 移走后游戏会退回到“整页 PNG + XML 文字框”模式，用游戏自己的字体渲染，中文正常。
- **文件头度量**：原版字体文件头有 ascent / descent / linegap；Font Maker 生成的全为 0，引擎也能用。

## 其他命令

```
python fonttool.py info 字体.mvec --has 要检查的字      字数、度量、是否零宽空格模式、缺字
python fonttool.py preview a.mvec b.mvec --text 文字    渲染对比图
```

## MVC4 格式

见 `mvec.py` 开头的说明。简要：

```
文件头  "MVC4"  u16 字数  u16 ascent  u16 descent  u16 linegap
字符表  每项 18 字节：u32 码位, i16 xmin xmax ymin ymax advance, u32 字形数据偏移
字形    04 x y = moveTo（首个轮廓后跟 02 01）  05 x y = lineTo
        06 cx cy x y = 二次曲线  08 = 结束；坐标 i16，y 向下
```

## 字体授权

转换后的 `.mvec` 仍是原字体的衍生品，随汉化补丁分发前请确认授权：
SIL OFL 等开源字体可以分发（需附协议原文）；商业字体（如华康、方正、汉仪的大部分字体）通常不允许。
