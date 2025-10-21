import streamlit as st
import plotly.express as px
from api import get_worldbank_data

st.set_page_config(page_title="World Bank Dashboard", layout="wide")

st.title("🌍 World Bank Interactive Dashboard")

with st.expander("App information"):
    st.write("""
        This application provides you with interactive dashboards containing valuable information about countries. The data is used here
             is gathered from [Wrold Bank](https://data.worldbank.org/).
    """)

st.divider() 

st.markdown(
    """
    <style>
    /* Selected state (non-hover) */
    [data-baseweb="popover"] li[role="option"][aria-selected="true"] {
        background-color: red !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
# --- Dashboard selection ---
dashboard_option = st.sidebar.selectbox(
    "Select Dashboard:",
    ["GDP per Capita", "Population Growth", "Economic Overview"]
)

# ============================================================
# BASIC DASHBOARDS
# ============================================================
if dashboard_option in ["GDP per Capita", "Population Growth", "CO2 Emissions"]:
    indicator_map = {
        "GDP per Capita": "NY.GDP.PCAP.CD",
        "Population Growth": "SP.POP.GROW",
        "CO2 Emissions": "EN.ATM.CO2E.PC"
    }
    indicator = indicator_map[dashboard_option]

    # --- Load data ---
    with st.spinner("Fetching World Bank data..."):
        df = get_worldbank_data(indicator)

    if df.empty:
        st.error("No data available.")
        st.stop()

    # --- Filters ---
    years = sorted(df["date"].unique(), reverse=True)
    selected_year = st.sidebar.slider("Select Year", min_value=min(years), max_value=max(years), value=max(years))

    filtered_df = df[df["date"] == selected_year]

    # --- Plotly Interactive Visualization ---
    fig = px.scatter(
        filtered_df,
        x="country",
        y="indicator_value",
        color="indicator_value",
        hover_name="country",
        title=f"{dashboard_option} ({selected_year})",
    )
    fig.update_layout(xaxis_title="Country", yaxis_title=dashboard_option)

    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# ECONOMIC OVERVIEW (CROSS-FILTER DASHBOARD)
# ============================================================
elif dashboard_option == "Economic Overview":
    st.markdown("### 💹 Economic Overview — Explore GDP, Life Expectancy, and Population")

    # --- Fetch data ---
    with st.spinner("Loading economic indicators..."):
        gdp_df = get_worldbank_data("NY.GDP.PCAP.CD")      # GDP per capita
        life_df = get_worldbank_data("SP.DYN.LE00.IN")    # Life Expectancy at Birth
        pop_df = get_worldbank_data("SP.POP.TOTL")        # Population total

    # --- Validate data ---
    if gdp_df.empty or life_df.empty or pop_df.empty:
        st.error("World Bank API returned no data for one of the indicators.")
        st.stop()

    # --- Merge datasets ---
    merged = (
        gdp_df.merge(life_df, on=["country", "countryiso3code", "date"], suffixes=("_gdp", "_life"))
               .merge(pop_df, on=["country", "countryiso3code", "date"])
    )
    merged.rename(columns={"indicator_value": "population"}, inplace=True)

    if merged.empty:
        st.error("No merged data available — World Bank API returned incomplete datasets.")
        st.stop()

    # --- Year filtering ---
    years = sorted(merged["date"].unique(), reverse=True)
    if not years:
        st.error("No available years in the dataset.")
        st.stop()

    selected_year = st.sidebar.slider(
        "Select Year",
        min_value=min(years),
        max_value=max(years),
        value=max(years)
    )

    year_df = merged[merged["date"] == selected_year]

    # --- Scatter Plot ---
    st.write("Click a country in the scatter plot to view its GDP trend over time 👇")

    fig1 = px.scatter(
        year_df,
        x="indicator_value_gdp",
        y="indicator_value_life",
        size="population",
        color="indicator_value_gdp",
        hover_name="country",
        title=f"GDP vs Life Expectancy ({selected_year})",
        color_continuous_scale="Viridis",
    )

    clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- Capture click selection ---
    selected_country = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        selected_country = clicked.selection.points[0]["hovertext"]

    # --- Country Trend ---
    if selected_country:
        st.subheader(f"📈 GDP per Capita Over Time — {selected_country}")
        country_df = merged[merged["country"] == selected_country]
        fig2 = px.line(
            country_df,
            x="date",
            y="indicator_value_gdp",
            title=f"GDP per Capita Over Time ({selected_country})",
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Select a country in the scatter plot to view its GDP trend.")



