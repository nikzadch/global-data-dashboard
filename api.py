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

# --- IMF Data API---
@st.cache_data
def get_imf_data(indicator, countries="all", date="2010:2023"):
    """
    Fetches IMF indicator data from the DataMapper API
    and returns a clean DataFrame with columns:
    ['country', 'countryiso3code', 'date', 'indicator_value'].
    
    --- THIS IS THE FIX ---
    The JSON from the IMF is nested { "values": { "INDICATOR_CODE": { ...data... }}}.
    My previous code forgot to check for "INDICATOR_CODE".
    This version correctly accesses the nested data blob.
    """
    base_url = f"https://www.imf.org/external/datamapper/api/v1/{indicator}"
    
    try:
        response = requests.get(base_url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"IMF API request failed: {e}")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
    except requests.exceptions.JSONDecodeError:
        st.error("Failed to decode JSON response from IMF API.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    # Unpivot the nested JSON
    records = []
    
    # The actual data is one level deeper, under the indicator code itself.
    data_blob = data.get("values", {}).get(indicator, {})
    
    if not data_blob:
        st.error(f"IMF API: Data found, but 'values' or '{indicator}' key was missing in JSON response.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    for iso_code, year_data in data_blob.items():
        if not isinstance(year_data, dict):
            continue
            
        for year_str, value_obj in year_data.items():
            
            # --- Robustly parse the data ---
            try:
                if value_obj is None:
                    continue
                    
                year = int(year_str)
                
                if isinstance(value_obj, (int, float)):
                    value = float(value_obj)
                else:
                    value_str = str(value_obj).strip().replace(",", "")
                    if value_str == "--" or value_str == "NA" or value_str == "n/a" or value_str == "":
                        continue
                    value = float(value_str) 
                
                records.append({
                    "countryiso3code": iso_code,
                    "date": year,
                    "indicator_value": value
                })
            except (ValueError, TypeError):
                continue

    if not records:
        st.error(f"IMF API: No valid numeric data found for indicator {indicator}. All data points were null or non-numeric.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    df = pd.DataFrame(records)

    # --- Data Cleaning ---
    def get_country_name_or_code(iso_code):
        try:
            return pycountry.countries.get(alpha_3=iso_code).name
        except AttributeError:
            return iso_code 

    df['country'] = df['countryiso3code'].apply(get_country_name_or_code)
        
    # Reorder columns to match WB output
    df = df[["country", "countryiso3code", "date", "indicator_value"]]
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


# --- Master Data Fetcher (Adapter/Wrapper) ---
def get_data(indicator_code, countries="all", date="2010:2023"):
    """
    Decides which API to call based on the indicator prefix.
    - 'WB_' for World Bank
    - 'IMF_' for IMF
    
    The function signature is now standardized.
    """
    if indicator_code.startswith("WB_"):
        wb_indicator = indicator_code.replace("WB_", "")
        return get_worldbank_data(indicator=wb_indicator, countries=countries, date=date)
    
    elif indicator_code.startswith("IMF_"):
        imf_indicator = indicator_code.replace("IMF_", "")
        return get_imf_data(indicator=imf_indicator, countries=countries, date=date)
    
    else:
        # Default or error
        raise ValueError("Invalid indicator code prefix. Use 'WB_' or 'IMF_'.")
    