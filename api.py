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
    # Add more common mappings as needed
    name_to_iso3["Bolivia (Plurinational State of)"] = "BOL"
    name_to_iso3["Venezuela (Bolivarian Republic of)"] = "VEN"
    name_to_iso3["Iran (Islamic Republic of)"] = "IRN"
    
    return name_to_m49, name_to_iso3

NAME_TO_M49, NAME_TO_ISO3 = get_country_mapping()

# --- Re-usable Helper Function ---
# Moved from get_imf_data to be used by all data fetchers
def get_country_name_or_code(iso_code):
    """Tries to find a country name from an ISO3 code, otherwise returns the code."""
    try:
        return pycountry.countries.get(alpha_3=iso_code).name
    except AttributeError:
        # Fallback for codes not in pycountry (e.g., aggregates)
        return iso_code

# --- IMF Data API---
@st.cache_data
def get_imf_data(indicator, countries="all", date="2010:2023"):
    """
    Fetches IMF indicator data from the DataMapper API
    and returns a clean DataFrame with columns:
    ['country', 'countryiso3code', 'date', 'indicator_value'].
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
                    "countryiso3code": iso_code.upper(), # Standardize ISO code
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
    # Use the globally-scoped helper function
    df['country'] = df['countryiso3code'].apply(get_country_name_or_code)
        
    # Reorder columns to match WB output
    df = df[["country", "countryiso3code", "date", "indicator_value"]]
    return df.reset_index(drop=True)


# --- World Bank Data API ---
@st.cache_data
def get_worldbank_data(indicator="NY.GDP.PCAP.CD", countries="all", date="2010:2023"):
    """
    Fetches World Bank indicator data and returns a clean DataFrame
    with columns: ['country', 'countryiso3code', 'date', 'indicator_value'].
    (This is your original function, unchanged)
    """
    url = f"https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}?format=json&date={date}&per_page=20000"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"World Bank API request failed: {e}")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
    except requests.exceptions.JSONDecodeError:
        st.error("Failed to decode JSON response from World Bank API.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])


    if not data or len(data) < 2 or data[1] is None:
        st.warning(f"World Bank API: No data returned for indicator {indicator}.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    records = data[1]
    df = pd.DataFrame.from_records(records)
    
    # Handle case where no records are returned
    if df.empty:
        st.warning(f"World Bank API: No data found for indicator {indicator}.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    df["country"] = df["country"].apply(lambda x: x.get("value") if isinstance(x, dict) else x)
    keep_cols = ["country", "countryiso3code", "date", "value"]
    
    # Check if all required columns exist
    for col in keep_cols:
        if col not in df.columns:
            st.error(f"World Bank API: Expected column '{col}' not in response.")
            return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    df = df[keep_cols]
    df.rename(columns={"value": "indicator_value"}, inplace=True)
    df = df.dropna(subset=["indicator_value", "country"])
    
    if df.empty:
        st.warning(f"World Bank API: Data for {indicator} was found but contained no numeric values.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
        
    df["date"] = pd.to_numeric(df["date"], errors='coerce')
    df = df.dropna(subset=["date"])
    df["date"] = df["date"].astype(int)
    
    return df.reset_index(drop=True)


# --- NEW: Data Commons API ---
@st.cache_data
def get_datacommons_data(indicator, countries="all", date="2010:2023"):
    """
    Fetches Data Commons time series data for a specific variable
    and returns a clean DataFrame with columns:
    ['country', 'countryiso3code', 'date', 'indicator_value'].
    
    --- FINAL FIX ---
    1. Switched back to a POST request. The GET request fails when the
       list of countries is too long, causing a "URL Too Long" error.
    2. Using the correct JSON payload for /v2/observation.
    3. Kept the manual date filtering, as we fetch all dates ("date": "").
    """
    
    # 1. API Key is hardcoded
    api_key = "A7C8l4sxmruXAvA5gDbsacZrnOXKJS3POz314CrCf5EykNra" 

    # 2. Correct API URL
    API_URL = "https://api.datacommons.org/v2/observation"
    
    # 3. Prepare entities
    if countries == "all":
        iso_codes = list(NAME_TO_ISO3.values())
    elif isinstance(countries, list):
        iso_codes = [NAME_TO_ISO3.get(c) for c in countries if NAME_TO_ISO3.get(c)]
    else:
        st.error(f"Data Commons API: Invalid 'countries' parameter. Must be 'all' or a list of names.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    entity_dcids = [f"country/{iso}" for iso in iso_codes]
    
    if not entity_dcids:
        st.error("Data Commons API: Could not map provided countries to any valid ISO codes.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    # 4. Build the request payload and headers for a POST request
    payload = {
        "variable": { "dcids": [indicator] },
        "entity": { "dcids": entity_dcids },
        "date": "",  # Fetch all dates
        "select": ["variable", "entity", "date", "value"]
    }
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': api_key
    }

    # 5. Make the API call
    try:
        # Use POST and send the 'json' payload
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status() 
        data = response.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"Data Commons API request failed: {e}")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
    except requests.exceptions.RequestException as e:
        st.error(f"Data Commons API connection failed: {e}")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
    except requests.exceptions.JSONDecodeError:
        st.error("Failed to decode JSON response from Data Commons API.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    # 6. Process the response
    records = []
    all_data = data.get("data", {})
    
    if not all_data:
         # This warning is correct if the indicator name is wrong
         st.warning(f"Data Commons API: No data found for indicator '{indicator}'. Check the indicator name.")
         return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    for entity_dcid, var_data in all_data.items():
        try:
            iso_code = entity_dcid.split("/")[-1].upper()
            country_name = get_country_name_or_code(iso_code)
            
            # The API returns the indicator name as the key
            observations = var_data.get(indicator, [])
            for obs in observations:
                date_str = obs.get("date")
                value = obs.get("value")
                
                if date_str and value is not None and len(date_str) >= 4:
                    records.append({
                        "country": country_name,
                        "countryiso3code": iso_code,
                        "date": int(date_str.split("-")[0]), # Get year
                        "indicator_value": float(value)
                    })
        except (ValueError, TypeError, AttributeError):
            continue

    if not records:
        st.error(f"Data Commons API: No valid numeric data found for indicator {indicator}.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])

    df = pd.DataFrame(records)
    
    # --- Manual Date Filtering ---
    # We must filter the results to the user's requested date range
    if df.empty:
        st.error(f"Data Commons API: No valid data found for {indicator}.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
        
    try:
        start_year, end_year = [int(y) for y in date.split(":")]
        df = df[(df['date'] >= start_year) & (df['date'] <= end_year)]
    except (ValueError, TypeError):
        st.error(f"Data Commons API: Could not apply date filter for range '{date}'.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
    # --- End of filter section ---

    if df.empty: 
        st.warning(f"Data Commons API: No valid data found for {indicator} in the range {date}.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
    
    # Aggregate to year level
    df = df.groupby(['country', 'countryiso3code', 'date'])['indicator_value'].mean().reset_index()

    df = df[["country", "countryiso3code", "date", "indicator_value"]]
    return df.reset_index(drop=True)


# --- Master Data Fetcher (Adapter/Wrapper) ---
def get_data(indicator_code, countries="all", date="2010:2023"):
    """
    Decides which API to call based on the indicator prefix.
    - 'WB_' for World Bank
    - 'IMF_' for IMF
    - 'DC_' for Data Commons (NEW)
    
    The function signature is standardized.
    """
    if indicator_code.startswith("WB_"):
        wb_indicator = indicator_code.replace("WB_", "")
        return get_worldbank_data(indicator=wb_indicator, countries=countries, date=date)
    
    elif indicator_code.startswith("IMF_"):
        imf_indicator = indicator_code.replace("IMF_", "")
        return get_imf_data(indicator=imf_indicator, countries=countries, date=date)
    
    elif indicator_code.startswith("DC_"):
        dc_indicator = indicator_code.replace("DC_", "")
        return get_datacommons_data(indicator=dc_indicator, countries=countries, date=date)
    
    else:
        # Default or error
        st.error(f"Invalid indicator code prefix: '{indicator_code}'. Must use 'WB_', 'IMF_', or 'DC_'.")
        return pd.DataFrame(columns=["country", "countryiso3code", "date", "indicator_value"])
