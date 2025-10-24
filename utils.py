import pandas as pd
from api import get_data
import streamlit as st

@st.cache_data
def fetch_and_merge_data():
    """
    Fetches and merges data for the new, more reliable set of indicators
    FOR ALL AVAILABLE YEARS.
    """
    indicator_codes = {
        'gini': 'WB_SI.POV.GINI',
        'gender_ratio_labor': 'WB_SL.TLF.CACT.FM.ZS',
        'governance': 'WB_RL.EST',
        'school_enrollment': 'WB_SE.SEC.ENRR',
        'life_expectancy': 'WB_SP.DYN.LE00.IN',
        'access_to_electricity': 'WB_EG.ELC.ACCS.ZS'
    }
    
    dataframes_to_merge = []

    for name, code in indicator_codes.items():
        # --- CHANGE ---
        # Removed year/date_range filters to get all time-series data
        df = get_data(indicator_code=code) 
        
        if not df.empty:
            # Keep 'date' for time-series analysis
            df = df[['country', 'countryiso3code', 'date', 'indicator_value']].drop_duplicates(
                subset=['countryiso3code', 'date']
            )
            df.rename(columns={'indicator_value': name}, inplace=True)
            dataframes_to_merge.append(df)

    if not dataframes_to_merge:
        return pd.DataFrame()

    merged_df = dataframes_to_merge[0]
    for df_to_merge in dataframes_to_merge[1:]:
        # Merge on all common columns, including 'date'
        merged_df = pd.merge(merged_df, df_to_merge, 
                             on=['country', 'countryiso3code', 'date'], 
                             how='outer')
        
    return merged_df.sort_values(by=['country', 'date'])

def normalize(series):
    """Helper function for normalization"""
    if series.max() == series.min(): 
        return 0.5 
    return (series - series.min()) / (series.max() - series.min())

def process_year_data(df_year):
    """
    Applies transformations and normalization to a single year's DataFrame.
    This ensures normalization is done *within* the year, not globally.
    """
    # 1. Transform Indicators
    df_year['gini_score'] = 100 - df_year['gini']
    
    # 2. Normalize components
    df_year['norm_gini'] = normalize(df_year['gini_score'])
    df_year['norm_gender_labor'] = normalize(df_year['gender_ratio_labor'])
    df_year['norm_governance'] = normalize(df_year['governance'])
    df_year['norm_school'] = normalize(df_year['school_enrollment'])
    df_year['norm_life_expectancy'] = normalize(df_year['life_expectancy'])
    df_year['norm_electricity'] = normalize(df_year['access_to_electricity'])
    
    return df_year

def calculate_fairness_score(df):
    """
    Calculates the score for the "Development & Equality Index"
    by processing the full time-series DataFrame year by year.
    """
    required_cols = [
        'gini', 'gender_ratio_labor', 'governance', 'school_enrollment', 
        'life_expectancy', 'access_to_electricity'
    ]
    
    # We can't check for missing columns here, as they might just be missing
    # from the *merge*, not from the API.
    
    df.dropna(subset=required_cols, inplace=True)
    if df.empty:
        st.warning("No countries had a complete set of all 6 indicators for *any* year.")
        return pd.DataFrame(), pd.DataFrame()

    # --- CHANGE ---
    # Apply calculations by grouping by 'date'
    # This correctly normalizes each year against its peers.
    try:
        score_df = df.groupby('date').apply(process_year_data).reset_index(drop=True)
    except Exception as e:
        st.error(f"An error occurred during score calculation: {e}")
        return pd.DataFrame(), pd.DataFrame()


    # 3. Calculate Final Score
    score_components = [
        'norm_gini', 'norm_gender_labor', 'norm_governance', 
        'norm_school', 'norm_life_expectancy', 'norm_electricity'
    ]
    
    # Check if component columns were created
    if not all(col in score_df.columns for col in score_components):
         st.warning("Score calculation failed to produce normalized components. Data may be sparse.")
         return pd.DataFrame(), pd.DataFrame()
         
    score_df['fairness_score'] = score_df[score_components].sum(axis=1)
    
    component_cols = ['country', 'countryiso3code', 'date'] + score_components
    components_df = score_df[component_cols]

    return score_df, components_df
