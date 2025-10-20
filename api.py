import requests
import pandas as pd

def get_worldbank_data(indicator="NY.GDP.PCAP.CD", countries="all", date="2010:2023"):
    """
    Fetches World Bank indicator data and returns a clean DataFrame
    with columns: ['country', 'countryiso3code', 'date', 'indicator_value'].
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

    # Extract nested country info safely
    if "country" in df.columns:
        df["country"] = df["country"].apply(lambda x: x.get("value") if isinstance(x, dict) else x)
    else:
        df["country"] = None

    # Keep consistent columns
    keep_cols = ["country", "countryiso3code", "date", "value"]
    for col in keep_cols:
        if col not in df.columns:
            df[col] = None

    df = df[keep_cols]
    df.rename(columns={"value": "indicator_value"}, inplace=True)

    # Clean data types
    df = df.dropna(subset=["indicator_value", "country"])
    df["date"] = df["date"].astype(int)
    return df.reset_index(drop=True)