import streamlit as st
import plotly.express as px
from api import get_worldbank_data

st.set_page_config(page_title="World Bank Dashboards", layout="wide")

st.title("🌍 World Bank Interactive Dashboards")

with st.expander("App information"):
    st.write("""
        This application provides you with interactive dashboards containing valuable information about countries. The data is used here
            is gathered from [World Bank](https://data.worldbank.org/).
    """)
    st.write("""
        You can use the tab on the left side to select the dashboard and apply different filters.
    """)


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
    [ "Economic Overview", "Social Development Overview", "Population Growth"]
)

# ============================================================
# GLOBAL FILTERS
# ============================================================
# Fetch a base dataset to populate filters, ensuring they are always available.
# Population data is a good general-purpose choice for broad country/year coverage.
with st.spinner("Initializing filters..."):
    base_df = get_worldbank_data("SP.POP.TOTL")

if base_df.empty:
    st.error("Could not load initial data to create filters.")
    st.stop()

# Get unique lists for years and countries from the base data
years = sorted(base_df["date"].unique(), reverse=True)
countries = sorted(base_df["country"].unique())

# Define the filters globally in the sidebar
selected_year = st.sidebar.slider(
    "Select Year",
    min_value=min(years),
    max_value=max(years),
    value=max(years)
)

search_selection = st.sidebar.selectbox(
    "Search for a Country",
    options=["All Countries"] + countries,
    index=0
)


st.divider()

# ============================================================
# NEW: SOCIAL DEVELOPMENT DASHBOARD (CROSS-FILTERING)
# ============================================================
if dashboard_option == "Social Development Overview":
    st.markdown("### 🧑‍🏫 Social Development — Income Equality, Education, and Health")

    # --- Fetch data ---
    with st.spinner("Loading social development indicators..."):
        gini_df = get_worldbank_data("SI.POV.GINI")       # Gini Index (income inequality)
        education_df = get_worldbank_data("SE.ADT.LITR.ZS")  # Literacy rate, adult total
        life_df = get_worldbank_data("SP.DYN.LE00.IN")       # Life expectancy at birth
        pop_df = get_worldbank_data("SP.POP.TOTL")           # Population for bubble size

    # --- Validate data ---
    if gini_df.empty or education_df.empty or life_df.empty or pop_df.empty:
        st.error("World Bank API returned no data for one of the social indicators.")
        st.stop()

    # --- Merge datasets safely ---
    merged = (
        gini_df.merge(education_df, on=["country", "countryiso3code", "date"], suffixes=("_gini", "_edu"))
                .merge(life_df, on=["country", "countryiso3code", "date"])
    )
    merged.rename(columns={"indicator_value": "life_expectancy"}, inplace=True)
    merged = merged.merge(pop_df, on=["country", "countryiso3code", "date"])
    merged.rename(columns={"indicator_value": "population"}, inplace=True)

    if merged.empty:
        st.error("No merged data available — World Bank API returned incomplete datasets.")
        st.stop()

    # --- Apply Global Filters ---
    # FIXED: Use the global 'selected_year' and 'search_selection' variables
    year_df = merged[merged["date"] == selected_year]
    if search_selection != "All Countries":
        year_df = year_df[year_df["country"] == search_selection]


    # --- Scatter Plot ---
    st.write("Click a country in the scatter plot to view its Gini Index trend over time 👇")
    fig1 = px.scatter(
        year_df.dropna(subset=["indicator_value_edu", "life_expectancy", "population", "indicator_value_gini"]),
        x="indicator_value_edu",
        y="life_expectancy",
        size="population",
        color="indicator_value_gini",
        hover_name="country",
        title=f"Education vs. Health vs. Income Equality ({selected_year})",
        labels={
            "indicator_value_edu": "Adult Literacy Rate (%)",
            "life_expectancy": "Life Expectancy (Years)",
            "indicator_value_gini": "Gini Index (Income Inequality)"
        },
        color_continuous_scale=px.colors.sequential.Viridis,
    )

    clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- Capture click selection ---
    click_selection = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        click_selection = clicked.selection.points[0]["hovertext"]

    # --- Country Trend ---
    # FIXED: Prioritize the search box selection, then the click selection
    country_for_trend = None
    if search_selection != "All Countries":
        country_for_trend = search_selection
    else:
        country_for_trend = click_selection

    if country_for_trend:
        st.subheader(f"📉 Gini Index Over Time — {country_for_trend}")
        country_df = merged[merged["country"] == country_for_trend]
        fig2 = px.line(
            country_df,
            x="date",
            y="indicator_value_gini",
            title=f"Gini Index Over Time ({country_for_trend})",
            labels={"indicator_value_gini": "Gini Index (Income Inequality)"}
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Select a country from the search box or click one in the scatter plot to view its Gini trend.")


# ============================================================
# BASIC DASHBOARD
# ============================================================
elif dashboard_option == "Population Growth":
    # --- Load data ---
    with st.spinner(f"Fetching {dashboard_option} data..."):
        df = get_worldbank_data("SP.POP.GROW")

    if df.empty:
        st.error(f"No data available for {dashboard_option}.")
        st.stop()

    # --- Apply Global Filters ---
    filtered_df = df[df["date"] == selected_year]
    if search_selection != "All Countries":
        filtered_df = filtered_df[filtered_df["country"] == search_selection]

    # --- Plotly Interactive Visualization ---
    st.subheader(f"{dashboard_option} ({selected_year})")
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
    
    with st.expander("Data Explanation"):
        st.write("""
            **GDP (Gross Domestic Product):** GDP measures the total monetary value of all goods and services produced within a country's borders over a specific period. It's a key indicator of economic health.
        """)
        st.write("""
            **Life Expectancy:** Life expectancy is the average number of years a person is expected to live based on current mortality rates. It's a key metric for gauging the health and longevity of a population.
    """)

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

    # --- Apply Global Filters ---
    year_df = merged[merged["date"] == selected_year]
    if search_selection != "All Countries":
        year_df = year_df[year_df["country"] == search_selection]

    # --- Choropleth Map ---
    st.markdown(f"#### Life Expectancy Across Countries ({selected_year})") # Use Streamlit markdown for title
    st.write("Click a country on the map to view its trends over time 👇")
    fig1 = px.choropleth(
        year_df,
        locations="countryiso3code",  # Use ISO-3 country codes for mapping
        color="indicator_value_life", # Color countries by life expectancy
        hover_name="country",         # Display full country name on hover
        hover_data={
            "countryiso3code": False,
            "indicator_value_life": ":.1f years", # Formatted life expectancy
            "indicator_value_gdp": ":,.0f USD",   # Formatted GDP
            "population": ":,.0f"                 # Formatted population
        },
        color_continuous_scale="Viridis", # A good perceptually uniform colormap
        labels={"indicator_value_life": "Life Expectancy (years)"},
    )
    # Professional map styling
    fig1.update_geos(
        showcountries=True,
        countrycolor="DarkGrey",
        showland=True,
        landcolor="lightgray",
        showocean=True,
        oceancolor="LightBlue",
        showlakes=True,
        lakecolor="LightBlue",
        projection_type="natural earth", # Natural earth projection looks good
        coastlinewidth=0.5,
        coastlinecolor="DarkGrey",
        lataxis_showgrid=False, # Hide latitude gridlines
        lonaxis_showgrid=False  # Hide longitude gridlines
    )
    fig1.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0}, # Remove margins
        coloraxis_colorbar=dict(
            title="Life Expectancy (years)", # Set a clear colorbar title
            orientation="h", # Horizontal colorbar is often cleaner at the bottom
            y=-0.1, # Position below the map
            x=0.5,
            xanchor="center",
            len=0.7 # Make it wider
        ),
        geo_bgcolor="white", # Ensure background is white
    )
    
    clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- Capture click selection ---
    click_selection = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        click_selection = clicked.selection.points[0]["hovertext"]

    # --- Country Trend Charts ---
    country_for_trend = search_selection if search_selection != "All Countries" else click_selection

    if country_for_trend:
        st.subheader(f"📈 Economic & Population Trends — {country_for_trend}")
        country_df = merged[merged["country"] == country_for_trend]

        col1, col2 = st.columns(2)

        with col1:
            # Chart 1: GDP Trend
            fig2 = px.line(
                country_df,
                x="date",
                y="indicator_value_gdp",
                title=f"GDP per Capita Over Time",
                labels={"indicator_value_gdp": "GDP per capita (US$)"},
            )
            st.plotly_chart(fig2, use_container_width=True)

        with col2:
            # Chart 2: Population Trend
            fig3 = px.line(
                country_df,
                x="date",
                y="population",
                title=f"Population Over Time",
                labels={"population": "Total Population"},
                color_discrete_sequence=['#FF8C00'] # Orange color for contrast
            )
            st.plotly_chart(fig3, use_container_width=True)
            
    else:
        st.info("Select a country from the search box or click one on the map to view its trends.")