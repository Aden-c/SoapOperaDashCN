"""制作人员名单：以 backup/credits.txt 为底，翻译职位与说明句，人名保留英文
   python credits_tool.py   → 写入 Game Files/assets/credits.txt"""
import os, re
from strings_tool import add_breaks

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'backup', 'credits.txt')
DST = os.path.join(HERE, '..', 'Game Files', 'assets', 'credits.txt')

ROLES = {
    'Managing Director': '总经理', 'Creative Director': '创意总监', 'Project Manager': '项目经理',
    'Producer': '制作人', 'Lead Programmer': '主程序', 'Programmers': '程序',
    'Lead Game Designer': '首席游戏设计', 'Designer': '设计', 'Additional design by': '额外设计',
    'Lead Artist': '首席美术', 'Artists': '美术', 'Additional art by': '额外美术',
    'Special Thanks to:': '特别感谢', 'Special Thanks': '特别感谢',
    'Design Consultant': '设计顾问', 'Art Consultant': '美术顾问', 'Engineering Consultant': '技术顾问',
    'Senior Producers': '高级制作人', 'Game Design Manager': '游戏设计经理', 'Art Director': '美术总监',
    'Quality Assurance': '质量保证', 'QA Manager': '质量保证经理', 'Chief Creative Officer': '首席创意官',
    'VP, Executive Producer': '副总裁、执行制作人', 'VP, Engineering': '技术副总裁', 'VP, Marketing': '市场副总裁',
    'Playground Game Engine': 'Playground 游戏引擎', 'Product Marketing': '产品营销', 'Audio': '音频',
}
LINES = {
    'Rapid and creative development of this game was facilitated by Bamtang\'s SwitPC technologies.':
        '本游戏借助 Bamtang 的 SwitPC 技术，实现了快速而富有创意的开发。',
    'This game was built using the Playground SDK™': '本游戏使用 Playground SDK™ 制作',
    'Copyright © 2010 PlayFirst, Inc.  All rights reserved.': 'Copyright © 2010 PlayFirst, Inc. 保留一切权利。',
    'PlayFirst, Soap Opera Dash, DinerTown, and all related titles, logos, and characters are trademarks of PlayFirst, Inc.':
        'PlayFirst、Soap Opera Dash、DinerTown 及所有相关名称、标志和角色均为 PlayFirst, Inc. 的商标。',
    'Soap Opera Dash and PlayFirst are registered in the U.S. and other countries.':
        'Soap Opera Dash 和 PlayFirst 已在美国及其他国家注册。',
    'Bamtang is a trademark of Johnston Technology EIRL.': 'Bamtang 是 Johnston Technology EIRL 的商标。',
    'Protected by copyright and licenses restricting use, copying, distribution and decompilation.':
        '受版权及许可协议保护，限制使用、复制、分发和反编译。',
    'Morgan Condict (Project Lead)': 'Morgan Condict（项目负责人）',
    'David Parks (Lead)': 'David Parks（负责人）',
}


# 汉化人员，放在名单最前面（职位标题每行别超过 ~10 个字，显示区只有 200px 宽）
HANHUA = [
    '[[中文汉化]]',
    '',
    '[审校、解包]',
    '艾登',
    '',
    '[中文标志设计]',
    '艾登',
    '',
    '[初译、图片处理]',
    'Claude Opus 5.5',
    '',
    '[字体与排版技术]',
    'Claude Opus 5.5',
    '',
    '',
]


def convert(line):
    s = line.strip()
    m = re.fullmatch(r'\[(.*)\]', s)
    if m and m.group(1) in ROLES:
        s = '[' + ROLES[m.group(1)] + ']'
    elif s in LINES:
        s = LINES[s]
    if re.search(r'[一-鿿]', s):
        return add_breaks(s)
    # 纯英文（人名等）：空格可见且不折行，只在逗号后允许折行
    return s.replace(' ', ' ').replace(', ', ',  ')


text = open(SRC, encoding='utf-8-sig', newline='').read()
lines = text.split('\r\n')
# 去掉开头的破解组留言（[[Cracked By]] 到其后第一个空行），它不属于原版名单
if '[[Cracked By]]' in lines[0]:
    lines = lines[lines.index('') + 1:]
out = '\r\n'.join(convert(l) for l in HANHUA + lines)
open(DST, 'w', encoding='utf-8-sig', newline='').write(out)
print('credits.txt 已写入')
