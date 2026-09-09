"""
03_transform_load.py

This script transforms raw data and loads it into the MS-SQL star schema.
It also prepares a merged dataset for machine learning models.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

# Add the project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.utils.db_connection import (
    load_config,
    get_engine,
    load_dataframe_to_sql,
    truncate_table,
    execute_query
)

def create_date_key(date_series):
    """Creates a date_key in YYYYMMDD integer format."""
    return pd.to_datetime(date_series).dt.strftime('%Y%m%d').astype(int)

def load_dimension_mapping(engine, table_name, id_col, key_col):
    """Loads a dimension table mapping from ID to Key."""
    query = f"SELECT {id_col}, {key_col} FROM {table_name}"
    df = pd.read_sql(query, engine)
    return dict(zip(df[id_col], df[key_col]))

def load_raw_data(project_root):
    """Loads raw CSV data files."""
    print("🔄 Loading raw data files...")
    data_dir = project_root / 'data'
    
    sales_path = data_dir / 'raw' / 'sales_data.csv'
    hist_weather_path = data_dir / 'weather' / 'historical_weather.csv'
    fcst_weather_path = data_dir / 'weather' / 'forecast_weather.csv'
    
    sales_df = pd.read_csv(sales_path) if sales_path.exists() else pd.DataFrame()
    hist_weather_df = pd.read_csv(hist_weather_path) if hist_weather_path.exists() else pd.DataFrame()
    fcst_weather_df = pd.read_csv(fcst_weather_path) if fcst_weather_path.exists() else pd.DataFrame()
    
    # Combine weather data if both exist
    weather_df = pd.concat([hist_weather_df, fcst_weather_df], ignore_index=True)
    if not weather_df.empty:
        # Drop duplicates just in case there's overlap
        weather_df = weather_df.drop_duplicates(subset=['date', 'store_id'], keep='last')
        
    print(f"✅ Loaded {len(sales_df)} sales records and {len(weather_df)} weather records.")
    return sales_df, weather_df

def transform_sales_data(sales_df, store_mapping, product_mapping):
    """Transforms sales data according to business rules."""
    print("🔄 Transforming sales data...")
    if sales_df.empty:
        return pd.DataFrame()
        
    df = sales_df.copy()
    
    # Mappings
    df['store_key'] = df['store_id'].map(store_mapping)
    df['product_key'] = df['product_id'].map(product_mapping)
    df['date_key'] = create_date_key(df['date'])
    
    # Calculations
    df['total_revenue'] = df['quantity_sold'] * df['unit_price']
    df['total_cost'] = df['quantity_sold'] * df['unit_cost']
    df['profit'] = df['total_revenue'] - df['total_cost']
    
    print("✅ Sales data transformed.")
    return df

def transform_weather_data(weather_df, store_mapping):
    """Transforms weather data."""
    print("🔄 Transforming weather data...")
    if weather_df.empty:
        return pd.DataFrame()
        
    df = weather_df.copy()
    
    # Mappings
    df['store_key'] = df['store_id'].map(store_mapping)
    df['date_key'] = create_date_key(df['date'])
    
    # Calculations
    df['mean_temp_c'] = (df['max_temp_c'] + df['min_temp_c']) / 2.0
    
    if 'weather_severity_index' not in df.columns:
        # Simple heuristic for severity if not provided by source
        df['weather_severity_index'] = (
            (df['precipitation_mm'] > 50).astype(int) * 3 +
            (df['max_temp_c'] > 40).astype(int) * 2 +
            (df['min_temp_c'] < 5).astype(int) * 2
        )
        
    if 'data_source' not in df.columns:
        df['data_source'] = 'open-meteo'
        
    print("✅ Weather data transformed.")
    return df

def engineer_features(sales_df, weather_df, output_path):
    """Creates a merged dataset for machine learning."""
    print("🔄 Engineering features for ML...")
    if sales_df.empty or weather_df.empty:
        print("❌ Missing sales or weather data for feature engineering.")
        return
        
    # Merge on date and store_id
    sales_df['date'] = pd.to_datetime(sales_df['date'])
    weather_df['date'] = pd.to_datetime(weather_df['date'])
    
    df = pd.merge(
        sales_df, 
        weather_df,
        on=['date', 'store_id'],
        how='left'
    )
    
    # Temporal features
    df['day_of_week'] = df['date'].dt.dayofweek
    df['month'] = df['date'].dt.month
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    
    # Indian Monsoon (June to September)
    df['is_monsoon'] = df['month'].isin([6, 7, 8, 9]).astype(int)
    
    # Simple festival mapping (can be expanded via Dim_Date later)
    # E.g., Diwali roughly Oct/Nov, Holi Mar. Here we just set 0 for baseline.
    df['is_festival'] = 0 
    
    # Temp deviation (assuming mean_temp_c is available)
    monthly_avg_temp = df.groupby(['store_id', 'month'])['mean_temp_c'].transform('mean')
    df['temp_deviation_from_avg'] = df['mean_temp_c'] - monthly_avg_temp
    
    # Rain intensity (0-4)
    # 0: None, 1: Light (<10mm), 2: Moderate (10-35mm), 3: Heavy (35-65mm), 4: Very Heavy (>65mm)
    bins = [-np.inf, 0, 10, 35, 65, np.inf]
    labels = [0, 1, 2, 3, 4]
    df['rain_intensity_level'] = pd.cut(df['precipitation_mm'].fillna(0), bins=bins, labels=labels, right=False).astype(int)
    
    # Lag features (needs sorting)
    df = df.sort_values(by=['store_id', 'product_id', 'date'])
    df['sales_lag_1d'] = df.groupby(['store_id', 'product_id'])['quantity_sold'].shift(1)
    df['sales_lag_7d'] = df.groupby(['store_id', 'product_id'])['quantity_sold'].shift(7)
    
    # Save to processed
    os.makedirs(output_path.parent, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"✅ ML ready dataset saved to: {output_path}")

def load_to_mssql(engine, weather_df, sales_df):
    """Loads transformed data into MS-SQL fact tables."""
    print("🔄 Loading data into MS-SQL...")
    
    try:
        # Load Fact_Weather
        if not weather_df.empty:
            print("Truncating Fact_Weather...")
            truncate_table(engine, 'Fact_Weather')
            
            weather_cols = [
                'date_key', 'store_key', 'max_temp_c', 'min_temp_c', 'mean_temp_c',
                'precipitation_mm', 'weather_severity_index', 'data_source'
            ]
            fact_weather = weather_df[weather_cols].copy()
            
            load_dataframe_to_sql(fact_weather, 'Fact_Weather', engine, chunksize=1000)
            print("✅ Fact_Weather loaded successfully.")
            
        # Load Fact_Sales
        if not sales_df.empty:
            print("Truncating Fact_Sales...")
            truncate_table(engine, 'Fact_Sales')
            
            sales_cols = [
                'date_key', 'store_key', 'product_key', 'quantity_sold',
                'unit_price', 'unit_cost', 'total_revenue', 'total_cost', 'profit', 'discount_applied'
            ]
            # Ensure discount_applied exists
            if 'discount_applied' not in sales_df.columns:
                sales_df['discount_applied'] = 0.0
                
            fact_sales = sales_df[sales_cols].copy()
            
            load_dataframe_to_sql(fact_sales, 'Fact_Sales', engine, chunksize=1000)
            print("✅ Fact_Sales loaded successfully.")
            
    except Exception as e:
        print(f"❌ Error during database load: {e}")

def run_validation(engine):
    """Validates the loaded data in the database."""
    print("📊 Running validation checks...")
    
    try:
        # Count checks
        weather_count = execute_query(engine, "SELECT COUNT(*) as cnt FROM Fact_Weather")
        sales_count = execute_query(engine, "SELECT COUNT(*) as cnt FROM Fact_Sales")
        
        print(f"Fact_Weather row count: {weather_count.iloc[0]['cnt'] if weather_count is not None else 0}")
        print(f"Fact_Sales row count: {sales_count.iloc[0]['cnt'] if sales_count is not None else 0}")
        
        # NULL checks
        weather_nulls = execute_query(engine, "SELECT COUNT(*) as cnt FROM Fact_Weather WHERE store_key IS NULL OR date_key IS NULL")
        sales_nulls = execute_query(engine, "SELECT COUNT(*) as cnt FROM Fact_Sales WHERE store_key IS NULL OR product_key IS NULL OR date_key IS NULL")
        
        w_nulls = weather_nulls.iloc[0]['cnt'] if weather_nulls is not None else 0
        s_nulls = sales_nulls.iloc[0]['cnt'] if sales_nulls is not None else 0
        
        if w_nulls > 0:
            print(f"❌ WARNING: Found {w_nulls} rows with NULL keys in Fact_Weather")
        else:
            print("✅ No NULL keys in Fact_Weather")
            
        if s_nulls > 0:
            print(f"❌ WARNING: Found {s_nulls} rows with NULL keys in Fact_Sales")
        else:
            print("✅ No NULL keys in Fact_Sales")
            
    except Exception as e:
        print(f"❌ Validation error: {e}")

def main():
    print("🚀 Starting Transform and Load Process")
    
    config = load_config(PROJECT_ROOT / 'config.yaml')
    engine = get_engine(config)
    
    # 1. Load Mappings from DB
    try:
        store_mapping = load_dimension_mapping(engine, 'Dim_Store', 'store_id', 'store_key')
        product_mapping = load_dimension_mapping(engine, 'Dim_Product', 'product_id', 'product_key')
    except Exception as e:
        print(f"❌ Failed to load dimension mappings: {e}")
        return
        
    # 2. Load Raw Data
    sales_raw, weather_raw = load_raw_data(PROJECT_ROOT)
    
    # 3. Transform Data
    sales_transformed = transform_sales_data(sales_raw, store_mapping, product_mapping)
    weather_transformed = transform_weather_data(weather_raw, store_mapping)
    
    # 4. Feature Engineering
    ml_output_path = PROJECT_ROOT / 'data' / 'processed' / 'ml_ready_dataset.csv'
    engineer_features(sales_transformed.copy(), weather_transformed.copy(), ml_output_path)
    
    # 5. Load to MS-SQL
    load_to_mssql(engine, weather_transformed, sales_transformed)
    
    # 6. Validation
    run_validation(engine)
    
    print("🎉 Transform and Load Process Complete!")

if __name__ == "__main__":
    main()
