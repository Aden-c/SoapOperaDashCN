@echo off
rem 双击无效，请在命令行中使用：fonttool.bat build -p 项目\fonts.json
python -X utf8 "%~dp0fonttool.py" %*
