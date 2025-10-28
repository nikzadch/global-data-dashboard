import streamlit as st
import plotly.express as px
from api import get_data, get_worldbank_data
from utils import fetch_and_merge_data, calculate_fairness_score

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
    [data-baseweb="tooltip"] {
    display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
# --- Dashboard selection ---
dashboard_option = st.sidebar.selectbox(
    "Select Dashboard:",
    [ "Economic Overview", "Social Development Overview", "Fairness & Development", "Government Debt (IMF)", "Country Comparison"]
)

# ============================================================
# GLOBAL FILTERS
# ============================================================
# Fetch a base dataset to populate filters, ensuring they are always available.
# Population data is a good general-purpose choice for broad country/year coverage.
with st.spinner("Initializing filters..."):
    base_df = get_data("WB_SP.POP.TOTL")

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
    st.markdown("### 🩺 Social Development — Health Expenditure vs. Life Expectancy")

    # --- Fetch data ---
    with st.spinner("Loading social development indicators..."):
        life_df = get_data("WB_SP.DYN.LE00.IN")        # Life expectancy at birth
        health_df = get_data("WB_SH.XPD.CHEX.PC.CD")   # Current health expenditure per capita (USD)
        pop_df = get_data("WB_SP.POP.TOTL")            # Population for hover data

    # --- Validate data ---
    if life_df.empty or health_df.empty or pop_df.empty:
        st.error("World Bank API returned no data for one of the social indicators.")
        st.stop()

    # --- Merge datasets safely ---
    merged = (
        life_df.merge(health_df, on=["country", "countryiso3code", "date"], suffixes=("_life", "_health"))
               .merge(pop_df, on=["country", "countryiso3code", "date"])
    )
    merged.rename(columns={
        "indicator_value_life": "life_expectancy",
        "indicator_value_health": "health_expenditure",
        "indicator_value": "population"
    }, inplace=True)

    if merged.empty:
        st.error("No merged data available — World Bank API returned incomplete datasets.")
        st.stop()

    # --- Apply Global Filters ---
    year_df = merged[merged["date"] == selected_year]
    if search_selection != "All Countries":
        year_df = year_df[year_df["country"] == search_selection]

    # --- Bubble Map (px.scatter_geo) ---
    st.markdown(f"#### Health Expenditure vs. Life Expectancy ({selected_year})")
    st.write("Click a country on the map to view its health expenditure trend over time 👇")
    
    fig1 = px.scatter_geo(
        year_df, # Use the globally filtered dataframe
        locations="countryiso3code",
        color="life_expectancy",
        size="health_expenditure",
        hover_name="country",
        hover_data={
            "countryiso3code": False,
            "life_expectancy": ":.1f years",
            "health_expenditure": ":,.0f USD",
            "population": ":,.0f"
        },
        projection="natural earth",
        title=f"Bubble size represents Health Expenditure per Capita (USD)",
        color_continuous_scale="Plasma",
        labels={
            "life_expectancy": "Life Expectancy (Years)",
            "health_expenditure": "Health Expenditure per Capita (USD)"
        }
    )
    
    fig1.update_geos(
        showcountries=True,
        countrycolor="DarkGrey",
        showland=True,
        landcolor="lightgray",
        showocean=True,
        oceancolor="LightBlue",
        showlakes=True,
        lakecolor="LightBlue",
        projection_type="natural earth",
        coastlinewidth=0.5,
        coastlinecolor="DarkGrey",
        lataxis_showgrid=False,
        lonaxis_showgrid=False
    )
    fig1.update_layout(
        margin={"r":0,"t":40,"l":0,"b":0}, # Title is now part of the fig, so t=40
        coloraxis_colorbar=dict(
            title="Life Expectancy (years)",
            orientation="h",
            y=-0.1,
            x=0.5,
            xanchor="center",
            len=0.7
        ),
        geo_bgcolor="white",
    )

    clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- Capture click selection ---
    click_selection = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        click_selection = clicked.selection.points[0]["hovertext"]

    # --- Country Trend ---
    country_for_trend = search_selection if search_selection != "All Countries" else click_selection

    if country_for_trend:
        st.subheader(f"💸 Health Expenditure Over Time — {country_for_trend}")
        country_df = merged[merged["country"] == country_for_trend]
        
        if country_df.dropna(subset=['health_expenditure']).empty:
             st.warning(f"No health expenditure trend data available for {country_for_trend}.")
        else:
            fig2 = px.line(
                country_df,
                x="date",
                y="health_expenditure",
                title=f"Health Expenditure per Capita Over Time ({country_for_trend})",
                labels={"health_expenditure": "Health Expenditure per Capita (USD)"}
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Select a country from the search box or click one on the map to view its health expenditure trend.")


# ============================================================
# Government Debt (IMF) DASHBOARD
# ============================================================
elif dashboard_option == "Government Debt (IMF)":
    st.markdown("### 🏛️ General Government Gross Debt (% of GDP)")
    st.markdown("Data sourced from the **International Monetary Fund (IMF)** via its DataMapper API.")

    # --- 1. Fetch data (ALL years) ---
    with st.spinner("Loading IMF debt data for all years..."):
        # We call get_data with the IMF code.
        # The 'date' param is passed to the function, which will
        # fetch all data and then filter it.
        all_imf_data = get_data(
            indicator_code="IMF_GGXWDG_NGDP", # General government gross debt
            countries="all", # Pass 'all' so the function filters by country *after* fetching
            date=f"{min(years)}:{max(years)}"
        )

    # --- 2. Validate data ---
    if all_imf_data.empty:
        st.error("IMF API returned no data for the Government Debt indicator.")
        st.stop()

    # --- 3. Apply Global Filters ---
    year_df = all_imf_data[all_imf_data["date"] == selected_year]
    
    if year_df.empty:
        st.warning(f"No IMF debt data available for {selected_year}.")
        st.stop()
        
    map_df = year_df.copy()
    # The 'search_selection' filter will be used for the trend chart
    
    # --- 4. Bubble Map (px.scatter_geo) ---
    st.markdown(f"#### Government Debt as % of GDP ({selected_year})")
    st.write("Click a country on the map to view its debt trend over time 👇")
    
    fig1 = px.scatter_geo(
        map_df, 
        locations="countryiso3code",
        color="indicator_value",
        size="indicator_value", # Size bubbles by the debt value
        hover_name="country",
        hover_data={
            "countryiso3code": False,
            "indicator_value": ":.1f%", # Format as percentage
        },
        projection="natural earth",
        title=f"Bubble size represents debt as % of GDP",
        color_continuous_scale=px.colors.sequential.YlOrRd, # Red scale for debt
        labels={
            "indicator_value": "Debt (% of GDP)"
        }
    )
    
    # Apply your preferred map styling
    fig1.update_geos(
        showcountries=True, countrycolor="DarkGrey",
        showland=True, landcolor="lightgray",
        showocean=True, oceancolor="LightBlue",
        showlakes=True, lakecolor="LightBlue",
        projection_type="natural earth",
        coastlinewidth=0.5, coastlinecolor="DarkGrey",
        lataxis_showgrid=False, lonaxis_showgrid=False
    )
    fig1.update_layout(
        margin={"r":0,"t":40,"l":0,"b":0},
        coloraxis_colorbar=dict(
            title="Debt (% of GDP)",
            orientation="h", y=-0.1, x=0.5,
            xanchor="center", len=0.7
        ),
        geo_bgcolor="white",
    )

    clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- 5. Capture click selection ---
    click_selection = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        click_selection = clicked.selection.points[0]["hovertext"]

    # --- 6. Country Trend ---
    country_for_trend = search_selection if search_selection != "All Countries" else click_selection

    if country_for_trend:
        st.subheader(f"📈 Government Debt Over Time — {country_for_trend}")
        
        # Use the original full dataset (all_imf_data) for the trend
        country_df = all_imf_data[all_imf_data["country"] == country_for_trend]
        
        if country_df.dropna(subset=['indicator_value']).empty:
             st.warning(f"No debt trend data available for {country_for_trend}.")
        else:
            fig2 = px.line(
                country_df.sort_values(by="date"), # Sort by date for a clean line
                x="date",
                y="indicator_value",
                title=f"Government Debt as % of GDP ({country_for_trend})",
                labels={"indicator_value": "Debt (% of GDP)"}
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Select a country from the search box or click one on the map to view its trend.")

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
        gdp_df = get_data("WB_NY.GDP.PCAP.CD")      # GDP per capita
        life_df = get_data("WB_SP.DYN.LE00.IN")    # Life Expectancy at Birth
        pop_df = get_data("WB_SP.POP.TOTL")        # Population total

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


# ============================================================
# Fairness & Development (CROSS-FILTER DASHBOARD)
# ============================================================      # app.py -> Add this as a new elif block
elif dashboard_option == "Fairness & Development":
    st.markdown("### 📈 Development & Equality Index")
    st.markdown("""
    This score combines metrics for income fairness, gender equality, governance, education, health, and basic opportunity. 
    **A higher score (and larger bubble) indicates better overall performance.**
    """)

    with st.spinner("Fetching and processing all time-series data..."):
        # 1. Fetch ALL data (no year filter)
        all_data = fetch_and_merge_data()
        
        if all_data.empty:
            st.error("Could not retrieve any data for the required indicators.")
            st.stop()
            
        # 2. Calculate scores for ALL data
        score_df, components_df = calculate_fairness_score(all_data.copy())

        if score_df.empty:
            st.warning("No data available to display after calculations.")
            st.stop()

    # --- 3. Apply Global Filters (THE FIX) ---
    # Filter by selected year *after* all calculations
    year_df = score_df[score_df["date"] == selected_year]
    
    if year_df.empty:
        st.warning(f"No countries had complete data for all 6 indicators in {selected_year}. Please try another year.")
        st.stop()

    # Create a separate df for the map that isn't filtered by country
    map_df = year_df.copy() 
    
    # Apply country filter *only* to the data table (if selected)
    if search_selection != "All Countries":
        year_df = year_df[year_df["country"] == search_selection]

    # --- 4. Bubble Map (px.scatter_geo) - THE "UGLY" FIX ---
    st.markdown(f"#### Development & Equality Index Score ({selected_year})")
    st.write("Click a country on the map to view its score component trends over time 👇")
    
    fig1 = px.scatter_geo(
        map_df, # Use the year-filtered, non-country-filtered data
        locations="countryiso3code",
        color="fairness_score",
        size="fairness_score", # Bubble size based on the score itself
        hover_name="country",
        hover_data={
            "countryiso3code": False,
            "fairness_score": ":.2f",
            "life_expectancy": ":.1f years",
            "gini": ":.1f",
        },
        projection="natural earth",
        title=f"Bubble size represents the total score",
        color_continuous_scale="Viridis", # Changed from Plasma for better contrast
        labels={
            "fairness_score": "Index Score (0-6)",
            "life_expectancy": "Life Expectancy",
            "gini": "Gini Index"
        }
    )
    
    # Apply your exact styling from the "Social Development" dashboard
    fig1.update_geos(
        showcountries=True, countrycolor="DarkGrey",
        showland=True, landcolor="lightgray",
        showocean=True, oceancolor="LightBlue",
        showlakes=True, lakecolor="LightBlue",
        projection_type="natural earth",
        coastlinewidth=0.5, coastlinecolor="DarkGrey",
        lataxis_showgrid=False, lonaxis_showgrid=False
    )
    fig1.update_layout(
        margin={"r":0,"t":40,"l":0,"b":0},
        coloraxis_colorbar=dict(
            title="Index Score",
            orientation="h", y=-0.1, x=0.5,
            xanchor="center", len=0.7
        ),
        geo_bgcolor="white",
    )

    # Add click event
    clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- 5. Capture click selection ---
    click_selection = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        click_selection = clicked.selection.points[0]["hovertext"]

    # --- 6. Country Trend ---
    country_for_trend = search_selection if search_selection != "All Countries" else click_selection

    if country_for_trend:
        st.subheader(f"📊 Score Components Over Time — {country_for_trend}")
        # Use the full, un-filtered components_df
        country_df = components_df[components_df["country"] == country_for_trend]
        
        if country_df.empty:
            st.warning(f"No trend data available for {country_for_trend}.")
        else:
            # Melt data for plotting
            plot_data = country_df.melt(
                id_vars=['date'], 
                value_vars=components_df.columns.drop(['country', 'countryiso3code', 'date']),
                var_name='Component', 
                value_name='Normalized Score (0-1)'
            )
            # Clean up names
            plot_data['Component'] = plot_data['Component'].str.replace('norm_', '').str.replace('_', ' ').str.title()
            
            fig2 = px.line(
                plot_data,
                x="date",
                y="Normalized Score (0-1)",
                color="Component",
                title=f"Score Component Trends for {country_for_trend}"
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Select a country from the search box or click one on the map to view its component trends.")

    # --- 7. Data Table Section ---
    with st.expander("View Score Data for All Countries"):
        st.dataframe(
            map_df.sort_values("fairness_score", ascending=False)
            [['country', 'date', 'fairness_score', 'life_expectancy', 'gini', 'governance']]
            .reset_index(drop=True)
        )

# ============================================================
# Country Comparison Dashboard
# ============================================================         
elif dashboard_option == "Country Comparison":
    st.markdown("### 📈 Head-to-Head Country Comparison")

    # --- 1. Dashboard-Specific Country Selectors ---
    col1, col2 = st.columns(2)
    with col1:
        # Set safe defaults
        default_a = "United States" if "United States" in countries else countries[0]
        selected_country_a = st.selectbox(
            "Select Country A",
            options=countries,
            index=countries.index(default_a)
        )
    with col2:
        default_b = "China" if "China" in countries else countries[1]
        selected_country_b = st.selectbox(
            "Select Country B",
            options=countries,
            index=countries.index(default_b)
        )
    
    st.markdown(f"#### Comparing: **{selected_country_a}** vs. **{selected_country_b}**")


    # --- 2. Define Metrics and Fetch Data ---
    indicators = {
        "GDP per capita (USD)": {
            "code": "WB_NY.GDP.PCAP.CD", 
            "label": "GDP per capita (Current USD)"
        },
        "Inflation (Annual %)": {
            "code": "IMF_PCPIPCH", 
            "label": "Inflation, Avg. Consumer Prices (Annual %)"
        },
        "Government Debt (% of GDP)": {
            "code": "IMF_GGXWDG_NGDP", 
            "label": "General Gov. Gross Debt (% of GDP)"
        },
        "Life Expectancy (Years)": {
            "code": "WB_SP.DYN.LE00.IN", 
            "label": "Life Expectancy at Birth (Years)"
        }
    }
    
    # Fetch data for all 4 indicators
    with st.spinner(f"Loading comparison data for {selected_country_a} and {selected_country_b}..."):
        data_frames = {}
        for metric_name, info in indicators.items():
            # Get data for ALL years (ignoring global country filter)
            all_data = get_data(
                indicator_code=info["code"],
                countries="all"
            )
            # Filter for only the two selected countries
            if not all_data.empty:
                filtered_df = all_data[
                    all_data['country'].isin([selected_country_a, selected_country_b])
                ]
                data_frames[metric_name] = filtered_df
            else:
                data_frames[metric_name] = pd.DataFrame() # Empty
    

    # --- 3. Create 2x2 Grid for Charts ---
    chart_col1, chart_col2 = st.columns(2)

    # --- Plot Chart 1: GDP per capita ---
    with chart_col1:
        metric_name = "GDP per capita (USD)"
        df = data_frames[metric_name]
        if df.empty or df.shape[0] < 2:
            st.warning(f"No comparison data available for {metric_name}.")
        else:
            fig_gdp = px.line(
                df, x="date", y="indicator_value", color="country",
                title=metric_name, 
                labels={"indicator_value": "USD per capita"}
            )
            fig_gdp.add_vline(x=selected_year, line_width=2, line_dash="dash", line_color="red")
            fig_gdp.update_layout(hovermode="x unified")
            st.plotly_chart(fig_gdp, use_container_width=True)

    # --- Plot Chart 2: Inflation ---
    with chart_col2:
        metric_name = "Inflation (Annual %)"
        df = data_frames[metric_name]
        if df.empty or df.shape[0] < 2:
            st.warning(f"No comparison data available for {metric_name}.")
        else:
            fig_inf = px.line(
                df, x="date", y="indicator_value", color="country",
                title=metric_name, 
                labels={"indicator_value": "Annual % Change"}
            )
            fig_inf.add_vline(x=selected_year, line_width=2, line_dash="dash", line_color="red")
            fig_inf.update_layout(hovermode="x unified")
            st.plotly_chart(fig_inf, use_container_width=True)

    # --- Plot Chart 3: Government Debt ---
    with chart_col1:
        metric_name = "Government Debt (% of GDP)"
        df = data_frames[metric_name]
        if df.empty or df.shape[0] < 2:
            st.warning(f"No comparison data available for {metric_name}.")
        else:
            fig_debt = px.line(
                df, x="date", y="indicator_value", color="country",
                title=metric_name, 
                labels={"indicator_value": "% of GDP"}
            )
            fig_debt.add_vline(x=selected_year, line_width=2, line_dash="dash", line_color="red")
            fig_debt.update_layout(hovermode="x unified")
            st.plotly_chart(fig_debt, use_container_width=True)
            
    # --- Plot Chart 4: Life Expectancy ---
    with chart_col2:
        metric_name = "Life Expectancy (Years)"
        df = data_frames[metric_name]
        if df.empty or df.shape[0] < 2:
            st.warning(f"No comparison data available for {metric_name}.")
        else:
            fig_life = px.line(
                df, x="date", y="indicator_value", color="country",
                title=metric_name, 
                labels={"indicator_value": "Years"}
            )
            fig_life.add_vline(x=selected_year, line_width=2, line_dash="dash", line_color="red")
            fig_life.update_layout(hovermode="x unified")
            st.plotly_chart(fig_life, use_container_width=True)