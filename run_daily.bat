@echo off
:: COVID-19 파이프라인 자동 실행 스크립트
:: 작업 스케줄러가 이 파일을 실행합니다

set PYTHON=C:\Users\mypc\anaconda3\python.exe
set SCRIPT=C:\Users\mypc\Documents\covid-pipeline\covid_pipeline.py
set OUTDIR=C:\Users\mypc\Documents\covid-pipeline\covid_output
set LOGFILE=C:\Users\mypc\Documents\covid-pipeline\pipeline_log.txt

echo [%date% %time%] Pipeline started >> "%LOGFILE%"

:: 원하는 주 목록을 아래에 추가/수정하세요
%PYTHON% "%SCRIPT%" --state Virginia --name Semin --option 1 >> "%LOGFILE%" 2>&1
%PYTHON% "%SCRIPT%" --state California --name Semin --option 1 >> "%LOGFILE%" 2>&1
%PYTHON% "%SCRIPT%" --state Texas --name Semin --option 1 >> "%LOGFILE%" 2>&1

echo [%date% %time%] Pipeline finished >> "%LOGFILE%"
echo Reports saved to: %OUTDIR%
