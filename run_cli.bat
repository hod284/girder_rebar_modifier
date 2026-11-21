@echo off
chcp 65001 > nul
cd /d "%~dp0"
python src\modify_rebar.py input\girder_rebar.ifc output\girder_rebar_D19x5.ifc --size 19 --count 5 --report output\change_report.json
python src\verify_rebar.py input\girder_rebar.ifc output\girder_rebar_D19x5.ifc --png docs\section_before_after.png
pause
