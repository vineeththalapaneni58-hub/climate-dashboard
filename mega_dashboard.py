# mega_dashboard.py
# Mega Climate Dashboard - 30 World Capitals
# Single scrollable page, no tabs, no dropdowns
# Runs on port 8052
# Usage: python mega_dashboard.py

import os
import webbrowser
import threading
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, dash_table, Input, Output
from sqlalchemy import create_engine, text

DATABASE_URL = "sqlite:///mega_climate.db"

def load_data():
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        query  = text("""
            SELECT c.city, c.region, c.languages, c.timezone,
                   c.latitude, c.longitude, c.attractions,
                   f.date, f.high_c, f.low_c, f.feels_like_c,
                   f.rain_probability, f.weather_condition,
                   f.day_length, f.season, f.climate_risk,
                   f.travel_recommendation, f.travel_score
            FROM mega_forecast f
            JOIN mega_city c ON f.city_id = c.city_id
            ORDER BY c.city, f.date
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        print(f"Loaded {len(df)} rows from database.")
        return df
    except Exception as e:
        print(f"Database error: {e}. Falling back to CSV.")
        return pd.read_csv("data/mega_data.csv")

df       = load_data()
first_d  = df.groupby("city")["date"].min().reset_index()
first_d.columns = ["city","first_date"]
df       = df.merge(first_d, on="city")
today_df = df[df["date"]==df["first_date"]].drop_duplicates(subset="city").copy()
today_df = today_df.sort_values("travel_score", ascending=False).reset_index(drop=True)

REGION_COLORS = {
    "Africa":   "#d35400",
    "Americas": "#2471a3",
    "Asia":     "#1e8449",
    "Europe":   "#6c3483",
    "Oceania":  "#117a65",
}
def rc(r): return REGION_COLORS.get(r,"#888888")

def sc(s):
    if s>=8:   return "#1e8449"
    elif s>=6: return "#d35400"
    elif s>=4: return "#ba4a00"
    else:      return "#c0392b"

def sl(s):
    if s>=8:   return "Excellent"
    elif s>=6: return "Good"
    elif s>=4: return "Fair"
    else:      return "Poor"

def temp_color(t):
    if t is None: return "#888888"
    if t>=40:   return "#7b241c"
    elif t>=35: return "#c0392b"
    elif t>=30: return "#d35400"
    elif t>=25: return "#f0a500"
    elif t>=20: return "#1e8449"
    elif t>=15: return "#2471a3"
    else:       return "#1a5276"

def wi(condition):
    if condition is None: return "🌡️"
    c = str(condition).lower()
    if "clear" in c:      return "☀️"
    elif "mainly" in c:   return "🌤️"
    elif "partly" in c:   return "⛅"
    elif "overcast" in c: return "☁️"
    elif "fog" in c:      return "🌫️"
    elif "drizzle" in c:  return "🌦️"
    elif "rain" in c or "shower" in c: return "🌧️"
    elif "snow" in c:     return "❄️"
    elif "thunder" in c:  return "⛈️"
    else:                 return "🌡️"

def gf(city):
    flags = {
        "Bogota":"🇨🇴","Washington D.C.":"🇺🇸","Nairobi":"🇰🇪",
        "Riyadh":"🇸🇦","New Delhi":"🇮🇳","London":"🇬🇧","Rome":"🇮🇹",
        "Tokyo":"🇯🇵","Canberra":"🇦🇺","Jakarta":"🇮🇩","Berlin":"🇩🇪",
        "Moscow":"🇷🇺","Santiago":"🇨🇱","Mexico City":"🇲🇽","Ottawa":"🇨🇦",
        "Oslo":"🇳🇴","Bangkok":"🇹🇭","Wellington":"🇳🇿","Ulaanbaatar":"🇲🇳",
        "Cairo":"🇪🇬","Lagos":"🇳🇬","Colombo":"🇱🇰","Manila":"🇵🇭",
        "Seoul":"🇰🇷","Kuala Lumpur":"🇲🇾","Athens":"🇬🇷","Budapest":"🇭🇺",
        "Buenos Aires":"🇦🇷","Doha":"🇶🇦","Brasilia":"🇧🇷"
    }
    return flags.get(city,"🌍")

BG     = "#f8f4ef"
CARD   = "#ffffff"
CARD2  = "#f2ede6"
BORDER = "rgba(0,0,0,0.08)"
TEXT   = "#2a1f0e"
MUTED  = "#7a6a50"
HEAD   = "#1a120a"

def build_map():
    fig = go.Figure()
    for rgn in sorted(today_df["region"].unique()):
        sub = today_df[today_df["region"]==rgn]
        fig.add_trace(go.Scattergeo(
            lat=sub["latitude"], lon=sub["longitude"],
            mode="markers+text", name=rgn,
            text=sub["city"],
            textposition="top center",
            textfont=dict(size=8, color=TEXT, family="Arial"),
            marker=dict(size=12, color=rc(rgn),
                        line=dict(width=2, color=CARD), opacity=0.9),
            customdata=sub[["high_c","low_c","weather_condition",
                             "travel_recommendation","rain_probability",
                             "season","travel_score"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "High: %{customdata[0]}C  Low: %{customdata[1]}C<br>"
                "Condition: %{customdata[2]}<br>"
                "Rain: %{customdata[4]}%  Season: %{customdata[5]}<br>"
                "Score: %{customdata[6]}/10<br>"
                "Travel: %{customdata[3]}<extra></extra>"
            )
        ))
    fig.update_layout(
        paper_bgcolor=CARD, margin=dict(r=0,t=0,l=0,b=0),
        showlegend=True,
        legend=dict(bgcolor=CARD, bordercolor=BORDER, borderwidth=1,
                    font=dict(color=TEXT,size=11,family="Arial"),
                    orientation="h", yanchor="bottom", y=1.01,
                    xanchor="left", x=0),
        geo=dict(showland=True, landcolor="#e8e0d0",
                 showocean=True, oceancolor="#d4e8f0",
                 showcoastlines=True, coastlinecolor=BORDER,
                 showframe=False, showcountries=True,
                 countrycolor=BORDER, bgcolor=CARD,
                 showlakes=True, lakecolor="#d4e8f0")
    )
    return fig

def build_donut():
    rc_counts = today_df["region"].value_counts()
    total     = len(today_df)
    fig = go.Figure(go.Pie(
        labels=rc_counts.index, values=rc_counts.values, hole=0.6,
        marker=dict(colors=[rc(r) for r in rc_counts.index],
                    line=dict(color=CARD, width=3)),
        textfont=dict(family="Arial", size=11),
        hovertemplate="<b>%{label}</b><br>%{value} cities<extra></extra>"
    ))
    fig.add_annotation(
        text=f"<b>{total}</b><br>Cities",
        x=0.5, y=0.5,
        font=dict(size=16, family="Arial", color=TEXT),
        showarrow=False
    )
    fig.update_layout(
        paper_bgcolor=CARD,
        font=dict(family="Arial", color=TEXT),
        showlegend=True,
        legend=dict(font=dict(size=11,family="Arial"),
                    bgcolor="rgba(0,0,0,0)", orientation="v", x=1, y=0.5),
        margin=dict(t=10,b=10,l=10,r=80), height=260
    )
    return fig

def build_lollipop():
    srt = today_df.sort_values("travel_score", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=srt["travel_score"], y=[f"{gf(c)}  {c}" for c in srt["city"]],
        orientation="h",
        marker=dict(color=[rc(r) for r in srt["region"]], opacity=0.2),
        width=0.04, showlegend=False, hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=srt["travel_score"],
        y=[f"{gf(c)}  {c}" for c in srt["city"]],
        mode="markers+text",
        text=[f"  {s}" for s in srt["travel_score"]],
        textposition="middle right",
        textfont=dict(size=10, family="Arial", color=TEXT),
        marker=dict(size=14, color=[rc(r) for r in srt["region"]],
                    line=dict(width=2, color=CARD), opacity=0.95),
        showlegend=False,
        customdata=srt[["city","travel_score","region"]].values,
        hovertemplate="<b>%{customdata[0]}</b><br>Score: %{customdata[1]}/10<br>Region: %{customdata[2]}<extra></extra>"
    ))
    fig.update_layout(
        paper_bgcolor=CARD, plot_bgcolor=CARD2,
        font=dict(family="Arial", color=TEXT, size=12),
        xaxis=dict(range=[0,12], gridcolor=BORDER, color=MUTED,
                   title=dict(text="Today's Travel Score",
                              font=dict(color=MUTED,size=11)),
                   tickfont=dict(size=10,family="Arial")),
        yaxis=dict(color=TEXT, tickfont=dict(size=10,family="Arial")),
        margin=dict(t=10,b=40,l=160,r=60),
        barmode="overlay",
        height=max(520, len(srt)*18+80)
    )
    return fig

def build_feels_line():
    srt = today_df.sort_values("high_c", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Actual High C",
        x=[f"{gf(c)} {c}" for c in srt["city"]],
        y=srt["high_c"],
        marker_color=[rc(r) for r in srt["region"]], opacity=0.55,
        hovertemplate="<b>%{x}</b><br>Actual High: %{y}C<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        name="Feels Like C",
        x=[f"{gf(c)} {c}" for c in srt["city"]],
        y=srt["feels_like_c"],
        mode="lines+markers",
        line=dict(color="#c0392b", width=2.5),
        marker=dict(size=8, color="#c0392b", symbol="diamond",
                    line=dict(width=1.5, color=CARD)),
        hovertemplate="<b>%{x}</b><br>Feels Like: %{y}C<extra></extra>"
    ))
    fig.update_layout(
        paper_bgcolor=CARD, plot_bgcolor=CARD2,
        font=dict(family="Arial", color=TEXT, size=12),
        xaxis=dict(gridcolor=BORDER, color=MUTED, tickangle=35,
                   tickfont=dict(size=9,family="Arial")),
        yaxis=dict(gridcolor=BORDER, color=MUTED,
                   title=dict(text="Temperature (C)",
                              font=dict(color=MUTED,size=11)),
                   tickfont=dict(size=10,family="Arial")),
        legend=dict(font=dict(size=11,family="Arial"),
                    bgcolor="rgba(0,0,0,0)",
                    orientation="h", yanchor="bottom",
                    y=1.02, xanchor="right", x=1),
        margin=dict(t=20,b=100,l=60,r=20), height=360
    )
    return fig

def candle_color(rec, score):
    """Color based on travel recommendation and score."""
    if "Highly" in str(rec): return "#1e8449"
    elif str(rec) == "Recommended": return "#27ae60"
    elif "umbrella" in str(rec): return "#d35400"
    else: return "#c0392b"

def build_candlestick(city_name):
    """
    Builds a weather candlestick chart for a given city.
    Body = high to low temperature range
    Color = travel recommendation
    Dashed line = feels like temperature
    Blue dots = rain probability (size proportional)
    """
    city_df = df[df["city"] == city_name].sort_values("date").copy()
    if city_df.empty:
        return go.Figure()

    short_dates = []
    for d in city_df["date"]:
        parts = d.split("-")
        month_names = {"01":"Jan","02":"Feb","03":"Mar","04":"Apr","05":"May",
                       "06":"Jun","07":"Jul","08":"Aug","09":"Sep","10":"Oct",
                       "11":"Nov","12":"Dec"}
        short_dates.append(f"{month_names.get(parts[1], parts[1])} {parts[2]}")
    fig = go.Figure()

    # Draw candle bodies as thick lines
    for i, (_, row) in enumerate(city_df.iterrows()):
        color = candle_color(row["travel_recommendation"], row["travel_score"])
        sd    = short_dates[i]
        fig.add_trace(go.Scatter(
            x=[sd, sd],
            y=[row["low_c"], row["high_c"]],
            mode="lines",
            line=dict(color=color, width=22),
            showlegend=False,
            hovertemplate=(
                f"<b>{sd}</b><br>"
                f"High: {row['high_c']}C<br>"
                f"Low: {row['low_c']}C<br>"
                f"Feels Like: {row['feels_like_c']}C<br>"
                f"Rain: {row['rain_probability']}%<br>"
                f"Score: {row['travel_score']}/10<br>"
                f"{row['travel_recommendation']}<extra></extra>"
            )
        ))
        # High label on top
        fig.add_annotation(
            x=sd, y=row["high_c"],
            text=f"{row['high_c']}",
            showarrow=False,
            yshift=12,
            font=dict(size=9, color=color, family="Arial"),
            xanchor="center"
        )
        # Low label on bottom
        fig.add_annotation(
            x=sd, y=row["low_c"],
            text=f"{row['low_c']}",
            showarrow=False,
            yshift=-12,
            font=dict(size=9, color=color, family="Arial"),
            xanchor="center"
        )

    # Feels like dashed line
    fig.add_trace(go.Scatter(
        x=short_dates,
        y=city_df["feels_like_c"],
        mode="lines+markers",
        name="Feels Like",
        line=dict(color="#555555", width=1.5, dash="dot"),
        marker=dict(size=5, color="#555555"),
        hovertemplate="<b>%{x}</b><br>Feels Like: %{y}C<extra></extra>"
    ))

    # Rain probability dots below chart
    min_temp = city_df["low_c"].min()
    rain_y   = [min_temp - 4] * len(city_df)
    fig.add_trace(go.Scatter(
        x=short_dates,
        y=rain_y,
        mode="markers+text",
        name="Rain %",
        text=[f"{int(r)}%" for r in city_df["rain_probability"]],
        textposition="bottom center",
        textfont=dict(size=9, family="Arial", color="#2471a3"),
        marker=dict(
            size=[max(float(r)/6, 4) for r in city_df["rain_probability"]],
            color="#2471a3",
            opacity=0.65
        ),
        hovertemplate="<b>%{x}</b><br>Rain: %{text}<extra></extra>"
    ))

    fig.update_layout(
        paper_bgcolor=CARD,
        plot_bgcolor=CARD2,
        font=dict(family="Arial", color=TEXT, size=12),
        xaxis=dict(
            gridcolor=BORDER, color=MUTED,
            tickfont=dict(size=11, family="Arial"),
            showgrid=False,
            type="category"
        ),
        yaxis=dict(
            gridcolor=BORDER, color=MUTED,
            title=dict(text="Temperature (C)",
                       font=dict(color=MUTED, size=11)),
            tickfont=dict(size=10, family="Arial")
        ),
        showlegend=True,
        legend=dict(
            font=dict(size=11, family="Arial"),
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1
        ),
        margin=dict(t=30, b=60, l=60, r=20),
        height=380
    )
    return fig
def empty_detail():
    return html.Div([
        html.Div("🗺️", style={"fontSize":"36px","textAlign":"center","marginBottom":"10px"}),
        html.Div("Click any city on the map",
                 style={"color":MUTED,"textAlign":"center",
                        "fontFamily":"Arial","fontSize":"13px"}),
        html.Div("to see full weather profile and attractions",
                 style={"color":"#bbb","textAlign":"center",
                        "fontFamily":"Arial","fontSize":"11px"})
    ], style={"paddingTop":"60px"})

def city_detail(row):
    s     = row["travel_score"]
    color = sc(s)
    label = sl(s)
    icon  = wi(row.get("weather_condition"))
    f     = gf(row["city"])
    attrs = [a for a in str(row.get("attractions","")).split(" | ") if a]
    tc    = ("#1e8449" if "Highly" in str(row.get("travel_recommendation",""))
             else "#c0392b" if "Not" in str(row.get("travel_recommendation",""))
             else "#d35400")
    riskc = "#c0392b" if row.get("climate_risk","") != "No risk" else "#1e8449"

    def ri(lbl, val, vc=TEXT):
        return html.Div([
            html.Span(f"{lbl}  ",
                      style={"color":MUTED,"fontSize":"10px","fontFamily":"Arial",
                             "letterSpacing":"1px","textTransform":"uppercase"}),
            html.Span(str(val),
                      style={"color":vc,"fontSize":"12px",
                             "fontWeight":"bold","fontFamily":"Arial"})
        ], style={"marginBottom":"5px"})

    return html.Div([
        html.Div([
            html.Span(f"{f} ", style={"fontSize":"26px"}),
            html.Span(row["city"],
                      style={"fontFamily":"Arial","fontSize":"17px",
                             "fontWeight":"bold","color":HEAD}),
            html.Span(f"  {row['region']}",
                      style={"fontFamily":"Arial","fontSize":"10px",
                             "color":MUTED,"letterSpacing":"1px",
                             "textTransform":"uppercase"})
        ], style={"marginBottom":"8px"}),
        html.Hr(style={"margin":"8px 0","borderColor":BORDER}),
        ri("Languages", row["languages"]),
        ri("Timezone",  row["timezone"]),
        html.Hr(style={"margin":"8px 0","borderColor":BORDER}),
        html.Div("TODAY", style={"fontFamily":"Arial","fontSize":"9px",
                                  "color":MUTED,"letterSpacing":"2px","marginBottom":"6px"}),
        html.Div([
            html.Span(f"{icon} ", style={"fontSize":"16px"}),
            html.Span(str(row.get("weather_condition","")),
                      style={"fontFamily":"Arial","fontSize":"12px",
                             "fontWeight":"bold","color":TEXT})
        ], style={"marginBottom":"6px"}),
        ri("High / Low", f"{row['high_c']}C  /  {row['low_c']}C"),
        ri("Feels Like", f"{row['feels_like_c']}C"),
        ri("Rain", f"{row['rain_probability']}%",
           "#c0392b" if row["rain_probability"]>=70
           else "#d35400" if row["rain_probability"]>=40 else "#1e8449"),
        ri("Day Length", row["day_length"]),
        ri("Season",     row["season"]),
        html.Hr(style={"margin":"8px 0","borderColor":BORDER}),
        html.Div("ATTRACTIONS", style={"fontFamily":"Arial","fontSize":"9px",
                                        "color":MUTED,"letterSpacing":"2px","marginBottom":"6px"}),
        html.Div([
            html.Div([
                html.Span("📍 ", style={"fontSize":"10px"}),
                html.Span(a, style={"fontFamily":"Arial","fontSize":"11px","color":TEXT})
            ], style={"marginBottom":"3px","padding":"3px 6px",
                      "background":CARD2,"borderRadius":"4px"})
            for a in attrs
        ], style={"marginBottom":"8px"}),
        html.Hr(style={"margin":"8px 0","borderColor":BORDER}),
        html.Div([
            html.Div([
                html.Div(str(s),
                         style={"fontFamily":"Arial","fontSize":"36px",
                                "fontWeight":"bold","color":color,"lineHeight":"1"}),
                html.Div("/10", style={"fontFamily":"Arial","fontSize":"11px","color":MUTED}),
                html.Div(label, style={"fontFamily":"Arial","fontSize":"9px",
                                       "color":color,"letterSpacing":"2px","marginTop":"2px"})
            ], style={"textAlign":"center","minWidth":"68px"}),
            html.Div(style={"width":"1px","background":BORDER,"margin":"0 12px"}),
            html.Div([
                html.Div(str(row.get("travel_recommendation","")),
                         style={"fontFamily":"Arial","fontSize":"11px",
                                "fontWeight":"bold","color":tc,"marginBottom":"4px"}),
                html.Div(str(row.get("climate_risk","No risk")),
                         style={"fontFamily":"Arial","fontSize":"11px",
                                "color":riskc,"fontWeight":"bold"})
            ], style={"flex":"1"})
        ], style={"display":"flex","alignItems":"center"})
    ], style={"fontFamily":"Arial"})

def slbl(text):
    return html.Div(text, style={
        "fontFamily":"Arial","fontSize":"10px","color":MUTED,
        "letterSpacing":"2px","textTransform":"uppercase","marginBottom":"8px"
    })

def ssub(text):
    return html.Div(text, style={
        "fontFamily":"Arial","fontSize":"11px","color":MUTED,"marginBottom":"10px"
    })

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Mega Climate Dashboard"

app.index_string = '''<!DOCTYPE html>
<html>
<head>
{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #f8f4ef !important; color: #2a1f0e; font-family: Arial, sans-serif; }
.Select-control { background:#fff !important; border-color:rgba(0,0,0,0.1) !important; color:#2a1f0e !important; border-radius:6px !important; }
.Select-menu-outer { background:#fff !important; border-color:rgba(0,0,0,0.1) !important; }
.Select-option { background:#fff !important; color:#2a1f0e !important; }
.Select-option:hover { background:#f2ede6 !important; }
.Select-value-label { color:#2a1f0e !important; }
::-webkit-scrollbar { width:5px; }
::-webkit-scrollbar-track { background:#f8f4ef; }
::-webkit-scrollbar-thumb { background:#e0d8cc; border-radius:3px; }
</style>
</head>
<body>{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>'''

PAD  = {"padding":"20px 40px"}
PAD2 = {"padding":"20px 40px","background":CARD2}
SEP  = {"borderBottom":f"0.5px solid {BORDER}"}

app.layout = html.Div([

    # HEADER
    html.Div([
        html.Div([
            html.Div([
                html.Span("🌍 ", style={"fontSize":"20px"}),
                html.Span("Mega Climate Dashboard",
                          style={"fontFamily":"Arial","fontSize":"20px",
                                 "fontWeight":"bold","color":HEAD})
            ], style={"marginBottom":"3px"}),
            html.Div("30 world capitals  ·  live 7-day forecast  ·  travel intelligence",
                     style={"fontFamily":"Arial","fontSize":"11px","color":MUTED})
        ], style={"flex":"1"}),
        html.Div([
            html.Span("● LIVE", style={"color":"#1e8449","fontSize":"10px",
                                        "fontWeight":"bold","letterSpacing":"2px",
                                        "marginRight":"12px"}),
            html.Span(f"{len(today_df)} cities loaded",
                      style={"fontSize":"10px","color":MUTED})
        ])
    ], style={"display":"flex","alignItems":"center","gap":"16px",
              "padding":"14px 40px","background":CARD,
              "borderBottom":f"2px solid {HEAD}"}),

    # SECTION 1: MAP + CITY DETAIL
    html.Div([
        slbl("World map · click any city to reveal its profile"),
        html.Div([
            html.Div([
                dcc.Graph(id="map-chart", figure=build_map(),
                          style={"height":"460px","borderRadius":"8px","overflow":"hidden"},
                          config={"scrollZoom":True,"displayModeBar":False})
            ], style={"width":"62%","display":"inline-block","verticalAlign":"top",
                      "border":f"0.5px solid {BORDER}","borderRadius":"8px",
                      "overflow":"hidden"}),
            html.Div([
                html.Div(id="city-detail-panel", children=empty_detail(),
                         style={"padding":"16px","background":CARD,
                                "borderRadius":"8px","border":f"0.5px solid {BORDER}",
                                "minHeight":"460px","overflowY":"auto"})
            ], style={"width":"36%","display":"inline-block",
                      "verticalAlign":"top","paddingLeft":"16px"})
        ])
    ], style={**PAD, **SEP}),

    # SECTION 2: FORECAST TABLE
    html.Div([
        html.Div(id="table-title",
                 children="CLICK A CITY ON THE MAP TO SEE ITS 7-DAY FORECAST",
                 style={"fontFamily":"Arial","fontSize":"10px","color":MUTED,
                        "letterSpacing":"2px","marginBottom":"12px"}),
        dash_table.DataTable(
            id="forecast-table",
            style_table={"overflowX":"auto","borderRadius":"6px","overflow":"hidden"},
            style_header={
                "backgroundColor":HEAD,"color":CARD,"fontWeight":"bold",
                "fontFamily":"Arial","textAlign":"center","fontSize":"11px","padding":"10px"
            },
            style_cell={
                "fontFamily":"Arial","textAlign":"center","padding":"8px 10px",
                "fontSize":"11px","border":f"0.5px solid {BORDER}",
                "backgroundColor":CARD,"color":TEXT
            },
            style_data={"backgroundColor":CARD},
            style_data_conditional=[
                {"if":{"row_index":"odd"},"backgroundColor":CARD2},
                {"if":{"filter_query":'{travel_recommendation} contains "Highly"'},
                 "backgroundColor":"#eaf3de","color":"#1e5631"},
                {"if":{"filter_query":'{travel_recommendation} contains "Not"'},
                 "backgroundColor":"#fdedec","color":"#7b241c"},
                {"if":{"filter_query":'{climate_risk} != "No risk"'},
                 "backgroundColor":"#fef9e7"},
            ]
        )
    ], style={**PAD2, **SEP}),

    # SECTION 3: DONUT + LOLLIPOP
    html.Div([
        html.Div([
            html.Div([
                slbl("Cities by region"),
                dcc.Graph(id="donut-chart", figure=build_donut(),
                          style={"height":"260px"},
                          config={"displayModeBar":False})
            ], style={"width":"22%","display":"inline-block","verticalAlign":"top",
                      "paddingRight":"20px"}),
            html.Div([
                slbl("Today's travel score — all 30 cities ranked"),
                ssub("Flag + city · color = region · dot = today's score"),
                dcc.Graph(id="lollipop-chart", figure=build_lollipop(),
                          config={"displayModeBar":False})
            ], style={"width":"76%","display":"inline-block","verticalAlign":"top"})
        ])
    ], style={**PAD, **SEP}),

    # SECTION 4: ACTUAL VS FEELS LIKE
    html.Div([
        slbl("Actual high vs feels like temperature — all cities today"),
        ssub("Bars = actual high temperature (color = region) · line = feels like"),
        dcc.Graph(id="feels-chart", figure=build_feels_line(),
                  config={"displayModeBar":False})
    ], style={**PAD2, **SEP}),

    # SECTION 5: CANDLESTICK WEATHER CHART
    html.Div([
        slbl("7-day weather forecast — candlestick style"),
        ssub("Body = high/low temp range · color = travel recommendation · dashed line = feels like · dot size = rain %"),
        html.Div([
            html.Label("Select City:",
                       style={"fontFamily":"Arial","fontSize":"11px",
                              "color":MUTED,"marginRight":"8px"}),
            dcc.Dropdown(
                id="candle-city-select",
                options=[{"label":f"{gf(c)}  {c}","value":c}
                         for c in sorted(df["city"].unique())],
                value="Tokyo",
                clearable=False,
                style={"width":"240px","fontSize":"12px","display":"inline-block",
                       "verticalAlign":"middle"}
            )
        ], style={"marginBottom":"14px","display":"flex","alignItems":"center"}),
        dcc.Graph(id="candle-chart",
                  figure=build_candlestick("Tokyo"),
                  config={"displayModeBar":False}),
        html.Div([
            html.Div([
                html.Div(style={"width":"14px","height":"18px","borderRadius":"3px",
                                "background":"#1e8449","display":"inline-block",
                                "marginRight":"4px","verticalAlign":"middle"}),
                html.Span("Highly recommended",
                          style={"fontFamily":"Arial","fontSize":"10px","color":MUTED,
                                 "marginRight":"14px"})
            ], style={"display":"inline-block"}),
            html.Div([
                html.Div(style={"width":"14px","height":"18px","borderRadius":"3px",
                                "background":"#d35400","display":"inline-block",
                                "marginRight":"4px","verticalAlign":"middle"}),
                html.Span("Carry an umbrella",
                          style={"fontFamily":"Arial","fontSize":"10px","color":MUTED,
                                 "marginRight":"14px"})
            ], style={"display":"inline-block"}),
            html.Div([
                html.Div(style={"width":"14px","height":"18px","borderRadius":"3px",
                                "background":"#c0392b","display":"inline-block",
                                "marginRight":"4px","verticalAlign":"middle"}),
                html.Span("Not recommended",
                          style={"fontFamily":"Arial","fontSize":"10px","color":MUTED,
                                 "marginRight":"14px"})
            ], style={"display":"inline-block"}),
            html.Div([
                html.Span("- - ",
                          style={"fontFamily":"Arial","fontSize":"12px",
                                 "color":"#555","marginRight":"4px"}),
                html.Span("Feels like temperature",
                          style={"fontFamily":"Arial","fontSize":"10px","color":MUTED,
                                 "marginRight":"14px"})
            ], style={"display":"inline-block"}),
            html.Div([
                html.Div(style={"width":"10px","height":"10px","borderRadius":"50%",
                                "background":"#2471a3","display":"inline-block",
                                "marginRight":"4px","verticalAlign":"middle",
                                "opacity":"0.7"}),
                html.Span("Dot size = rain probability",
                          style={"fontFamily":"Arial","fontSize":"10px","color":MUTED})
            ], style={"display":"inline-block"})
        ], style={"marginTop":"8px"})
    ], style={**PAD, "paddingBottom":"60px"}),

], style={"background":BG,"minHeight":"100vh"})

# CALLBACKS

@app.callback(
    Output("city-detail-panel","children"),
    Output("forecast-table","data"),
    Output("forecast-table","columns"),
    Output("table-title","children"),
    Input("map-chart","clickData")
)
def update_city(clickData):
    if clickData is None:
        return empty_detail(), [], [], "CLICK A CITY ON THE MAP TO SEE ITS 7-DAY FORECAST"
    try:
        city_name = clickData["points"][0]["text"].strip()
    except (KeyError, IndexError):
        return empty_detail(), [], [], "CLICK A CITY ON THE MAP TO SEE ITS 7-DAY FORECAST"

    city_df = df[df["city"]==city_name].copy()
    if city_df.empty:
        return empty_detail(), [], [], "CITY NOT FOUND"

    row = today_df[today_df["city"]==city_name]
    row = row.iloc[0] if not row.empty else city_df.iloc[0]

    cols_show = ["date","high_c","low_c","feels_like_c","rain_probability",
                 "weather_condition","day_length","season",
                 "climate_risk","travel_recommendation","travel_score"]
    col_labels = {
        "date":"Date","high_c":"High C","low_c":"Low C",
        "feels_like_c":"Feels Like","rain_probability":"Rain %",
        "weather_condition":"Condition","day_length":"Day Length",
        "season":"Season","climate_risk":"Risk",
        "travel_recommendation":"Recommendation","travel_score":"Score"
    }
    columns = [{"name":col_labels[c],"id":c} for c in cols_show]
    data    = city_df[cols_show].to_dict("records")
    return (city_detail(row), data, columns,
            f"7-DAY FORECAST — {gf(city_name)} {city_name.upper()}")

@app.callback(
    Output("candle-chart","figure"),
    Input("candle-city-select","value")
)
def update_candle(city_name):
    return build_candlestick(city_name)

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8052")).start()
    app.run(debug=True, port=8052)