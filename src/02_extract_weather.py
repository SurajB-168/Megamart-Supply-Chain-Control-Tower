import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------

# Project root setup
PROJECT_ROOT = Path(r"c:\Users\suraj\OneDrive\Desktop\Predictive Supply Chain Control Tower")
DATA_DIR = PROJECT_ROOT / "data" / "weather"

# Create directories if they don't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)

STORES = [
    {"store_id": "STR001", "city": "Mumbai", "lat": 19.08, "lon": 72.88},
    {"store_id": "STR002", "city": "New Delhi", "lat": 28.61, "lon": 77.21},
    {"store_id": "STR003", "city": "Bengaluru", "lat": 12.97, "lon": 77.59},
    {"store_id": "STR004", "city": "Chennai", "lat": 13.08, "lon": 80.27},
    {"store_id": "STR005", "city": "Hyderabad", "lat": 17.39, "lon": 78.49},
    {"store_id": "STR006", "city": "Kolkata", "lat": 22.57, "lon": 88.36},
    {"store_id": "STR007", "city": "Pune", "lat": 18.52, "lon": 73.86},
    {"store_id": "STR008", "city": "Ahmedabad", "lat": 23.02, "lon": 72.57},
    {"store_id": "STR009", "city": "Jaipur", "lat": 26.92, "lon": 75.79},
    {"store_id": "STR010", "city": "Lucknow", "lat": 26.85, "lon": 80.95},
]

HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_PARAMS = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,relative_humidity_2m_max,relative_humidity_2m_min"
TIMEZONE = "Asia/Kolkata"

START_DATE = "2024-01-01"
END_DATE = "2025-12-31" 

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def calculate_severity(row):
    """
    Calculate the Weather Severity Index (0-100).
    Weights: Precipitation 40%, Temp Deviation 30%, Wind 15%, Humidity 15%
    """
    try:
        precip = float(row.get('precipitation_mm', 0) or 0)
        temp_max = float(row.get('max_temp_c', 30) or 30)
        wind = float(row.get('wind_speed_max_kmh', 0) or 0)
        hum_max = float(row.get('humidity_max_pct', 50) or 50)
        
        severity = (
            (precip / 50.0) * 40 +
            (abs(temp_max - 30) / 20.0) * 30 +
            (wind / 100.0) * 15 +
            (hum_max / 100.0) * 15
        )
        return min(max(severity, 0), 100)
    except:
        return 0

def fetch_weather_data(url, params, max_retries=3):
    """Fetch data from Open-Meteo with retry logic and exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"  ❌ API Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"  ❌ Request exception: {e}")
        
        if attempt < max_retries - 1:
            sleep_time = 2 ** attempt
            print(f"  🔄 Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
            
    return None

def generate_synthetic_data(store, start_date, end_date):
    """Generate realistic synthetic weather data if API fails."""
    print(f"  ⚠️ Generating SYNTHETIC data for {store['city']}")
    dates = pd.date_range(start=start_date, end=end_date)
    
    np.random.seed(42 + int(store['lat']))
    n = len(dates)
    
    base_temp = 30
    temp_variation = np.sin(np.linspace(0, 2 * np.pi * (n/365.25), n)) * 8
    max_temps = base_temp + temp_variation + np.random.normal(0, 2, n)
    min_temps = max_temps - np.random.uniform(5, 12, n)
    
    precip = np.random.exponential(2, n)
    precip[np.random.random(n) > 0.2] = 0  # ~80% dry days
    
    wind = np.random.gamma(2, 5, n)
    hum_max = np.clip(np.random.normal(80, 10, n), 0, 100)
    hum_min = np.clip(hum_max - np.random.uniform(10, 30, n), 0, 100)
    
    weather_codes = np.where(precip > 10, 63, np.where(precip > 0, 51, np.where(hum_max > 90, 3, 0)))
    
    df = pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'store_id': store['store_id'],
        'city': store['city'],
        'weather_code': weather_codes,
        'max_temp_c': max_temps,
        'min_temp_c': min_temps,
        'precipitation_mm': precip,
        'wind_speed_max_kmh': wind,
        'humidity_max_pct': hum_max,
        'humidity_min_pct': hum_min
    })
    
    df['weather_severity_index'] = df.apply(calculate_severity, axis=1)
    df['is_extreme_weather'] = df['weather_severity_index'] > 70
    return df

def parse_openmeteo_response(data, store):
    """Parse JSON response from Open-Meteo to a structured DataFrame."""
    daily = data.get('daily', {})
    if not daily:
        return pd.DataFrame()
        
    df = pd.DataFrame({
        'date': daily.get('time', []),
        'store_id': store['store_id'],
        'city': store['city'],
        'weather_code': daily.get('weather_code', []),
        'max_temp_c': daily.get('temperature_2m_max', []),
        'min_temp_c': daily.get('temperature_2m_min', []),
        'precipitation_mm': daily.get('precipitation_sum', []),
        'wind_speed_max_kmh': daily.get('wind_speed_10m_max', []),
        'humidity_max_pct': daily.get('relative_humidity_2m_max', []),
        'humidity_min_pct': daily.get('relative_humidity_2m_min', [])
    })
    
    df['weather_severity_index'] = df.apply(calculate_severity, axis=1)
    df['is_extreme_weather'] = df['weather_severity_index'] > 70
    return df

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

def main():
    print("🌤️ Starting Weather Data Extraction for MegaMart")
    
    historical_dfs = []
    forecast_dfs = []
    
    for store in STORES:
        print(f"\n📍 Processing {store['city']} ({store['store_id']})...")
        
        # 1. Historical Data
        hist_params = {
            "latitude": store['lat'],
            "longitude": store['lon'],
            "start_date": START_DATE,
            "end_date": END_DATE,
            "daily": DAILY_PARAMS,
            "timezone": TIMEZONE
        }
        
        print("  📊 Fetching historical data...")
        hist_data = fetch_weather_data(HISTORICAL_URL, hist_params)
        if hist_data:
            hist_df = parse_openmeteo_response(hist_data, store)
            historical_dfs.append(hist_df)
            print(f"  ✅ Historical data extracted: {len(hist_df)} rows")
        else:
            synth = generate_synthetic_data(store, START_DATE, END_DATE)
            historical_dfs.append(synth)
            
        time.sleep(1) # Rate limit delay
        
        # 2. Forecast Data
        forecast_params = {
            "latitude": store['lat'],
            "longitude": store['lon'],
            "daily": DAILY_PARAMS,
            "timezone": TIMEZONE,
            "forecast_days": 7
        }
        
        print("  📈 Fetching forecast data...")
        forecast_data = fetch_weather_data(FORECAST_URL, forecast_params)
        if forecast_data:
            forecast_df = parse_openmeteo_response(forecast_data, store)
            forecast_dfs.append(forecast_df)
            print(f"  ✅ Forecast data extracted: {len(forecast_df)} rows")
        else:
            start_f = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            end_f = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            synth = generate_synthetic_data(store, start_f, end_f)
            forecast_dfs.append(synth)
            
        time.sleep(1) # Rate limit delay
        
    print("\n💾 Saving results to CSV...")
    
    # Save Historical
    if historical_dfs:
        final_hist = pd.concat(historical_dfs, ignore_index=True)
        hist_path = DATA_DIR / "historical_weather.csv"
        final_hist.to_csv(hist_path, index=False)
        print(f"  ✅ Saved {len(final_hist)} historical records to {hist_path}")
        print(f"  📅 Date Range: {final_hist['date'].min()} to {final_hist['date'].max()}")
        
        missing_hist = final_hist.isnull().sum().sum()
        if missing_hist > 0:
            print(f"  ⚠️ Warning: {missing_hist} missing values in historical data.")
    
    # Save Forecast
    if forecast_dfs:
        final_forecast = pd.concat(forecast_dfs, ignore_index=True)
        forecast_path = DATA_DIR / "forecast_weather.csv"
        final_forecast.to_csv(forecast_path, index=False)
        print(f"  ✅ Saved {len(final_forecast)} forecast records to {forecast_path}")
        print(f"  📅 Date Range: {final_forecast['date'].min()} to {final_forecast['date'].max()}")
        
        missing_forecast = final_forecast.isnull().sum().sum()
        if missing_forecast > 0:
            print(f"  ⚠️ Warning: {missing_forecast} missing values in forecast data.")

    print("\n🎉 Weather Data Extraction Complete!")

if __name__ == "__main__":
    main()
