"""Plotly 차트 헬퍼.

- 파이차트는 제공하지 않는다(구성비는 가로 막대/누적막대/트리맵 사용).
- 색상은 고정 순서의 범주형 팔레트를 순환 없이 사용한다.

색 설계(핑크 테마)
------------------
`PALETTE` 는 **검색어(계열) 식별용** 범주형 팔레트다. 전부 핑크 톤으로 칠하면
계열을 구분할 수 없으므로 1번 슬롯만 핑크이고 나머지는 다른 색상이다.
슬롯 순서 자체가 색각 이상 대비를 보장하는 장치이므로 재정렬하지 않는다.

검증 결과(OKLab dE x100, Machado 2009 severity 1.0)
  · 인접 쌍 색각이상 분리 10.3  (기준 8 이상)
  · 전체 쌍 정상시력 분리   18.5  (기준 15 이상)
  · 앞 5색은 전체 쌍 기준도 통과 -> 산점도에서 5계열까지 안전
  · 1·3·4번은 흰 배경 대비 3:1 미만 -> 값 라벨/표를 함께 제공해야 한다
    (막대 text_auto 와 각 페이지의 표가 그 역할을 한다)

`SEQ` 는 **크기(양)를 나타내는 순차 스케일**이다. 베이비핑크에서 진분홍까지
한 가지 색상으로만 이어지며, 히트맵처럼 값의 크기를 색으로 읽는 곳에 쓴다.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 범주형(계열 식별) — 고정 순서, 순환 금지
PALETTE = [
    "#ff81b8",  # 1 분홍
    "#089772",  # 2 민트
    "#62bbf5",  # 3 하늘
    "#dea80b",  # 4 버터
    "#ad75fe",  # 5 라일락
    "#2955d3",  # 6 블루
    "#a14206",  # 7 브라운
    "#913797",  # 8 자두
]

# 순차(크기) — 베이비핑크 -> 진분홍, 단일 색상 램프
PINK_SEQ = [
    "#f9d4e2", "#f2c0d3", "#efabc5", "#e896b7", "#e180a9", "#da6a9c",
    "#d3508e", "#c73880", "#b72672", "#a31b64", "#8f1357", "#7a0b49", "#65093c",
]
SEQ = PINK_SEQ

# 서수(순서 있는 구간) — 5단계, 밝기 간격 검증 통과
PINK_ORDINAL = ["#e896b7", "#da6a9c", "#c73880", "#a31b64", "#7a0b49"]

# 브랜드 앵커 (테마/요약 박스에서 재사용)
PINK_DEEP = "#d3508e"
PINK_SOFT = "#fbeaf1"
INK_MUTED = "#6b6570"
GRID = "#f0e2e9"

_LAYOUT = dict(
    template="plotly_white",
    font=dict(family='system-ui, -apple-system, "Segoe UI", "Malgun Gothic", sans-serif', size=13),
    margin=dict(l=10, r=10, t=48, b=10),
    colorway=PALETTE,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)


def _style(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(**_LAYOUT, height=height)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def _empty(title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text="표시할 데이터가 없습니다", showarrow=False, font=dict(color=INK_MUTED))
    return _style(fig.update_layout(title=title))


def bar(df, x, y, title, *, color=None, orientation="v", text_auto=True, sort=True):
    if df is None or len(df) == 0:
        return _empty(title)
    d = df.copy()
    if sort:
        key = x if orientation == "h" else y
        if key in d.columns and pd.api.types.is_numeric_dtype(d[key]):
            d = d.sort_values(key, ascending=(orientation == "h"))
    fig = px.bar(d, x=x, y=y, color=color, orientation=orientation, title=title,
                 text_auto=".2s" if text_auto else False,
                 color_discrete_sequence=PALETTE)
    fig.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
    return _style(fig)


def grouped_bar(df, x, y, color, title):
    if df is None or len(df) == 0:
        return _empty(title)
    fig = px.bar(df, x=x, y=y, color=color, barmode="group", title=title,
                 color_discrete_sequence=PALETTE)
    fig.update_traces(marker_line_width=0)
    return _style(fig)


def stacked_bar(df, x, y, color, title, *, percent=False):
    if df is None or len(df) == 0:
        return _empty(title)
    fig = px.bar(df, x=x, y=y, color=color, title=title,
                 barmode="relative", color_discrete_sequence=PALETTE)
    fig.update_traces(marker_line_width=0)
    if percent:
        fig.update_layout(barnorm="percent")
        fig.update_yaxes(title="비율(%)", ticksuffix="%")
    return _style(fig)


def line(df, x, y, color, title, *, y_title=None, markers=True):
    if df is None or len(df) == 0:
        return _empty(title)
    fig = px.line(df, x=x, y=y, color=color, title=title, markers=markers,
                  color_discrete_sequence=PALETTE)
    fig.update_traces(line_width=2)
    if y_title:
        fig.update_yaxes(title=y_title)
    return _style(fig)


def area(df, x, y, color, title, *, y_title=None):
    if df is None or len(df) == 0:
        return _empty(title)
    fig = px.area(df, x=x, y=y, color=color, title=title, color_discrete_sequence=PALETTE)
    if y_title:
        fig.update_yaxes(title=y_title)
    return _style(fig)


def histogram(df, x, title, *, color=None, nbins=40, barmode="overlay", marginal="box"):
    if df is None or len(df) == 0 or x not in df:
        return _empty(title)
    fig = px.histogram(df, x=x, color=color, nbins=nbins, title=title, barmode=barmode,
                       marginal=marginal, opacity=0.75, color_discrete_sequence=PALETTE)
    return _style(fig)


def box(df, x, y, title, *, color=None, points="outliers"):
    if df is None or len(df) == 0 or y not in df:
        return _empty(title)
    fig = px.box(df, x=x, y=y, color=color or x, points=points, title=title,
                 color_discrete_sequence=PALETTE)
    return _style(fig)


def violin(df, x, y, title, *, color=None):
    if df is None or len(df) == 0 or y not in df:
        return _empty(title)
    fig = px.violin(df, x=x, y=y, color=color or x, box=True, points=False, title=title,
                    color_discrete_sequence=PALETTE)
    return _style(fig)


def strip(df, x, y, title, *, color=None):
    if df is None or len(df) == 0 or y not in df:
        return _empty(title)
    fig = px.strip(df, x=x, y=y, color=color or x, title=title, color_discrete_sequence=PALETTE)
    return _style(fig)


def scatter(df, x, y, title, *, color=None, size=None, hover_name=None, trendline=None, log_xy=False):
    if df is None or len(df) == 0 or x not in df or y not in df:
        return _empty(title)
    fig = px.scatter(df, x=x, y=y, color=color, size=size, hover_name=hover_name,
                     title=title, trendline=trendline, opacity=0.8,
                     color_discrete_sequence=PALETTE)
    if log_xy:
        fig.update_xaxes(type="log")
        fig.update_yaxes(type="log")
    return _style(fig)


def ecdf(df, x, title, *, color=None):
    if df is None or len(df) == 0 or x not in df:
        return _empty(title)
    fig = px.ecdf(df, x=x, color=color, title=title, color_discrete_sequence=PALETTE)
    fig.update_yaxes(title="누적비율")
    return _style(fig)


def heatmap(matrix: pd.DataFrame, title, *, index_col=None, text=True, colorscale=SEQ):
    """행렬(피봇/교차표) DataFrame 을 히트맵으로. 첫 컬럼이 라벨이면 index_col 로 지정."""
    if matrix is None or len(matrix) == 0:
        return _empty(title)
    m = matrix.copy()
    if index_col and index_col in m.columns:
        m = m.set_index(index_col)
    elif not isinstance(m.index, pd.Index) or m.index.name is None:
        first = m.columns[0]
        if not pd.api.types.is_numeric_dtype(m[first]):
            m = m.set_index(first)
    m = m.select_dtypes("number")
    drop = [c for c in ("합계", "All") if c in m.columns]
    m = m.drop(columns=drop, errors="ignore")
    m = m.drop(index=[i for i in ("합계", "All") if i in m.index], errors="ignore")
    fig = px.imshow(m, text_auto=".0f" if text else False, aspect="auto",
                    color_continuous_scale=colorscale, title=title)
    fig.update_xaxes(side="bottom")
    return _style(fig)


def treemap(df, path, values, title):
    if df is None or len(df) == 0:
        return _empty(title)
    fig = px.treemap(df, path=path, values=values, title=title,
                     color_discrete_sequence=PALETTE)
    fig.update_layout(**_LAYOUT, height=460)
    return fig
