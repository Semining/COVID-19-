#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
covid_pipeline.py
=================
COVID-19 공공데이터 자동화 파이프라인

[업그레이드 포인트]
  Before: 교수님 GitHub 정적 CSV 수동 로드
  After:  CDC 정부 공식 Socrata API 자동 수집 + 로컬 캐시 + 리포트 자동 저장

Data Source: CDC Socrata Open Data API
  https://data.cdc.gov/resource/9mfq-cb36.json
  (API Key 불필요, 무료 공개 API)

Author  : Semin Seo
Course  : MIS433 Python Programming — George Mason University
Version : 2.0 (Automated Pipeline)
"""

import sys
import io
import requests
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import folium
import warnings
from pathlib import Path
from datetime import date

# Windows 터미널 cp949 인코딩 문제 방지 — UTF-8 강제
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")
plt.style.use("ggplot")


# ═══════════════════════════════════════════════════════════
# 1. 상수 및 설정
# ═══════════════════════════════════════════════════════════

CDC_API_URL   = "https://data.cdc.gov/resource/pwn4-m3yp.json"   # Weekly Cases & Deaths by State
CACHE_DIR     = Path("./covid_cache")
OUTPUT_DIR    = Path("./covid_output")

# 주 전체 이름 → CDC API 약어 매핑
STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District Of Columbia": "DC",
}

# Option 2: 주별 중심 좌표 (지도 중심 설정용)
STATE_CENTERS = {
    "Virginia": [37.43, -78.66], "California": [36.78, -119.42],
    "Texas": [31.97, -99.90], "New York": [42.17, -74.95],
    "Florida": [27.66, -81.52], "Illinois": [40.35, -88.99],
    "Washington": [47.40, -121.49], "Pennsylvania": [40.59, -77.21],
    "Ohio": [40.39, -82.76], "Georgia": [32.17, -82.90],
    "North Carolina": [35.63, -79.81], "Michigan": [43.33, -84.54],
    "New Jersey": [40.30, -74.52], "Arizona": [33.73, -111.43],
    "Massachusetts": [42.23, -71.53], "Tennessee": [35.86, -86.35],
    "Indiana": [39.85, -86.26], "Missouri": [38.46, -92.29],
    "Maryland": [39.06, -76.80], "Wisconsin": [44.27, -89.62],
    "Colorado": [39.33, -105.55], "Minnesota": [45.69, -93.90],
    "South Carolina": [33.86, -80.95], "Alabama": [32.79, -86.83],
    "Louisiana": [31.17, -91.87], "Kentucky": [37.67, -84.65],
    "Oregon": [43.93, -120.56], "Oklahoma": [35.57, -96.93],
    "Connecticut": [41.60, -72.75], "Iowa": [42.08, -93.50],
    "Utah": [39.32, -111.09], "Nevada": [38.31, -117.06],
    "Arkansas": [34.97, -92.37], "Mississippi": [32.74, -89.68],
    "Kansas": [38.53, -96.73], "New Mexico": [34.52, -105.87],
    "Nebraska": [41.49, -99.90], "Idaho": [44.24, -114.48],
    "West Virginia": [38.49, -80.95], "Hawaii": [19.74, -155.84],
    "New Hampshire": [43.45, -71.56], "Maine": [44.69, -69.38],
    "Montana": [47.03, -110.45], "Rhode Island": [41.68, -71.51],
    "Delaware": [38.91, -75.53], "South Dakota": [44.30, -99.44],
    "North Dakota": [47.53, -99.78], "Alaska": [64.20, -153.49],
    "Vermont": [44.09, -72.67], "Wyoming": [43.07, -107.29],
    "District Of Columbia": [38.91, -77.02],
}


# ═══════════════════════════════════════════════════════════
# 2. DataFetcher — CDC API 호출 및 캐시 관리
# ═══════════════════════════════════════════════════════════

class DataFetcher:
    """
    CDC Socrata API에서 COVID-19 데이터를 자동으로 수집합니다.

    [자동화 포인트]
      - 당일 캐시 파일이 있으면 API 미호출 (중복 요청 방지)
      - 없으면 CDC API에서 실시간 데이터 수집 후 캐시 저장
      - 캐시 파일명: covid_cache/{STATE}_{YYYY-MM-DD}.csv
    """

    def __init__(self):
        CACHE_DIR.mkdir(exist_ok=True)
        OUTPUT_DIR.mkdir(exist_ok=True)

    def fetch(self, state_name: str) -> pd.DataFrame:
        """주 이름으로 CDC 데이터 가져오기 (캐시 우선)"""
        abbr = STATE_ABBR.get(state_name.title())
        if not abbr:
            raise ValueError(
                f"'{state_name}' 주를 찾을 수 없습니다.\n"
                f"영어 전체 이름으로 입력해주세요. (예: Virginia, California)"
            )

        cache_file = CACHE_DIR / f"{abbr}_{date.today()}.csv"

        # ── 캐시 히트: 오늘 이미 수집한 데이터 재사용
        if cache_file.exists():
            print(f"  ✓ [캐시 사용] {cache_file.name}")
            df = pd.read_csv(cache_file, parse_dates=["start_date"])
            return df

        # ── 캐시 미스: CDC API 실시간 호출
        print(f"  → [CDC API 호출] state={abbr} (2020-01-01 ~ 2021-12-31)")

        # ※ Socrata의 $SoQL 파라미터는 URL에 직접 포함해야 $ 인코딩 문제 없음
        query = (
            f"?state={abbr}"
            f"&$order=start_date"
            f"&$limit=500"
            f"&$where=start_date >= '2020-01-01' AND start_date <= '2021-12-31'"
        )

        try:
            resp = requests.get(CDC_API_URL + query, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"CDC API 호출 실패: {e}")

        data = resp.json()
        if not data:
            raise ValueError(f"{state_name} ({abbr}) 데이터가 없습니다.")

        df = pd.DataFrame(data)
        df["start_date"] = pd.to_datetime(df["start_date"])

        # 숫자 컬럼 변환 (pwn4-m3yp 컬럼명: new_cases, tot_deaths, new_deaths)
        for col in ["tot_cases", "tot_deaths", "new_cases", "new_deaths"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        df = df.sort_values("start_date").reset_index(drop=True)

        # 캐시 저장
        df.to_csv(cache_file, index=False)
        print(f"  ✓ [캐시 저장] {cache_file.name} ({len(df)}행)")

        return df


# ═══════════════════════════════════════════════════════════
# 3. DataAnalyzer — 통계 분석 (논리 오류 3개 수정 적용)
# ═══════════════════════════════════════════════════════════

class DataAnalyzer:
    """
    COVID-19 데이터를 분석합니다.

    [수정된 논리 오류]
      Bug 1 (average_daily_cases): 원본은 누적값/날짜수 → 의미 없는 수치
                                   수정: CDC new_case 컬럼 직접 평균
      Bug 2 (total_cases_overall): 원본은 2020 누적 + 2021 누적 = 2배 과대평가
                                   수정: 2021 최종 누적값만 사용
    """

    @staticmethod
    def first_case_date(df: pd.DataFrame) -> pd.Timestamp:
        """첫 확진자 발생일"""
        positive = df[df["tot_cases"] > 0]
        return positive["start_date"].min() if not positive.empty else df["start_date"].min()

    @staticmethod
    def annual_stats(df: pd.DataFrame, year: int) -> dict:
        """연간 통계 (버그 수정 버전) — 주별(weekly) 데이터 기준"""
        yearly = df[df["start_date"].dt.year == year].sort_values("start_date")
        if yearly.empty:
            return {}

        # 총 누적값 (해당 연도 마지막 주 기준)
        total_cases  = yearly["tot_cases"].iloc[-1]
        total_deaths = yearly["tot_deaths"].iloc[-1]

        # ✅ Bug 1 수정: new_cases/new_deaths 컬럼 직접 평균 (주간 평균 신규 확진)
        #    (원본: tot_cases / 날짜수 → 누적 부하 평균이라 의미 없음)
        avg_weekly_cases  = yearly["new_cases"].mean()
        avg_weekly_deaths = yearly["new_deaths"].mean()

        return {
            "total_cases":        total_cases,
            "total_deaths":       total_deaths,
            "avg_daily_cases":    avg_weekly_cases,   # 키 유지 (출력 포맷 재활용)
            "avg_daily_deaths":   avg_weekly_deaths,
        }

    @staticmethod
    def overall_stats(df: pd.DataFrame) -> dict:
        """
        전체 기간 통계 (버그 수정 버전)

        ✅ Bug 2 수정: 2021 최종 누적값 = 전체 통산 합계
           (원본: 2020 누적 + 2021 누적 → 2020년 데이터 이중 계산 → 약 2배 과대)
        """
        last_row = df.sort_values("start_date").iloc[-1]
        return {
            "total_cases":  last_row["tot_cases"],   # ✅ 마지막 누적값 = 실제 전체 합계
            "total_deaths": last_row["tot_deaths"],
        }

    @staticmethod
    def time_series(df: pd.DataFrame):
        """시계열 데이터 반환 (누적 + 주간 신규, 음수 방어 포함)"""
        s = df.sort_values("start_date").set_index("start_date")
        return (
            s["tot_cases"],
            s["new_cases"].clip(lower=0),    # 데이터 수정으로 인한 음수 방어
            s["tot_deaths"],
            s["new_deaths"].clip(lower=0),
        )


# ═══════════════════════════════════════════════════════════
# 4. ReportSaver — 자동 리포트 저장
# ═══════════════════════════════════════════════════════════

class ReportSaver:
    """
    분석 결과를 자동으로 파일에 저장합니다.

    [자동화 포인트]
      - PNG  : covid_output/{State}_{YYYY-MM-DD}_report.png
      - CSV  : covid_output/{State}_{YYYY-MM-DD}_stats.csv
      - HTML : covid_output/{State}_{YYYY-MM-DD}_map.html
    """

    @staticmethod
    def save_chart(fig, state_name: str):
        path = OUTPUT_DIR / f"{state_name.replace(' ', '_')}_{date.today()}_report.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"  ✓ [자동 저장] 차트: {path}")

    @staticmethod
    def save_stats_csv(stats_by_year: dict, state_name: str):
        rows = [
            {
                "state":            state_name,
                "year":             year,
                "total_cases":      int(s["total_cases"]),
                "total_deaths":     int(s["total_deaths"]),
                "avg_daily_cases":  round(s["avg_daily_cases"], 2),
                "avg_daily_deaths": round(s["avg_daily_deaths"], 2),
            }
            for year, s in stats_by_year.items()
        ]
        path = OUTPUT_DIR / f"{state_name.replace(' ', '_')}_{date.today()}_stats.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        print(f"  ✓ [자동 저장] 통계 CSV: {path}")

    @staticmethod
    def save_map(map_obj, state_name: str):
        path = OUTPUT_DIR / f"{state_name.replace(' ', '_')}_{date.today()}_map.html"
        map_obj.save(str(path))
        print(f"  ✓ [자동 저장] 지도 HTML: {path}")


# ═══════════════════════════════════════════════════════════
# 5. Visualizer — 시각화
# ═══════════════════════════════════════════════════════════

class Visualizer:

    @staticmethod
    def plot_timeseries(df: pd.DataFrame, state: str, name: str):
        """2×2 subplot: 일일 신규 확진, 누적 확진, 일일 신규 사망, 누적 사망"""
        cum_cases, daily_cases, cum_deaths, daily_deaths = DataAnalyzer.time_series(df)

        fig, axs = plt.subplots(2, 2, figsize=(14, 9))

        axs[0, 0].bar(daily_cases.index, daily_cases.values,
                      color="steelblue", alpha=0.7, width=1)
        axs[0, 0].set_title("Weekly New Cases")

        axs[0, 1].plot(cum_cases.index, cum_cases.values,
                       color="steelblue", linewidth=1.5)
        axs[0, 1].set_title("Cumulative Cases")

        axs[1, 0].bar(daily_deaths.index, daily_deaths.values,
                      color="firebrick", alpha=0.7, width=1)
        axs[1, 0].set_title("Weekly New Deaths")

        axs[1, 1].plot(cum_deaths.index, cum_deaths.values,
                       color="firebrick", linewidth=1.5)
        axs[1, 1].set_title("Cumulative Deaths")

        for ax in axs.flat:
            ax.set_xlabel("Date")
            ax.set_ylabel("Count")
            ax.tick_params(axis="x", rotation=45)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

        plt.suptitle(
            f"{state} COVID-19 Report for {name}\n"
            f"Data Source: CDC Socrata API  |  2020–2021",
            fontsize=13, fontweight="bold",
        )
        plt.tight_layout()
        return fig

    @staticmethod
    def plot_choropleth(df: pd.DataFrame, state: str) -> folium.Map:
        """주(State) 위치에 통계 팝업을 표시하는 인터랙티브 지도"""
        last = df.sort_values("start_date").iloc[-1]
        center = STATE_CENTERS.get(state, [39.5, -98.35])

        m = folium.Map(location=center, zoom_start=7, tiles="CartoDB positron")

        popup_html = f"""
        <div style='font-family:sans-serif; min-width:200px'>
          <h4 style='margin:0 0 8px 0'>{state}</h4>
          <hr style='margin:4px 0'>
          <b>As of {last['start_date'].strftime('%Y-%m-%d')}</b><br>
          Total Cases:  {int(last['tot_cases']):,}<br>
          Total Deaths: {int(last['tot_deaths']):,}<br>
          <small style='color:gray'>Source: CDC Socrata API</small>
        </div>
        """

        folium.Marker(
            location=center,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{state} — Click for stats",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(m)

        return m


# ═══════════════════════════════════════════════════════════
# 6. main
# ═══════════════════════════════════════════════════════════

def main():
    BANNER = "=" * 58
    print(BANNER)
    print("  COVID-19 Automated Data Pipeline v2.0")
    print("  Data Source : CDC Socrata Open Data API")
    print("  Cache Dir   : ./covid_cache/")
    print("  Output Dir  : ./covid_output/")
    print(BANNER)

    name  = input("\nHello. Please enter your name: ").strip()
    state = input(
        "\nWhich state's COVID-19 data would you like?\n"
        "  Enter the full state name (e.g., Virginia): "
    ).strip().title()

    if state not in STATE_ABBR:
        print(f"\n❌ '{state}' not found. Check spelling (e.g., 'Virginia', 'New York').")
        return

    # ── 데이터 수집 ──────────────────────────────────────
    print(f"\n{'─'*58}")
    print(f"  Fetching data for {state} ...")
    print(f"{'─'*58}")

    fetcher = DataFetcher()
    df = fetcher.fetch(state)

    # ── 통계 분석 ─────────────────────────────────────────
    first_date = DataAnalyzer.first_case_date(df)
    print(f"\n📅 Day 0 of COVID-19 in {state}: "
          f"{first_date.strftime('%B %d, %Y')}")

    print(f"\n{'─'*58}")
    print(f"  {state} — Annual Statistics")
    print(f"{'─'*58}")

    summary_stats = {}
    for year in [2020, 2021]:
        stats = DataAnalyzer.annual_stats(df, year)
        if not stats:
            continue
        summary_stats[year] = stats
        label = f" (from {first_date.strftime('%B %d')})" if year == 2020 else ""
        print(f"\n{year}{label}:")
        print(f"  - Total reported cases:    {stats['total_cases']:>14,.0f}")
        print(f"  - Avg weekly new cases:    {stats['avg_daily_cases']:>14,.1f}")
        print(f"  - Total reported deaths:   {stats['total_deaths']:>14,.0f}")
        print(f"  - Avg weekly new deaths:   {stats['avg_daily_deaths']:>14,.1f}")

    overall = DataAnalyzer.overall_stats(df)
    print(f"\n{'─'*58}")
    print(f"  Overall Totals in {state} (as of Dec 31, 2021):")
    print(f"{'─'*58}")
    print(f"  - Total cases:   {overall['total_cases']:>14,.0f}")
    print(f"  - Total deaths:  {overall['total_deaths']:>14,.0f}")

    # ── 시각화 선택 ───────────────────────────────────────
    print(f"\n{'─'*58}")
    print(f"\n{name}, please select a visualization option:\n")
    print(f"  1. Time-series subplots")
    print(f"     Daily new + cumulative cases/deaths (2020–2021)")
    print(f"\n  2. Interactive state map")
    print(f"     Summary popup with total stats")
    choice = input("\nEnter your choice (1 or 2): ").strip()

    saver = ReportSaver()
    print()

    if choice == "1":
        print("  Generating time-series charts ...")
        fig = Visualizer.plot_timeseries(df, state, name)
        saver.save_chart(fig, state)
        saver.save_stats_csv(summary_stats, state)
        plt.show()

    elif choice == "2":
        print("  Generating interactive map ...")
        m = Visualizer.plot_choropleth(df, state)
        saver.save_map(m, state)
        map_path = OUTPUT_DIR / f"{state.replace(' ', '_')}_{date.today()}_map.html"
        print(f"\n  Open this file in your browser to view the map:")
        print(f"  {map_path.resolve()}")

    else:
        print("  Invalid choice. Please enter 1 or 2.")
        return

    print(f"\n{'═'*58}")
    print(f"  ✅ Pipeline complete!")
    print(f"  Reports saved to: {OUTPUT_DIR.resolve()}")
    print(f"{'═'*58}\n")


if __name__ == "__main__":
    main()
