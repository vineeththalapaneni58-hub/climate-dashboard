# dashboard.py
# World Capitals Climate Dashboard
# Reads forecast_data.csv and displays an interactive dashboard

import os
import webbrowser
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, dash_table, Input, Output

# -------------------------------------------------------
# LOAD AND PREPARE DATA
# -------------------------------------------------------

df = pd.read_csv("forecast_data.csv")

# Get first available date per city
first_dates          = df.groupby("city")["date"].min().reset_index()
first_dates.columns  = ["city", "first_date"]
df                   = df.merge(first_dates, on="city")
today_df             = df[df["date"] == df["first_date"]].drop_duplicates(subset="city").copy()

print("Cities loaded:", today_df["city"].tolist())
print("Columns:", today_df.columns.tolist())

# -------------------------------------------------------
# PRE-BUILD ALL FIGURES AT STARTUP
# So they are ready before any callback fires
# -------------------------------------------------------

def build_map(region="All"):
    filtered = today_df if region == "All" else today_df[today_df["region"] == region]
    fig = px.scatter_geo(
        filtered,
        lat="latitude", lon="longitude",
        hover_name="city", color="region",
        projection="natural earth",
        custom_data=["high_c", "low_c", "weather_condition",
                     "travel_recommendation", "rain_probability"]
    )
    fig.update_traces(
        marker=dict(size=13, opacity=0.9, line=dict(width=1.5, color="white")),
        hovertemplate=(
            "<b>%{hovertext}</b><br><br>"
            "🌡️ High: %{customdata[0]}°C  |  Low: %{customdata[1]}°C<br>"
            "🌤️ Condition: %{customdata[2]}<br>"
            "🌧️ Rain chance: %{customdata[4]}%<br>"
            "✈️ Travel: %{customdata[3]}<extra></extra>"
        )
    )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend=dict(title="Region", bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#ddd", borderwidth=1),
        geo=dict(
            showland=True, landcolor="#eef0e8",
            showocean=True, oceancolor="#d0e8f5",
            showcoastlines=True, coastlinecolor="#bbb",
            showframe=False, showcountries=True, countrycolor="#ddd"
        ),
        paper_bgcolor="white"
    )
    return fig


def build_bar(region="All"):
    filtered = today_df if region == "All" else today_df[today_df["region"] == region]
    filtered = filtered.sort_values("high_c", ascending=False)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="High °C", x=filtered["city"], y=filtered["high_c"],
        marker_color="#e74c3c", width=0.35,
        hovertemplate="<b>%{x}</b><br>High: %{y}°C<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        name="Low °C", x=filtered["city"], y=filtered["low_c"],
        marker_color="#3498db", width=0.35,
        hovertemplate="<b>%{x}</b><br>Low: %{y}°C<extra></extra>"
    ))
    fig.update_layout(
        barmode="group", bargroupgap=0.25,
        xaxis_title="City", yaxis_title="Temperature (°C)",
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
    filtered = filtered.sort_values("latitude")
    fig = px.scatter(
        filtered,
        x="latitude",
        y="high_c",
        color="region",
        text="city",
        size="high_c",
        size_max=22,
        custom_data=["city", "high_c", "low_c", "region", "latitude"]
    )
    fig.update_traces(
        textposition="top center",
        marker=dict(opacity=0.85, line=dict(width=1, color="white")),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Latitude: %{customdata[4]}°<br>"
            "High: %{customdata[1]}°C<br>"
            "Low: %{customdata[2]}°C<br>"
            "Region: %{customdata[3]}<extra></extra>"
        )
    )
    fig.update_layout(
        xaxis_title="Latitude (negative = southern hemisphere)",
        yaxis_title="High Temperature (°C)",
        font=dict(family="Arial", size=13),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        yaxis=dict(gridcolor="#ececec", zeroline=False),
        xaxis=dict(
            gridcolor="#ececec",
            zeroline=True,
            zerolinecolor="#aaa",
            zerolinewidth=1.5
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=30, b=50, l=60, r=20),
        height=320
    )
    return fig


# -------------------------------------------------------
# APP SETUP
# -------------------------------------------------------

app = Dash(__name__)

# -------------------------------------------------------
# LAYOUT
# -------------------------------------------------------

app.layout = html.Div([

    # Header
    html.Div([
        html.H1("🌍 World Capitals Climate Dashboard",
                style={"textAlign": "center", "fontFamily": "Arial",
                       "color": "#1a1a2e", "fontSize": "32px", "marginBottom": "4px"}),
        html.P("Live 7-day weather forecasts for 10 world capitals",
               style={"textAlign": "center", "fontFamily": "Arial",
                      "color": "#666", "fontSize": "15px", "marginTop": "0"})
    ], style={"padding": "28px 0 10px 0",
              "borderBottom": "2px solid #f0f0f0",
              "marginBottom": "16px"}),

    # Region filter
    html.Div([
        html.Label("Filter by Region:",
                   style={"fontFamily": "Arial", "fontWeight": "bold",
                          "fontSize": "14px", "marginBottom": "6px", "display": "block"}),
        dcc.Dropdown(
            id="region-filter",
            options=[{"label": "🌐 All Regions", "value": "All"}] +
                    [{"label": r, "value": r} for r in sorted(df["region"].unique())],
            value="All",
            clearable=False,
            style={"width": "280px", "fontSize": "14px"}
        )
    ], style={"padding": "0 40px 16px 40px"}),

    # Map + Summary card
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
                    html.P("🗺️", style={"fontSize": "40px",
                                        "textAlign": "center", "margin": "20px 0 8px"}),
                    html.P("Click any city on the map",
                           style={"color": "#999", "textAlign": "center",
                                  "fontFamily": "Arial", "fontSize": "14px"}),
                    html.P("to see detailed weather info",
                           style={"color": "#bbb", "textAlign": "center",
                                  "fontFamily": "Arial", "fontSize": "13px"})
                ])
            ], style={
                "padding": "16px", "background": "#fafafa",
                "borderRadius": "12px", "fontFamily": "Arial",
                "minHeight": "440px", "border": "1px solid #eee",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"
            })
        ], style={"width": "34%", "display": "inline-block",
                  "verticalAlign": "top", "paddingLeft": "16px"})

    ], style={"padding": "0 40px 24px 40px"}),

    # Scatter plot
    html.Div([
        html.H3("Temperature vs Latitude — Today",
                style={"fontFamily": "Arial", "color": "#1a1a2e",
                       "fontSize": "18px", "marginBottom": "8px"}),
        dcc.Graph(
            id="scatter-plot",
            figure=build_scatter(),
            style={"height": "320px", "width": "100%"}
        )
    ], style={
        "padding": "20px 40px",
        "background": "#ffffff",
        "margin": "0 40px 24px 40px",
        "borderRadius": "12px",
        "border": "1px solid #ddd",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"
    }),

    # Bar chart
    html.Div([
        html.H3("Temperature Comparison — All Cities (Today)",
                style={"fontFamily": "Arial", "color": "#1a1a2e",
                       "fontSize": "18px", "marginBottom": "4px"}),
        dcc.Graph(
            id="temp-chart",
            figure=build_bar(),
            style={"height": "320px", "width": "100%"}
        )
    ], style={
        "padding": "20px 40px",
        "background": "#fafafa",
        "margin": "0 40px 24px 40px",
        "borderRadius": "12px",
        "border": "1px solid #eee",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"
    }),

    # Forecast table
    html.Div([
        html.H3(id="table-title",
                children="Click a city on the map to see its 7-day forecast",
                style={"fontFamily": "Arial", "color": "#1a1a2e",
                       "fontSize": "18px", "marginBottom": "12px"}),
        dash_table.DataTable(
            id="forecast-table",
            style_table={"overflowX": "auto", "borderRadius": "8px", "overflow": "hidden"},
            style_header={
                "backgroundColor": "#1a1a2e", "color": "white",
                "fontWeight": "bold", "fontFamily": "Arial",
                "textAlign": "center", "fontSize": "13px", "padding": "10px"
            },
            style_cell={
                "fontFamily": "Arial", "textAlign": "center",
                "padding": "9px 12px", "fontSize": "13px",
                "border": "1px solid #f0f0f0"
            },
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
    ], style={
        "padding": "20px 40px",
        "background": "#fafafa",
        "margin": "0 40px 40px 40px",
        "borderRadius": "12px",
        "border": "1px solid #eee",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"
    }),

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
    Output("scatter-plot", "figure"),
    Input("region-filter", "value")
)
def update_scatter(region):
    return build_scatter(region)


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
            html.P("🗺️", style={"fontSize": "40px",
                                 "textAlign": "center", "margin": "20px 0 8px"}),
            html.P("Click any city on the map",
                   style={"color": "#999", "textAlign": "center",
                          "fontFamily": "Arial", "fontSize": "14px"}),
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
        "date": "Date", "high_c": "High (°C)", "low_c": "Low (°C)",
        "feels_like_c": "Feels Like (°C)", "rain_probability": "Rain %",
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
        html.H3(city_name, style={"color": "#1a1a2e",
                                   "marginBottom": "2px", "fontSize": "20px"}),
        html.Hr(style={"margin": "8px 0 12px 0", "borderColor": "#eee"}),
        info_row("Region",    row["region"]),
        info_row("Languages", row["languages"]),
        info_row("Timezone",  row["timezone"]),
        html.Hr(style={"margin": "8px 0 12px 0", "borderColor": "#eee"}),
        html.P("TODAY", style={"fontSize": "11px", "color": "#aaa",
                                "letterSpacing": "1px", "margin": "0 0 8px 0"}),
        info_row("🌡️ High / Low",  f"{row['high_c']}°C  /  {row['low_c']}°C"),
        info_row("🌡️ Feels Like",  f"{row['feels_like_c']}°C"),
        info_row("🌤️ Condition",   row["weather_condition"]),
        info_row("🌧️ Rain Chance", f"{row['rain_probability']}%"),
        info_row("🌅 Day Length",  row["day_length"]),
        info_row("🍂 Season",      row["season"]),
        html.Hr(style={"margin": "8px 0 12px 0", "borderColor": "#eee"}),
        html.Div([
            html.Span("✈️ Travel:  ", style={"fontSize": "13px", "color": "#555"}),
            html.Span(row["travel_recommendation"],
                      style={"fontWeight": "bold", "color": travel_color, "fontSize": "13px"})
        ], style={"marginBottom": "8px"}),
        html.Div([
            html.Span("⚠️ Risk:  ", style={"fontSize": "13px", "color": "#555"}),
            html.Span(row["climate_risk"],
                      style={"fontWeight": "bold", "color": risk_color, "fontSize": "13px"})
        ])
    ])

    return data, columns, summary, f"7-Day Forecast — {city_name}"


# -------------------------------------------------------
# RUN
# -------------------------------------------------------

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open("http://127.0.0.1:8050")
    app.run(debug=True)