@echo off
chcp 65001 > nul

set PYTHON=C:\Users\mypc\anaconda3\python.exe
set SCRIPT=C:\Users\mypc\Documents\covid-pipeline\covid_pipeline.py
set OUTDIR=C:\Users\mypc\Documents\covid-pipeline\covid_output
set LOGFILE=C:\Users\mypc\Documents\covid-pipeline\pipeline_log.txt

echo [%date% %time%] Pipeline started >> "%LOGFILE%"
echo Running COVID-19 Pipeline...
echo.

%PYTHON% "%SCRIPT%" --state Virginia --name Semin --option 1 >> "%LOGFILE%" 2>&1
echo [1/3] Virginia done.

%PYTHON% "%SCRIPT%" --state California --name Semin --option 1 >> "%LOGFILE%" 2>&1
echo [2/3] California done.

%PYTHON% "%SCRIPT%" --state Texas --name Semin --option 1 >> "%LOGFILE%" 2>&1
echo [3/3] Texas done.

echo [%date% %time%] Pipeline finished >> "%LOGFILE%"
echo.
echo =============================================
echo  Pipeline complete!
echo  Reports: %OUTDIR%
echo  Log    : %LOGFILE%
echo =============================================
cmd /k
