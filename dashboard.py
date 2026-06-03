# dashboard.py
# World Capitals Climate Dashboard
# Dash application that connects directly to SQLite database
# using SQLAlchemy and displays interactive analytics.
#
# To switch to PostgreSQL change only the DATABASE_URL line.
# Usage: python dashboard.py

import os
import webbrowser
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, dash_table, Input, Output
from sqlalchemy import create_engine, text

# -------------------------------------------------------
# CONFIGURATION
# Change this one line to switch to PostgreSQL:
# DATABASE_URL = "postgresql://user:password@host:port/dbname"
# -------------------------------------------------------

DATABASE_URL = "sqlite:///climate_dashboard.db"

# -------------------------------------------------------
# DATABASE CONNECTION
# Pulls live data from the database using SQLAlchemy
# -------------------------------------------------------

def load_data_from_db():
    """
    Connects to the database and loads joined data from
    dim_city and fact_forecast tables into a pandas DataFrame.
    Falls back to CSV if database is unavailable.
    """
    try:
        engine = create_engine(DATABASE_URL, echo=False)
        query  = text("""
            SELECT
                c.city,
                c.region,
                c.languages,
                c.timezone,
                c.latitude,
                c.longitude,
                f.date,
                f.high_c,
                f.low_c,
                f.feels_like_c,
                f.rain_probability,
                f.weather_condition,
                f.day_length,
                f.season,
                f.climate_risk,
                f.travel_recommendation
            FROM fact_forecast f
            JOIN dim_city c ON f.city_id = c.city_id
            ORDER BY c.city, f.date
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        print(f"Loaded {len(df)} rows from database successfully.")
        return df

    except Exception as e:
        print(f"Database connection failed: {e}")
        print("Falling back to CSV...")
        return pd.read_csv("data/forecast_data.csv")


# -------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------

df = load_data_from_db()

# Get first available date per city for today view
first_dates      = df.groupby("city")["date"].min().reset_index()
first_dates.columns = ["city", "first_date"]
df               = df.merge(first_dates, on="city")
today_df         = df[df["date"] == df["first_date"]].drop_duplicates(subset="city").copy()

# -------------------------------------------------------
# KPI CALCULATIONS
# -------------------------------------------------------

hottest_city    = today_df.loc[today_df["high_c"].idxmax(), "city"]
hottest_temp    = today_df["high_c"].max()
coldest_city    = today_df.loc[today_df["high_c"].idxmin(), "city"]
coldest_temp    = today_df["high_c"].min()
avg_rain        = round(today_df["rain_probability"].mean(), 1)
travel_ready    = today_df[today_df["travel_recommendation"].str.contains("Highly|Recommended", na=False)].shape[0]
at_risk         = today_df[today_df["climate_risk"] != "No risk"].shape[0]

# -------------------------------------------------------
# APP SETUP
# -------------------------------------------------------

app = Dash(__name__)

# -------------------------------------------------------
# CHART BUILDERS
# -------------------------------------------------------

def build_map(region="All"):
    filtered = today_df if region == "All" else today_df[today_df["region"] == region]
    fig = px.scatter_geo(
        filtered, lat="latitude", lon="longitude",
        hover_name="city", color="region",
        projection="natural earth",
        custom_data=["high_c", "low_c", "weather_condition",
                     "travel_recommendation", "rain_probability"]
    )
    fig.update_traces(
        marker=dict(size=13, opacity=0.9, line=dict(width=1.5, color="white")),
        hovertemplate=(
            "<b>%{hovertext}</b><br><br>"
            "High: %{customdata[0]}C  |  Low: %{customdata[1]}C<br>"
            "Condition: %{customdata[2]}<br>"
            "Rain chance: %{customdata[4]}%<br>"
            "Travel: %{customdata[3]}<extra></extra>"
        )
    )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend=dict(title="Region", bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#ddd", borderwidth=1),
        geo=dict(showland=True, landcolor="#eef0e8",
                 showocean=True, oceancolor="#d0e8f5",
                 showcoastlines=True, coastlinecolor="#bbb",
                 showframe=False, showcountries=True, countrycolor="#ddd"),
        paper_bgcolor="white"
    )
    return fig


def build_bar(region="All"):
    filtered = today_df if region == "All" else today_df[today_df["region"] == region]
    filtered = filtered.sort_values("high_c", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="High C", x=filtered["city"], y=filtered["high_c"],
        marker_color="#e74c3c", width=0.35,
        hovertemplate="<b>%{x}</b><br>High: %{y}C<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        name="Low C", x=filtered["city"], y=filtered["low_c"],
        marker_color="#3498db", width=0.35,
        hovertemplate="<b>%{x}</b><br>Low: %{y}C<extra></extra>"
    ))
    fig.update_layout(
        barmode="group", bargroupgap=0.25,
        xaxis_title="City", yaxis_title="Temperature (C)",
        font=dict(family="Arial", size=13),
        plot_bgcolor="#fafafa", paper_bgcolor="#fafafa",
        yaxis=dict(gridcolor="#ececec"),
        xaxis=dict(gridcolor="#ececec"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=20, b=40)
    )
    return fig


def build_scatter(region="All"):
    filtered = today_df if region == "All" else today_df[today_df["region"] == region]
    fig = px.scatter(
        filtered, x="latitude", y="high_c",
        color="region", text="city", size="high_c", size_max=22,
        custom_data=["city", "high_c", "low_c", "region", "latitude"]
    )
    fig.update_traces(
        textposition="top center",
        marker=dict(opacity=0.85, line=dict(width=1, color="white")),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Latitude: %{customdata[4]}<br>"
            "High: %{customdata[1]}C<br>"
            "Low: %{customdata[2]}C<br>"
            "Region: %{customdata[3]}<extra></extra>"
        )
    )
    fig.update_layout(
        xaxis_title="Latitude (negative = southern hemisphere)",
        yaxis_title="High Temperature (C)",
        font=dict(family="Arial", size=13),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        yaxis=dict(gridcolor="#ececec"),
        xaxis=dict(gridcolor="#ececec", zeroline=True,
                   zerolinecolor="#aaa", zerolinewidth=1.5),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=30, b=50, l=60, r=20), height=320
    )
    return fig


def build_rain_chart(region="All"):
    filtered = today_df if region == "All" else today_df[today_df["region"] == region]
    filtered = filtered.sort_values("rain_probability", ascending=True)
    fig = go.Figure(go.Bar(
        x=filtered["rain_probability"],
        y=filtered["city"],
        orientation="h",
        marker_color=[
            "#e74c3c" if r >= 70 else "#f39c12" if r >= 40 else "#2ecc71"
            for r in filtered["rain_probability"]
        ],
        hovertemplate="<b>%{y}</b><br>Rain chance: %{x}%<extra></extra>"
    ))
    fig.update_layout(
        xaxis_title="Rain Probability (%)",
        yaxis_title="",
        font=dict(family="Arial", size=13),
        plot_bgcolor="#fafafa", paper_bgcolor="#fafafa",
        xaxis=dict(gridcolor="#ececec", range=[0, 100]),
        margin=dict(t=20, b=40, l=120, r=20), height=320
    )
    return fig


# -------------------------------------------------------
# KPI CARD BUILDER
# -------------------------------------------------------

def kpi_card(label, value, sub="", color="#1a1a2e"):
    return html.Div([
        html.P(label, style={"fontFamily": "Arial", "fontSize": "12px",
                              "color": "#888", "margin": "0 0 4px 0",
                              "textTransform": "uppercase", "letterSpacing": "1px"}),
        html.P(str(value), style={"fontFamily": "Arial", "fontSize": "26px",
                                   "fontWeight": "bold", "color": color,
                                   "margin": "0 0 2px 0"}),
        html.P(sub, style={"fontFamily": "Arial", "fontSize": "12px",
                            "color": "#aaa", "margin": "0"})
    ], style={
        "background": "#ffffff", "borderRadius": "10px",
        "padding": "16px 20px", "border": "1px solid #eee",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
        "flex": "1", "minWidth": "140px"
    })


# -------------------------------------------------------
# LAYOUT
# -------------------------------------------------------

app.layout = html.Div([

    # Header
    html.Div([
        html.H1("World Capitals Climate Dashboard",
                style={"textAlign": "center", "fontFamily": "Arial",
                       "color": "#1a1a2e", "fontSize": "30px", "marginBottom": "4px"}),
        html.P("Live 7-day weather analytics for 10 world capitals | Data from SQLite database",
               style={"textAlign": "center", "fontFamily": "Arial",
                      "color": "#888", "fontSize": "13px", "marginTop": "0"})
    ], style={"padding": "24px 0 10px 0", "borderBottom": "2px solid #f0f0f0",
              "marginBottom": "16px"}),

    # KPI cards row
    html.Div([
        kpi_card("Hottest City Today",   f"{hottest_temp}C",   hottest_city, "#e74c3c"),
        kpi_card("Coldest City Today",   f"{coldest_temp}C",   coldest_city, "#3498db"),
        kpi_card("Avg Rain Probability", f"{avg_rain}%",       "across all cities", "#f39c12"),
        kpi_card("Travel Recommended",   f"{travel_ready}/10", "cities today", "#2ecc71"),
        kpi_card("Climate Risk Alert",   f"{at_risk}/10",      "cities flagged", "#e74c3c"),
    ], style={"display": "flex", "gap": "12px", "padding": "0 40px 20px 40px",
              "flexWrap": "wrap"}),

    # Region filter
    html.Div([
        html.Label("Filter by Region:",
                   style={"fontFamily": "Arial", "fontWeight": "bold",
                          "fontSize": "14px", "marginBottom": "6px", "display": "block"}),
        dcc.Dropdown(
            id="region-filter",
            options=[{"label": "All Regions", "value": "All"}] +
                    [{"label": r, "value": r} for r in sorted(df["region"].unique())],
            value="All", clearable=False,
            style={"width": "280px", "fontSize": "14px"}
        )
    ], style={"padding": "0 40px 16px 40px"}),

    # Map and summary card
    html.Div([
        html.Div([
            dcc.Graph(id="world-map", figure=build_map(),
                      style={"height": "440px"}, config={"scrollZoom": True})
        ], style={"width": "63%", "display": "inline-block", "verticalAlign": "top",
                  "boxShadow": "0 2px 8px rgba(0,0,0,0.08)",
                  "borderRadius": "12px", "overflow": "hidden"}),

        html.Div([
            html.Div(id="city-summary", children=[
                html.Div([
                    html.P("Click any city on the map",
                           style={"color": "#999", "textAlign": "center",
                                  "fontFamily": "Arial", "fontSize": "14px",
                                  "marginTop": "40px"}),
                    html.P("to see detailed weather info",
                           style={"color": "#bbb", "textAlign": "center",
                                  "fontFamily": "Arial", "fontSize": "13px"})
                ])
            ], style={"padding": "16px", "background": "#fafafa",
                      "borderRadius": "12px", "fontFamily": "Arial",
                      "minHeight": "440px", "border": "1px solid #eee",
                      "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"})
        ], style={"width": "34%", "display": "inline-block",
                  "verticalAlign": "top", "paddingLeft": "16px"})

    ], style={"padding": "0 40px 24px 40px"}),

    # Bar chart and Rain chart side by side
    html.Div([
        html.Div([
            html.H3("Temperature Comparison Today",
                    style={"fontFamily": "Arial", "color": "#1a1a2e",
                           "fontSize": "16px", "marginBottom": "4px"}),
            dcc.Graph(id="temp-chart", figure=build_bar(), style={"height": "320px"})
        ], style={"width": "49%", "display": "inline-block", "verticalAlign": "top",
                  "padding": "20px", "background": "#fafafa", "borderRadius": "12px",
                  "border": "1px solid #eee", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"}),

        html.Div([
            html.H3("Rain Probability Today",
                    style={"fontFamily": "Arial", "color": "#1a1a2e",
                           "fontSize": "16px", "marginBottom": "4px"}),
            dcc.Graph(id="rain-chart", figure=build_rain_chart(), style={"height": "320px"})
        ], style={"width": "49%", "display": "inline-block", "verticalAlign": "top",
                  "padding": "20px", "background": "#fafafa", "borderRadius": "12px",
                  "border": "1px solid #eee", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
                  "marginLeft": "1%"})

    ], style={"padding": "0 40px 24px 40px"}),

    

    # Forecast table
    html.Div([
        html.H3(id="table-title",
                children="Click a city on the map to see its 7-day forecast",
                style={"fontFamily": "Arial", "color": "#1a1a2e",
                       "fontSize": "16px", "marginBottom": "12px"}),
        dash_table.DataTable(
            id="forecast-table",
            style_table={"overflowX": "auto", "borderRadius": "8px", "overflow": "hidden"},
            style_header={"backgroundColor": "#1a1a2e", "color": "white",
                          "fontWeight": "bold", "fontFamily": "Arial",
                          "textAlign": "center", "fontSize": "13px", "padding": "10px"},
            style_cell={"fontFamily": "Arial", "textAlign": "center",
                        "padding": "9px 12px", "fontSize": "13px",
                        "border": "1px solid #f0f0f0"},
            style_data={"backgroundColor": "#ffffff"},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
                {"if": {"filter_query": '{travel_recommendation} contains "Highly"'},
                 "backgroundColor": "#e6f4ea", "color": "#1a7a3c"},
                {"if": {"filter_query": '{travel_recommendation} contains "Not"'},
                 "backgroundColor": "#fdecea", "color": "#b71c1c"},
                {"if": {"filter_query": '{climate_risk} != "No risk"'},
                 "backgroundColor": "#fff8e1"},
            ]
        )
    ], style={"padding": "20px 40px", "background": "#fafafa",
              "margin": "0 40px 40px 40px", "borderRadius": "12px",
              "border": "1px solid #eee", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"}),

], style={"backgroundColor": "#f5f6fa", "minHeight": "100vh"})


# -------------------------------------------------------
# CALLBACKS
# -------------------------------------------------------

@app.callback(
    Output("world-map", "figure"),
    Input("region-filter", "value")
)
def update_map(region):
    return build_map(region)


@app.callback(
    Output("temp-chart", "figure"),
    Input("region-filter", "value")
)
def update_bar(region):
    return build_bar(region)





@app.callback(
    Output("rain-chart", "figure"),
    Input("region-filter", "value")
)
def update_rain(region):
    return build_rain_chart(region)


@app.callback(
    Output("forecast-table", "data"),
    Output("forecast-table", "columns"),
    Output("city-summary", "children"),
    Output("table-title", "children"),
    Input("world-map", "clickData"),
    Input("region-filter", "value")
)
def update_table(clickData, selected_region):
    if clickData is None:
        return [], [], html.Div([
            html.P("Click any city on the map",
                   style={"color": "#999", "textAlign": "center",
                          "fontFamily": "Arial", "fontSize": "14px",
                          "marginTop": "40px"}),
            html.P("to see detailed weather info",
                   style={"color": "#bbb", "textAlign": "center",
                          "fontFamily": "Arial", "fontSize": "13px"})
        ]), "Click a city on the map to see its 7-day forecast"

    city_name = clickData["points"][0]["hovertext"]
    city_df   = df[df["city"] == city_name].copy()
    row       = city_df.iloc[0]

    columns_to_show = [
        "date", "high_c", "low_c", "feels_like_c",
        "rain_probability", "weather_condition",
        "day_length", "season", "climate_risk", "travel_recommendation"
    ]
    col_labels = {
        "date": "Date", "high_c": "High (C)", "low_c": "Low (C)",
        "feels_like_c": "Feels Like (C)", "rain_probability": "Rain %",
        "weather_condition": "Condition", "day_length": "Day Length",
        "season": "Season", "climate_risk": "Climate Risk",
        "travel_recommendation": "Travel Recommendation"
    }
    columns = [{"name": col_labels[col], "id": col} for col in columns_to_show]
    data    = city_df[columns_to_show].to_dict("records")

    travel_color = (
        "#1a7a3c" if "Highly" in str(row["travel_recommendation"])
        else "#b71c1c" if "Not" in str(row["travel_recommendation"])
        else "#e67e22"
    )
    risk_color = "#b71c1c" if row["climate_risk"] != "No risk" else "#1a7a3c"

    def info_row(label, value):
        return html.Div([
            html.Span(label, style={"color": "#888", "fontSize": "12px",
                                    "display": "block", "marginBottom": "1px"}),
            html.Span(str(value), style={"color": "#222", "fontSize": "14px",
                                         "fontWeight": "500"})
        ], style={"marginBottom": "10px"})

    summary = html.Div([
        html.H3(city_name, style={"color": "#1a1a2e", "marginBottom": "2px",
                                   "fontSize": "20px"}),
        html.Hr(style={"margin": "8px 0 12px 0", "borderColor": "#eee"}),
        info_row("Region",    row["region"]),
        info_row("Languages", row["languages"]),
        info_row("Timezone",  row["timezone"]),
        html.Hr(style={"margin": "8px 0 12px 0", "borderColor": "#eee"}),
        html.P("TODAY", style={"fontSize": "11px", "color": "#aaa",
                                "letterSpacing": "1px", "margin": "0 0 8px 0"}),
        info_row("High / Low",  f"{row['high_c']}C  /  {row['low_c']}C"),
        info_row("Feels Like",  f"{row['feels_like_c']}C"),
        info_row("Condition",   row["weather_condition"]),
        info_row("Rain Chance", f"{row['rain_probability']}%"),
        info_row("Day Length",  row["day_length"]),
        info_row("Season",      row["season"]),
        html.Hr(style={"margin": "8px 0 12px 0", "borderColor": "#eee"}),
        html.Div([
            html.Span("Travel:  ", style={"fontSize": "13px", "color": "#555"}),
            html.Span(row["travel_recommendation"],
                      style={"fontWeight": "bold", "color": travel_color,
                             "fontSize": "13px"})
        ], style={"marginBottom": "8px"}),
        html.Div([
            html.Span("Risk:  ", style={"fontSize": "13px", "color": "#555"}),
            html.Span(row["climate_risk"],
                      style={"fontWeight": "bold", "color": risk_color,
                             "fontSize": "13px"})
        ])
    ])

    return data, columns, summary, f"7-Day Forecast: {city_name}"


# -------------------------------------------------------
# RUN
# -------------------------------------------------------

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        import threading
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8050")).start()
    app.run(debug=True)