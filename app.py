import streamlit as st
import plotly.express as px
from api import get_data, get_worldbank_data
from utils import fetch_and_merge_data, calculate_fairness_score
import pandas as pd

st.set_page_config(page_title="World Bank Dashboards", layout="wide")

st.title("🌍 Interactive Wold Dashboards")

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
    [ "Economic Overview", "Social Development Overview", "Fairness & Development", "Government Debt (IMF)",
      "Country Comparison"]
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
# SOCIAL DEVELOPMENT DASHBOARD (CROSS-FILTERING)
# ============================================================
if dashboard_option == "Social Development Overview":
    st.markdown("### 🩺 Social Development Overview — Cross-Country & Trend Analysis")

    with st.expander("About This Data"):
        st.write("""
            This dashboard provides a high-level overview of global social development indicators from the World Bank.
            * **Life Expectancy:** The average number of years a person is expected to live.
            * **Health Expenditure per capita:** The amount of money spent on healthcare per person, in US dollars.
            * **Education Expenditure:** Government spending on education as a percentage of its total GDP.
            * **Access to Sanitation:** The percentage of the population using at least basic sanitation services.
            * **Population:** The total number of people living in the country.
        """)

    # --- Fetch data ---
    with st.spinner("Loading social development indicators from World Bank API..."):
        life_df = get_data("WB_SP.DYN.LE00.IN")        # Life expectancy at birth
        health_df = get_data("WB_SH.XPD.CHEX.PC.CD")  # Current health expenditure per capita (USD)
        pop_df = get_data("WB_SP.POP.TOTL")           # Population for hover data
        edu_df = get_data("WB_SE.XPD.TOTL.GD.ZS")     # Government expenditure on education, total (% of GDP)
        sani_df = get_data("WB_SH.STA.BASS.ZS")       # Access to basic sanitation services (% of population)

    # --- Validate data ---
    if life_df.empty and health_df.empty and pop_df.empty and edu_df.empty and sani_df.empty:
        st.error("World Bank API returned no data for any of the social indicators. Please try again later.")
        st.stop()

    # --- [FIXED] Merge datasets ---
    # Rename 'indicator_value' in each df before merging to avoid conflicts
    life_df.rename(columns={"indicator_value": "life_expectancy"}, inplace=True)
    health_df.rename(columns={"indicator_value": "health_expenditure"}, inplace=True)
    pop_df.rename(columns={"indicator_value": "population"}, inplace=True)
    edu_df.rename(columns={"indicator_value": "education_expenditure_gdp"}, inplace=True)
    sani_df.rename(columns={"indicator_value": "access_to_sanitation"}, inplace=True)

    # Use 'outer' joins to keep all data, even if some indicators are missing
    # Start with life_df as the base
    merged = life_df
    
    # List of other dataframes to merge
    other_dfs = [health_df, pop_df, edu_df, sani_df]
    
    for df in other_dfs:
        # Check if df is not empty before merging
        if not df.empty:
            merged = merged.merge(
                df, 
                on=["country", "countryiso3code", "date"], 
                how="outer"
            )

    if merged.empty:
        st.error("No merged data available — World Bank API returned incomplete datasets.")
        st.stop()

    # Sort by date to make trend calculations easier
    merged.sort_values(by="date", ascending=False, inplace=True)

    # --- Apply Global Filters ---
    year_df = merged[merged["date"] == selected_year]
    if search_selection != "All Countries":
        year_df = year_df[year_df["country"] == search_selection]

    # --- Bubble Map (px.scatter_geo) ---
    with st.container(border=True):
        st.markdown(f"#### Health Expenditure vs. Life Expectancy ({selected_year})")
        st.write("Bubble size represents Health Expenditure per Capita (USD). Click a country to see details. 👇")
        
        # [FIXED] Drop rows where EITHER color or size values are NaN, essential for plotting
        plot_df = year_df.dropna(subset=['life_expectancy', 'health_expenditure'])
        
        if plot_df.empty:
            st.warning(f"No data available for 'Health Expenditure' and 'Life Expectancy' for {selected_year}.")
        
        fig1 = px.scatter_geo(
            plot_df, # Use the cleaned dataframe
            locations="countryiso3code",
            color="life_expectancy",
            size="health_expenditure",
            hover_name="country",
            hover_data={
                "countryiso3code": False,
                "life_expectancy": ":.1f years",
                "health_expenditure": ":,.0f USD",
                "education_expenditure_gdp": ":.1f %",
                "access_to_sanitation": ":.1f %",
                "population": ":,.0f"
            },
            projection="natural earth",
            color_continuous_scale="Plasma",
            labels={
                "life_expectancy": "Life Expectancy (Years)",
                "health_expenditure": "Health Exp. per Capita (USD)",
                "education_expenditure_gdp": "Education Exp. (% GDP)",
                "access_to_sanitation": "Sanitation Access (%)"
            }
        )
        
        fig1.update_geos(
            showcountries=True, countrycolor="DarkGrey",
            showland=True, landcolor="rgb(243, 243, 243)",
            showocean=True, oceancolor="rgb(217, 237, 247)",
            showlakes=True, lakecolor="rgb(217, 237, 247)",
            projection_type="natural earth",
            coastlinewidth=0.5, coastlinecolor="DarkGrey",
            lataxis_showgrid=False, lonaxis_showgrid=False
        )
        fig1.update_layout(
            margin={"r":0,"t":25,"l":0,"b":0},
            coloraxis_colorbar=dict(
                title="Life Expectancy",
                orientation="h",
                y=-0.1,
                x=0.5,
                xanchor="center",
                len=0.7
            ),
            geo_bgcolor="rgba(0,0,0,0)", # Transparent background
            paper_bgcolor="rgba(0,0,0,0)",
        )

        clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- Capture click selection ---
    click_selection = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        click_selection = clicked.selection.points[0]["hovertext"]

    # --- Country Trend ---
    country_for_trend = search_selection if search_selection != "All Countries" else click_selection

    if country_for_trend:
        st.subheader(f"📊 Key Metrics & Trends — {country_for_trend}")
        country_df = merged[merged["country"] == country_for_trend]

        # --- NEW: Key Metrics Block ---
        with st.container(border=True):
            # Get data for selected year and previous year
            current_data = country_df[country_df["date"] == selected_year]
            prev_year_data = country_df[country_df["date"] == (selected_year - 1)]

            # Helper function to safely get metric values and deltas
            def get_metric_values(metric_name):
                current_val = current_data[metric_name].iloc[0] if not current_data.empty and metric_name in current_data.columns else None
                prev_val = prev_year_data[metric_name].iloc[0] if not prev_year_data.empty and metric_name in prev_year_data.columns else None
                
                delta = None
                if current_val is not None and prev_val is not None and pd.notna(current_val) and pd.notna(prev_val):
                    if prev_val != 0:
                        delta = current_val - prev_val
                    else:
                        delta = current_val # Avoid division by zero, show absolute change
                return current_val, delta

            # Get all metric values
            life_val, life_delta = get_metric_values("life_expectancy")
            health_val, health_delta = get_metric_values("health_expenditure")
            edu_val, edu_delta = get_metric_values("education_expenditure_gdp")
            sani_val, sani_delta = get_metric_values("access_to_sanitation")
            pop_val, pop_delta = get_metric_values("population")

            # Display metrics in 5 columns
            met1, met2, met3, met4, met5 = st.columns(5)
            with met1:
                st.metric(
                    label=f"Life Expectancy ({selected_year})",
                    value=f"{life_val:.1f} yrs" if pd.notna(life_val) else "N/A",
                    delta=f"{life_delta:.1f} yrs" if pd.notna(life_delta) else None,
                )
            with met2:
                st.metric(
                    label=f"Health Exp/capita ({selected_year})",
                    value=f"${health_val:,.0f}" if pd.notna(health_val) else "N/A",
                    delta=f"${health_delta:,.0f}" if pd.notna(health_delta) else None,
                )
            with met3:
                st.metric(
                    label=f"Education Exp. (% GDP, {selected_year})",
                    value=f"{edu_val:.1f} %" if pd.notna(edu_val) else "N/A",
                    delta=f"{edu_delta:.1f} %" if pd.notna(edu_delta) else None,
                )
            with met4:
                st.metric(
                    label=f"Sanitation Access ({selected_year})",
                    value=f"{sani_val:.1f} %" if pd.notna(sani_val) else "N/A",
                    delta=f"{sani_delta:.1f} %" if pd.notna(sani_delta) else None,
                )
            with met5:
                st.metric(
                    label=f"Population ({selected_year})",
                    value=f"{pop_val:,.0f}" if pd.notna(pop_val) else "N/A",
                    delta=f"{pop_delta:,.0f}" if pd.notna(pop_delta) else None,
                )

        # --- NEW: Trend Charts in Tabs ---
        tab_life, tab_health, tab_edu, tab_sani, tab_pop = st.tabs([
            "🧬 Life Expectancy", "💸 Health Expenditure", "🎓 Education Exp.", "🚽 Sanitation", "👥 Population"
        ])

        # Helper to create clean trend charts
        def create_trend_chart(df, y_col, title, y_label, color, format_str):
            # Ensure data is sorted by date for a clean line chart
            df_sorted = df.sort_values(by="date")
            
            # Check if column exists and has data
            if y_col not in df_sorted.columns or df_sorted[y_col].dropna().empty:
                st.warning(f"No trend data available for '{y_label}'.")
                return None

            fig = px.line(
                df_sorted.dropna(subset=[y_col]), # Drop rows where this specific metric is NA
                x="date", y=y_col,
                title=title,
                labels={"date": "Year", y_col: y_label},
                color_discrete_sequence=[color]
            )
            fig.update_layout(template="plotly_white", title_x=0.5, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_traces(hovertemplate=f"Year: %{{x}}<br>{y_label}: %{{y:{format_str}}}<extra></extra>")
            return fig

        with tab_life:
            fig_life = create_trend_chart(country_df, "life_expectancy", "Life Expectancy Over Time", "Life Expectancy (years)", '#1f77b4', '.1f')
            if fig_life: st.plotly_chart(fig_life, use_container_width=True)
            
        with tab_health:
            fig_health = create_trend_chart(country_df, "health_expenditure", "Health Expenditure per Capita Over Time", "Health Exp. per Capita (USD)", '#d62728', ',.0f')
            if fig_health: st.plotly_chart(fig_health, use_container_width=True)
            
        with tab_edu:
            fig_edu = create_trend_chart(country_df, "education_expenditure_gdp", "Education Expenditure (% of GDP) Over Time", "Education Exp. (% of GDP)", '#2ca02c', '.1f')
            if fig_edu: st.plotly_chart(fig_edu, use_container_width=True)

        with tab_sani:
            fig_sani = create_trend_chart(country_df, "access_to_sanitation", "Access to Basic Sanitation Over Time", "Access to Sanitation (%)", '#9467bd', '.1f')
            if fig_sani: st.plotly_chart(fig_sani, use_container_width=True)
            
        with tab_pop:
            fig_pop = create_trend_chart(country_df, "population", "Population Over Time", "Total Population", '#ff7f0e', ',.0f')
            if fig_pop: st.plotly_chart(fig_pop, use_container_width=True)
            
    else:
        st.info("Select a country from the search box or click one on the map to view its detailed metrics and trends.")


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
    st.markdown("### 💹 Economic Overview — Cross-Country & Trend Analysis")
    
    with st.expander("About This Data"):
        st.write("""
            This dashboard provides a high-level overview of global economic and development indicators from the World Bank.
            * **GDP (Gross Domestic Product) per capita:** Measures the total economic output of a country, divided by its population.
            * **GNI (Gross National Income) per capita:** Similar to GDP, but also includes income earned by residents from overseas investments.
            * **Life Expectancy:** The average number of years a person is expected to live.
            * **Population:** The total number of people living in the country.
            * **CO2 Emissions (per capita):** Carbon dioxide (CO2) emissions excluding LULUCF (land use, land-use change, and forestry) per capita. A key environmental indicator.
        """)

    # --- Fetch data ---
    # We add GNI and CO2 emissions to the data pull
    with st.spinner("Loading economic indicators from World Bank API..."):
        gdp_df = get_data("WB_NY.GDP.PCAP.CD")      # GDP per capita
        life_df = get_data("WB_SP.DYN.LE00.IN")    # Life Expectancy at Birth
        pop_df = get_data("WB_SP.POP.TOTL")        # Population total
        gni_df = get_data("WB_NY.GNP.PCAP.CD")     # GNI per capita
        # UPDATED INDICATOR: EN.ATM.CO2E.PC is no longer available.
        # Using EN.GHG.CO2.PC.CE.AR5 (CO2 emissions excl. LULUCF per capita) instead.
        co2_df = get_data("WB_EN.GHG.CO2.PC.CE.AR5") # CO2 emissions (metric tons per capita)

    # --- Validate data ---
    if gdp_df.empty or life_df.empty or pop_df.empty or gni_df.empty or co2_df.empty:
        st.error("World Bank API returned no data for one or more key indicators. Please try again later.")
        st.stop()

    # --- Merge datasets ---
    # We follow your original merge logic, which suffixes and renames the final 'indicator_value'
    # This can be complex, so we'll merge and rename all ambiguous columns for clarity.
    
    # Merge gdp + life
    merged = gdp_df.merge(life_df, on=["country", "countryiso3code", "date"], suffixes=("_gdp", "_life"))
    
    # Merge in pop
    merged = merged.merge(pop_df, on=["country", "countryiso3code", "date"])
    # 'indicator_value' is now from pop_df, let's rename it
    merged.rename(columns={"indicator_value": "population"}, inplace=True)
    
    # Merge in gni
    merged = merged.merge(gni_df, on=["country", "countryiso3code", "date"])
    # 'indicator_value' is now from gni_df
    merged.rename(columns={"indicator_value": "gni_per_capita"}, inplace=True)
    
    # Merge in co2
    merged = merged.merge(co2_df, on=["country", "countryiso3code", "date"])
    # 'indicator_value' is now from co2_df
    merged.rename(columns={"indicator_value": "co2_emissions_pc"}, inplace=True)

    # Rename the first two columns that had suffixes
    merged.rename(columns={
        "indicator_value_gdp": "gdp_per_capita",
        "indicator_value_life": "life_expectancy"
    }, inplace=True)
    
    if merged.empty:
        st.error("No merged data available — World Bank API returned incomplete datasets.")
        st.stop()
    
    # Sort by date to make trend calculations easier
    merged.sort_values(by="date", ascending=False, inplace=True)

    # --- Apply Global Filters ---
    year_df = merged[merged["date"] == selected_year]
    if search_selection != "All Countries":
        year_df = year_df[year_df["country"] == search_selection]

    # --- Choropleth Map ---
    with st.container(border=True):
        st.markdown(f"#### 🌎 Global Development Indicators ({selected_year})")
        st.write("Click a country on the map to view its detailed metrics and trends below 👇")
        fig1 = px.choropleth(
            year_df,
            locations="countryiso3code",
            color="life_expectancy",
            hover_name="country",
            hover_data={
                "countryiso3code": False,
                "life_expectancy": ":.1f years",
                "gdp_per_capita": ":,.0f USD",
                "gni_per_capita": ":,.0f USD",
                "population": ":,.0f",
                "co2_emissions_pc": ":.2f tons"
            },
            color_continuous_scale="Viridis",
            labels={
                "life_expectancy": "Life Expectancy (years)",
                "gdp_per_capita": "GDP per capita (USD)",
                "gni_per_capita": "GNI per capita (USD)",
                "population": "Population",
                "co2_emissions_pc": "CO2 Emissions (tons/capita)"
            },
        )
        # Use your professional map styling
        fig1.update_geos(
            showcountries=True, countrycolor="DarkGrey",
            showland=True, landcolor="rgb(243, 243, 243)",
            showocean=True, oceancolor="rgb(217, 237, 247)",
            showlakes=True, lakecolor="rgb(217, 237, 247)",
            projection_type="natural earth",
            coastlinewidth=0.5, coastlinecolor="DarkGrey",
            lataxis_showgrid=False, lonaxis_showgrid=False
        )
        fig1.update_layout(
            margin={"r":0,"t":25,"l":0,"b":0},
            coloraxis_colorbar=dict(
                title="Life Expectancy",
                orientation="h",
                y=-0.1,
                x=0.5,
                xanchor="center",
                len=0.7
            ),
            geo_bgcolor="rgba(0,0,0,0)", # Transparent background
            paper_bgcolor="rgba(0,0,0,0)",
        )
        
        clicked = st.plotly_chart(fig1, use_container_width=True, on_select="rerun")

    # --- Capture click selection ---
    click_selection = None
    if clicked and clicked.selection and len(clicked.selection.points) > 0:
        # Get the 'hover_name' which we set to be the country name
        click_selection = clicked.selection.points[0]["hovertext"]

    # --- Country Trend Charts & Metrics ---
    # Determine the country to focus on
    country_for_trend = search_selection if search_selection != "All Countries" else click_selection

    if country_for_trend:
        st.subheader(f"📊 Key Metrics & Trends — {country_for_trend}")
        country_df = merged[merged["country"] == country_for_trend]

        # --- NEW: Key Metrics Block ---
        with st.container(border=True):
            # Get data for selected year and previous year
            current_data = country_df[country_df["date"] == selected_year]
            prev_year_data = country_df[country_df["date"] == (selected_year - 1)]

            # Helper function to safely get metric values and deltas
            def get_metric_values(metric_name):
                current_val = current_data[metric_name].iloc[0] if not current_data.empty else None
                prev_val = prev_year_data[metric_name].iloc[0] if not prev_year_data.empty else None
                
                delta = None
                if current_val is not None and prev_val is not None:
                    if prev_val != 0:
                        delta = current_val - prev_val
                    else:
                        delta = current_val # Avoid division by zero, show absolute change
                return current_val, delta

            # Get all metric values
            life_val, life_delta = get_metric_values("life_expectancy")
            gdp_val, gdp_delta = get_metric_values("gdp_per_capita")
            gni_val, gni_delta = get_metric_values("gni_per_capita")
            pop_val, pop_delta = get_metric_values("population")
            co2_val, co2_delta = get_metric_values("co2_emissions_pc")

            # Display metrics in 5 columns
            met1, met2, met3, met4, met5 = st.columns(5)
            with met1:
                st.metric(
                    label=f"Life Expectancy ({selected_year})",
                    value=f"{life_val:.1f} yrs" if life_val is not None else "N/A",
                    delta=f"{life_delta:.1f} yrs" if life_delta is not None else None,
                )
            with met2:
                st.metric(
                    label=f"GDP per capita ({selected_year})",
                    value=f"${gdp_val:,.0f}" if gdp_val is not None else "N/A",
                    delta=f"${gdp_delta:,.0f}" if gdp_delta is not None else None,
                )
            with met3:
                st.metric(
                    label=f"GNI per capita ({selected_year})",
                    value=f"${gni_val:,.0f}" if gni_val is not None else "N/A",
                    delta=f"${gni_delta:,.0f}" if gni_delta is not None else None,
                )
            with met4:
                st.metric(
                    label=f"Population ({selected_year})",
                    value=f"{pop_val:,.0f}" if pop_val is not None else "N/A",
                    delta=f"{pop_delta:,.0f}" if pop_delta is not None else None,
                )
            with met5:
                st.metric(
                    label=f"CO2 Emissions/capita ({selected_year})",
                    value=f"{co2_val:.2f} tons" if co2_val is not None else "N/A",
                    delta=f"{co2_delta:.2f} tons" if co2_delta is not None else None,
                    delta_color="inverse" # Higher emissions are "bad"
                )

        # --- NEW: Trend Charts in Tabs ---
        tab_life, tab_gdp, tab_gni, tab_pop, tab_co2 = st.tabs([
            "🧬 Life Expectancy", "💰 GDP per capita", "📈 GNI per capita", "👥 Population", "💨 CO2 Emissions"
        ])

        # Helper to create clean trend charts
        def create_trend_chart(df, y_col, title, y_label, color, format_str):
            fig = px.line(
                df, x="date", y=y_col,
                title=title,
                labels={"date": "Year", y_col: y_label},
                color_discrete_sequence=[color]
            )
            fig.update_layout(template="plotly_white", title_x=0.5, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_traces(hovertemplate=f"Year: %{{x}}<br>{y_label}: %{{y:{format_str}}}<extra></extra>")
            return fig

        with tab_life:
            fig_life = create_trend_chart(country_df, "life_expectancy", "Life Expectancy Over Time", "Life Expectancy (years)", '#1f77b4', '.1f')
            st.plotly_chart(fig_life, use_container_width=True)
            
        with tab_gdp:
            fig_gdp = create_trend_chart(country_df, "gdp_per_capita", "GDP per Capita Over Time", "GDP per capita (USD)", '#2ca02c', ',.0f')
            st.plotly_chart(fig_gdp, use_container_width=True)
            
        with tab_gni:
            fig_gni = create_trend_chart(country_df, "gni_per_capita", "GNI per Capita Over Time", "GNI per capita (USD)", '#d62728', ',.0f')
            st.plotly_chart(fig_gni, use_container_width=True)

        with tab_pop:
            fig_pop = create_trend_chart(country_df, "population", "Population Over Time", "Total Population", '#ff7f0e', ',.0f')
            st.plotly_chart(fig_pop, use_container_width=True)
            
        with tab_co2:
            fig_co2 = create_trend_chart(country_df, "co2_emissions_pc", "CO2 Emissions per Capita Over Time", "CO2 (tons per capita)", '#9467bd', '.2f')
            st.plotly_chart(fig_co2, use_container_width=True)
            
    else:
        st.info("Select a country from the search box or click one on the map to view its detailed metrics and trends.")


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

