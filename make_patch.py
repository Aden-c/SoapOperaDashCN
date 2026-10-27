"""打包汉化补丁（给玩家下载的 zip）

  python make_patch.py 1.0      → dist/SoapOperaDashCN_v1.0.zip

内容：
  cn_patch/assets/...   改动过的游戏文件（从当前游戏目录取，请先 apply / build 好）
  安装汉化.bat           备份原版 → 复制补丁 → 漫画 swf 改名（让漫画走 PNG+XML 模式才能显示中文）
  卸载汉化.bat           从备份还原
  使用说明.txt
  字体授权/              各字体的版权与授权协议
"""
import datetime, json, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, '..', 'Game Files', 'assets')
FONTS_CFG = os.path.join(HERE, 'fonts.json')

# 补丁包含的文件（相对 assets）
FILES = [
    'strings.xml',
    'credits.txt',
    'font/avenirltstdmedium.mvec',
    'font/highlanderstdbolditalic.mvec',
    'font/florastdbold.mvec',
    'font/florastd-bold.mvec',
    'font/domcasualstd.mvec',
    'scripts/mainmenu.lua',
    'scripts/metamap.lua',
    'animfx/mainmenu/sod_mainmenu_pieces01.png',
    'animfx/slate_big/atbt_slatebig.png',
]
COMIC_SWF = [f'comic/atbt_comic_venue{i}_init.swf' for i in range(1, 8)]

INSTALL_BAT = r'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 美女肥皂剧 汉化补丁 安装
if not exist "Soap Opera Dash.exe" (
  echo 没有找到 Soap Opera Dash.exe。
  echo 请把压缩包里的全部内容解压到游戏目录（Soap Opera Dash.exe 所在的文件夹）后再运行。
  pause & exit /b 1
)
if not exist "assets\strings.xml" (
  echo 没有找到 assets\strings.xml。
  echo 本补丁适用于资源为散文件（assets 文件夹）的版本；资源打包在 .pfp 里的版本暂未测试。
  pause & exit /b 1
)
if not exist "cn_backup" (
  echo 正在备份原版文件到 cn_backup ...
  for /f "usebackq delims=" %%f in ("cn_patch\filelist.txt") do (
    if exist "assets\%%f" (
      for %%d in ("cn_backup\assets\%%f") do if not exist "%%~dpd" mkdir "%%~dpd"
      copy /y "assets\%%f" "cn_backup\assets\%%f" >nul
    )
  )
)
echo 正在安装汉化文件 ...
xcopy /e /y /q "cn_patch\assets" "assets\" >nul
for %%f in (assets\comic\*.swf) do ren "%%f" "%%~nxf.bak"
echo.
echo 安装完成！直接运行 Soap Opera Dash.exe 即可。
echo 想恢复英文版，运行“卸载汉化.bat”。
pause
'''

UNINSTALL_BAT = r'''@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 美女肥皂剧 汉化补丁 卸载
if not exist "cn_backup\assets" (
  echo 没有找到备份文件夹 cn_backup，无法还原。
  pause & exit /b 1
)
xcopy /e /y /q "cn_backup\assets" "assets\" >nul
for %%f in (assets\comic\*.swf.bak) do ren "%%f" "%%~nf"
echo 已恢复为英文原版。
pause
'''

README_TXT = '''《美女肥皂剧》(Soap Opera Dash) 中文汉化补丁 v{ver}（{date}）

【安装】
1. 把压缩包里的全部内容解压到游戏目录，也就是 Soap Opera Dash.exe 所在的文件夹。
2. 双击运行「安装汉化.bat」。原版文件会自动备份到 cn_backup 文件夹。

【卸载】
双击运行「卸载汉化.bat」，从 cn_backup 还原英文原版。

【说明】
- 适用于游戏资源为散文件（有 assets 文件夹）的版本，测试版本 1.0.1.128。
- 剧情漫画改为静态图片加文字的方式显示（原版的 Flash 动画无法显示中文），
  安装脚本会把 assets\\comic 下的 .swf 改名为 .swf.bak。
- 本补丁为爱好者汉化，与 PlayFirst、Bamtang 无关。请支持正版游戏。
- 译文与中文标志设计以 CC BY-NC 4.0 授权：可转载、修改，须署名，不得用于商业用途。
  字体授权见「字体授权」文件夹。

【制作】
审校、中文标志设计、解包：艾登
初译、图片处理、字体与排版技术：Claude Opus 5.5

项目主页：https://github.com/Aden-c/SoapOperaDashCN
'''

HARMONY_NOTE = '''HarmonyOS Sans SC（正文字体）

版权归华为终端有限公司所有。依据其授权协议，字体可嵌入应用软件使用，
不得以独立形式重新分发或出售。本补丁中的 avenirltstdmedium.mvec 是将其转换为
本游戏专用格式后嵌入游戏使用的，请勿将其提取作他用。
如需使用该字体，请从华为官方渠道获取：https://developer.huawei.com/consumer/cn/design/resource/
'''


def ofl_body():
    """从本地某个 OFL 字体包里取协议正文（去掉开头的版权行）"""
    ref = os.path.join(HERE, '..', 'Game Files', 'pfp', '参考字体', '站酷快乐体3.53', 'OFL.txt')
    text = open(ref, encoding='utf-8', errors='replace').read()
    i = text.find('This Font Software is licensed under the SIL Open Font License')
    return text[i:] if i >= 0 else text


def font_copyright(path):
    from fontTools.ttLib import TTFont
    f = TTFont(os.path.expandvars(path), fontNumber=0, lazy=True)
    names = f['name']
    for lang in (0x804, 0x409, None):
        for r in names.names:
            if r.nameID == 0 and (lang is None or r.langID == lang):
                return r.toUnicode()
    return ''


def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime('%Y%m%d')
    os.makedirs(os.path.join(HERE, 'dist'), exist_ok=True)
    out = os.path.join(HERE, 'dist', f'SoapOperaDashCN_v{ver}.zip')
    missing = [f for f in FILES if not os.path.exists(os.path.join(ASSETS, f))]
    if missing:
        sys.exit('游戏目录里缺少：' + ', '.join(missing))

    cfg = json.load(open(FONTS_CFG, encoding='utf-8'))
    base = os.path.dirname(FONTS_CFG)
    ofl = ofl_body()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(os.path.join(ASSETS, f), 'cn_patch/assets/' + f)
        z.writestr('cn_patch/filelist.txt', '\r\n'.join(f.replace('/', '\\') for f in FILES) + '\r\n')
        z.writestr('安装汉化.bat', INSTALL_BAT.replace('\n', '\r\n').encode('utf-8'))
        z.writestr('卸载汉化.bat', UNINSTALL_BAT.replace('\n', '\r\n').encode('utf-8'))
        z.writestr('使用说明.txt', README_TXT.format(ver=ver, date=datetime.date.today()).replace('\n', '\r\n'))
        z.writestr('字体授权/HarmonyOS Sans SC.txt', HARMONY_NOTE.replace('\n', '\r\n'))
        for name, f in cfg['fonts'].items():
            src = os.path.expandvars(f['source'])
            src = src if os.path.isabs(src) else os.path.join(base, src)
            if 'HarmonyOS' in src:
                continue
            fam = os.path.splitext(os.path.basename(src))[0]
            z.writestr(f'字体授权/{fam}（{name}）.txt',
                       (f'{fam}\nCopyright: {font_copyright(src)}\n\n{ofl}').replace('\r\n', '\n').replace('\n', '\r\n'))
    size = os.path.getsize(out)
    print(f'已生成 {os.path.relpath(out, HERE)}（{size / 1048576:.1f} MB，{len(FILES)} 个游戏文件）')


if __name__ == '__main__':
    main()
