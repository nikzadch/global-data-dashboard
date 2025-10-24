# api.py

import requests
import pandas as pd
import pycountry # You will need to install this: pip install pycountry
import streamlit as st

# A simple cache to avoid re-mapping country codes on every run
@st.cache_data
def get_country_mapping():
    """Creates a mapping from country name to M49 code and ISO3 code."""
    name_to_m49 = {}
    name_to_iso3 = {}
    for country in pycountry.countries:
        name_to_m49[country.name] = country.numeric
        if hasattr(country, 'alpha_3'):
            name_to_iso3[country.name] = country.alpha_3
    # Add common name variations if needed
    name_to_m49["United States"] = "840" 
    name_to_iso3["United States"] = "USA"
    name_to_m49["Russian Federation"] = "643"
    name_to_iso3["Russian Federation"] = "RUS"
    return name_to_m49, name_to_iso3

NAME_TO_M49, NAME_TO_ISO3 = get_country_mapping()

def get_un_data(indicator, country_name="All", year=2021):
    """
    Fetches UN indicator data and returns a clean DataFrame with the standard columns.
    UN Indicator format: {database_id}/{indicator_id} e.g., "1/6"
    """
    if country_name == "All" or country_name == "all":
        # UN API is slow with 'all', so it's better to query without an areaCode filter
        url = f"http://data.un.org/ws/rest/data/{indicator}/?timePeriod={year}&format=json"
    else:
        # Map country name to UN's M49 numeric code
        area_code = NAME_TO_M49.get(country_name)
        if not area_code:
            # Return empty if country not found in mapping
            return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
        url = f"http://data.un.org/ws/rest/data/{indicator}/?areaCode={area_code}&timePeriod={year}&format=json"

    response = requests.get(url)

    if response.status_code != 200:
        # Silently fail for now, but you could raise an exception
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
    
    data = response.json()
    records = data.get("data", {}).get("records", [])
    if not records:
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    df = pd.DataFrame(records)
    
    # Standardize the DataFrame to match the World Bank output
    df.rename(columns={
        "areaName": "country",
        "timePeriod": "date",
        "value": "indicator_value"
    }, inplace=True)
    
    # Map country name to ISO3 code for consistency
    df['countryiso3code'] = df['country'].map(NAME_TO_ISO3)

    # Ensure required columns exist and have correct types
    df = df[["country", "countryiso3code", "date", "indicator_value"]]
    df['date'] = pd.to_numeric(df['date'], errors='coerce')
    df['indicator_value'] = pd.to_numeric(df['indicator_value'], errors='coerce')
    df.dropna(inplace=True)

    return df.reset_index(drop=True)


def get_worldbank_data(indicator="NY.GDP.PCAP.CD", countries="all", date="2010:2023"):
    """
    Fetches World Bank indicator data and returns a clean DataFrame
    with columns: ['country', 'countryiso3code', 'date', 'indicator_value'].
    (This is your original function, unchanged)
    """
    url = f"https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}?format=json&date={date}&per_page=20000"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception(f"API call failed: {response.status_code}")

    data = response.json()
    if not data or len(data) < 2:
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    records = data[1]
    df = pd.DataFrame.from_records(records)
    df["country"] = df["country"].apply(lambda x: x.get("value") if isinstance(x, dict) else x)
    keep_cols = ["country", "countryiso3code", "date", "value"]
    for col in keep_cols:
        if col not in df.columns:
            df[col] = None

    df = df[keep_cols]
    df.rename(columns={"value": "indicator_value"}, inplace=True)
    df = df.dropna(subset=["indicator_value", "country"])
    df["date"] = df["date"].astype(int)
    return df.reset_index(drop=True)


# --- The Master Data Fetcher (Adapter/Wrapper) ---
def get_data(indicator_code, country_name="All", year=2021, countries_iso="all", date_range="2010:2023"):
    """
    Decides which API to call based on the indicator prefix.
    - 'WB_' for World Bank
    - 'UN_' for UN Data
    """
    if indicator_code.startswith("WB_"):
        # Strip prefix and call World Bank API
        wb_indicator = indicator_code.replace("WB_", "")
        return get_worldbank_data(indicator=wb_indicator, countries=countries_iso, date=date_range)
    
    elif indicator_code.startswith("UN_"):
        # Strip prefix, format indicator, and call UN API
        # UN indicators are often {db_id}/{indicator_id}
        un_indicator = indicator_code.replace("UN_", "").replace("-", "/")
        return get_un_data(indicator=un_indicator, country_name=country_name, year=year)
    
    else:
        # Default or error
        raise ValueError("Invalid indicator code prefix. Use 'WB_' or 'UN_'.")
    