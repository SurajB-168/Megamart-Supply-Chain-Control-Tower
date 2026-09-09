import os
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

try:
    from utils.db_connection import get_engine, load_dataframe_to_sql, truncate_table, execute_query
except ImportError:
    print("⚠️ Could not import utils.db_connection. Please ensure it exists.")
    get_engine, load_dataframe_to_sql, truncate_table, execute_query = None, None, None, None

# Formatting function for Indian Rupee
def format_inr(number):
    try:
        s, *d = str(int(number)).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return f"₹{r}"
    except:
        return f"₹{number}"

# Product info dictionary
PRODUCT_INFO = {
    'PRD001': {'name': 'Umbrella', 'price': 499, 'margin': 0.6012, 'lead': 3},
    'PRD002': {'name': 'Raincoat', 'price': 899, 'margin': 0.5562, 'lead': 5},
    'PRD003': {'name': 'Waterproof Bag', 'price': 1299, 'margin': 0.5004, 'lead': 7},
    'PRD004': {'name': 'Gumboots', 'price': 749, 'margin': 0.5340, 'lead': 5},
    'PRD005': {'name': 'AC', 'price': 34999, 'margin': 0.2857, 'lead': 14},
    'PRD006': {'name': 'Cooler', 'price': 7999, 'margin': 0.3750, 'lead': 7},
    'PRD007': {'name': 'Fan', 'price': 1999, 'margin': 0.5003, 'lead': 5},
    'PRD008': {'name': 'Cold Drinks', 'price': 599, 'margin': 0.4007, 'lead': 2},
    'PRD009': {'name': 'Ice Cream', 'price': 349, 'margin': 0.4298, 'lead': 1},
    'PRD010': {'name': 'Sunscreen', 'price': 599, 'margin': 0.5008, 'lead': 5},
    'PRD011': {'name': 'Sunglasses', 'price': 1499, 'margin': 0.6004, 'lead': 7},
    'PRD012': {'name': 'Room Heater', 'price': 3499, 'margin': 0.4287, 'lead': 7},
    'PRD013': {'name': 'Blanket', 'price': 1999, 'margin': 0.5003, 'lead': 5},
    'PRD014': {'name': 'Hot Beverages', 'price': 449, 'margin': 0.4454, 'lead': 2},
    'PRD015': {'name': 'Jacket', 'price': 2999, 'margin': 0.5002, 'lead': 10},
    'PRD016': {'name': 'Thermal Wear', 'price': 999, 'margin': 0.5005, 'lead': 7},
    'PRD017': {'name': 'Rice', 'price': 599, 'margin': 0.2504, 'lead': 3},
    'PRD018': {'name': 'Cooking Oil', 'price': 749, 'margin': 0.2003, 'lead': 3},
    'PRD019': {'name': 'Toothpaste', 'price': 199, 'margin': 0.4020, 'lead': 3},
    'PRD020': {'name': 'Detergent', 'price': 349, 'margin': 0.3725, 'lead': 3},
}

def load_data(project_dir):
    print("🔄 Loading data...")
    data_dir = project_dir / "data"
    
    # Load best model
    model_path = project_dir / "models" / "best_model.pkl"
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found at {model_path}")
    model = joblib.load(model_path)
    print("✅ Model loaded successfully.")
    
    # Load weather forecast
    forecast_path = data_dir / "weather" / "forecast_weather.csv"
    if forecast_path.exists():
        forecast_df = pd.read_csv(forecast_path)
        forecast_df['date'] = pd.to_datetime(forecast_df['date'])
    else:
        # Dummy generation if not present
        print("⚠️ Forecast weather not found, using dummy data.")
        dates = pd.date_range(start=datetime.now().date(), periods=7)
        stores = [f"STR{i:03d}" for i in range(1, 11)]
        records = []
        for d in dates:
            for s in stores:
                records.append({
                    'date': d, 'store_id': s, 'max_temp_c': 35, 'min_temp_c': 25, 'mean_temp_c': 30,
                    'precipitation_mm': 5, 'humidity_max_pct': 70, 'wind_speed_max_kmh': 15,
                    'weather_severity_index': 2, 'temp_deviation_from_avg': 1, 'rain_intensity_level': 1
                })
        forecast_df = pd.DataFrame(records)
    
    # Load inventory
    inventory_path = data_dir / "raw" / "current_inventory.csv"
    if inventory_path.exists():
        inventory_df = pd.read_csv(inventory_path)
    else:
        print("⚠️ Inventory not found, generating random inventory.")
        products = list(PRODUCT_INFO.keys())
        stores = [f"STR{i:03d}" for i in range(1, 11)]
        inv_records = [{'store_id': s, 'product_id': p, 'stock_quantity': np.random.randint(10, 200)} 
                       for s in stores for p in products]
        inventory_df = pd.DataFrame(inv_records)

    # Load ML dataset for lag calculation
    ml_path = data_dir / "processed" / "ml_ready_dataset.csv"
    if ml_path.exists():
        ml_df = pd.read_csv(ml_path)
        # Average last 7 days per store-product
        lag_df = ml_df.groupby(['store_id', 'product_id'])['sales_quantity'].mean().reset_index()
        lag_df.rename(columns={'sales_quantity': 'sales_lag_7d'}, inplace=True)
    else:
        lag_df = pd.DataFrame([{'store_id': s, 'product_id': p, 'sales_lag_7d': np.random.randint(5, 50)} 
                               for s in inventory_df['store_id'].unique() for p in inventory_df['product_id'].unique()])

    return model, forecast_df, inventory_df, lag_df

def prepare_features(forecast_df, lag_df, products):
    print("🔄 Preparing features for predictions...")
    records = []
    
    # Create combinations
    for _, forecast in forecast_df.iterrows():
        for product_id in products:
            date_val = pd.to_datetime(forecast['date'])
            record = forecast.to_dict()
            record['product_id'] = product_id
            
            # Time features
            record['day_of_week'] = date_val.dayofweek
            record['month'] = date_val.month
            record['is_weekend'] = 1 if date_val.dayofweek >= 5 else 0
            record['is_monsoon'] = 1 if date_val.month in [6, 7, 8, 9] else 0
            
            # Simple festival logic (hardcoded for India e.g., Diwali in Nov, Holi in March)
            record['is_festival'] = 1 if (date_val.month == 11 and date_val.day == 12) or (date_val.month == 3 and date_val.day == 25) else 0
            record['is_festival_season'] = 1 if date_val.month in [10, 11, 12] else 0
            
            records.append(record)
            
    df = pd.DataFrame(records)
    
    # Merge lag
    df = df.merge(lag_df, on=['store_id', 'product_id'], how='left')
    df['sales_lag_7d'] = df['sales_lag_7d'].fillna(0)
    
    feature_cols = [
        'day_of_week', 'month', 'is_weekend', 'is_monsoon', 'is_festival', 'is_festival_season',
        'max_temp_c', 'min_temp_c', 'mean_temp_c', 'precipitation_mm', 'humidity_max_pct', 
        'wind_speed_max_kmh', 'weather_severity_index', 'temp_deviation_from_avg', 
        'rain_intensity_level', 'sales_lag_7d'
    ]
    
    # Keep other columns for metadata
    meta_cols = ['date', 'store_id', 'product_id']
    
    # Add dummy columns for any missing ones required by the model
    # (assuming model needs these exact features)
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0
            
    return df, feature_cols, meta_cols

def predict_with_uncertainty(model, X):
    print("📊 Generating predictions with uncertainty bands...")
    # Get predictions from individual trees
    if hasattr(model, 'estimators_'):
        tree_preds = []
        for tree in model.estimators_:
            tree_preds.append(tree.predict(X))
        tree_preds = np.array(tree_preds)  # Shape: (n_estimators, n_samples)
        
        # Calculate statistics
        mean_pred = np.mean(tree_preds, axis=0)
        lower_80 = np.percentile(tree_preds, 10, axis=0)
        upper_80 = np.percentile(tree_preds, 90, axis=0)
        lower_95 = np.percentile(tree_preds, 2.5, axis=0)
        upper_95 = np.percentile(tree_preds, 97.5, axis=0)
    else:
        # Fallback if not random forest
        mean_pred = model.predict(X)
        lower_80 = mean_pred * 0.8
        upper_80 = mean_pred * 1.2
        lower_95 = mean_pred * 0.6
        upper_95 = mean_pred * 1.4
        
    # Ensure no negative predictions
    return {
        'prediction': np.maximum(0, mean_pred),
        'lower_80': np.maximum(0, lower_80),
        'upper_80': np.maximum(0, upper_80),
        'lower_95': np.maximum(0, lower_95),
        'upper_95': np.maximum(0, upper_95)
    }

def analyze_risk_and_inaction(predictions_df, inventory_df):
    print("💰 Calculating Cost of Inaction & Stockout Risk...")
    
    # Aggregate 7-day predictions
    agg_df = predictions_df.groupby(['store_id', 'product_id']).agg({
        'prediction': 'sum',
        'upper_95': 'sum'
    }).reset_index()
    agg_df.rename(columns={'prediction': 'predicted_demand_7day', 'upper_95': 'predicted_demand_upper_95_7day'}, inplace=True)
    
    # Daily averages for calculations
    daily_avg_df = predictions_df.groupby(['store_id', 'product_id'])['prediction'].mean().reset_index()
    daily_avg_df.rename(columns={'prediction': 'avg_daily_demand'}, inplace=True)
    
    # Merge all
    risk_df = agg_df.merge(inventory_df[['store_id', 'product_id', 'stock_quantity']], on=['store_id', 'product_id'], how='left')
    risk_df['stock_quantity'] = risk_df['stock_quantity'].fillna(0)
    risk_df = risk_df.merge(daily_avg_df, on=['store_id', 'product_id'], how='left')
    
    results = []
    total_cost_inaction = 0
    
    for _, row in risk_df.iterrows():
        pid = row['product_id']
        p_info = PRODUCT_INFO.get(pid, {'price': 100, 'margin': 0.1, 'lead': 5})
        
        predicted_demand_7day = row['predicted_demand_7day']
        current_inventory = row['stock_quantity']
        avg_daily_sales = row['avg_daily_demand']
        
        # Cost of Inaction
        available_stock_after_lead = current_inventory - (p_info['lead'] * avg_daily_sales)
        if predicted_demand_7day > available_stock_after_lead:
            units_at_risk = predicted_demand_7day - available_stock_after_lead
            cost_of_inaction = units_at_risk * p_info['price'] * p_info['margin']
        else:
            units_at_risk = 0
            cost_of_inaction = 0
            
        total_cost_inaction += max(0, cost_of_inaction)
        
        # Risk Score
        base_risk = max(0, min(1, predicted_demand_7day / max(current_inventory, 1)))
        risk_score = min(1.0, base_risk * (1 + p_info['lead'] / 14))
        
        if risk_score < 0.30:
            risk_level = 'LOW'
        elif risk_score < 0.60:
            risk_level = 'MEDIUM'
        elif risk_score < 0.85:
            risk_level = 'HIGH'
        else:
            risk_level = 'CRITICAL'
            
        # Reorder Quantity
        safety_stock = avg_daily_sales * p_info['lead'] * 1.5
        reorder_qty = max(0, row['predicted_demand_upper_95_7day'] - current_inventory + safety_stock)
        
        results.append({
            'store_id': row['store_id'],
            'product_id': pid,
            'predicted_demand_7day': predicted_demand_7day,
            'current_inventory': current_inventory,
            'units_at_risk': max(0, units_at_risk),
            'cost_of_inaction': max(0, cost_of_inaction),
            'risk_score': risk_score,
            'risk_level': risk_level,
            'recommended_reorder_qty': reorder_qty
        })
        
    return pd.DataFrame(results), total_cost_inaction

def main():
    project_dir = Path(r"c:\Users\suraj\OneDrive\Desktop\Predictive Supply Chain Control Tower")
    processed_dir = project_dir / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    print("🚀 Starting Predict & Risk Analysis...")
    
    # 1. Load Data
    model, forecast_df, inventory_df, lag_df = load_data(project_dir)
    products = list(PRODUCT_INFO.keys())
    
    # 2. Prepare features
    features_df, feature_cols, meta_cols = prepare_features(forecast_df, lag_df, products)
    
    # 3. Predict with Uncertainty (Feature 1)
    X = features_df[feature_cols].values
    preds = predict_with_uncertainty(model, X)
    
    predictions_df = features_df[meta_cols].copy()
    for k, v in preds.items():
        predictions_df[k] = v
        
    # Save predictions
    preds_path = processed_dir / "predictions.csv"
    predictions_df.to_csv(preds_path, index=False)
    print(f"✅ Saved predictions to {preds_path}")
    
    # 4. Risk & Cost of Inaction (Feature 2)
    risk_df, total_coi = analyze_risk_and_inaction(predictions_df, inventory_df)
    
    # Save risk
    risk_path = processed_dir / "stockout_risk.csv"
    risk_df.to_csv(risk_path, index=False)
    print(f"✅ Saved risk assessments to {risk_path}")
    
    # 5. Database upload (if available)
    if load_dataframe_to_sql:
        print("🔄 Uploading to MS-SQL Database...")
        try:
            truncate_table("Fact_Predictions")
            load_dataframe_to_sql(predictions_df, "Fact_Predictions")
            
            truncate_table("Fact_Stockout_Risk")
            load_dataframe_to_sql(risk_df, "Fact_Stockout_Risk")
            print("✅ Successfully uploaded to MS-SQL.")
        except Exception as e:
            print(f"❌ Failed to upload to DB: {e}")
    
    # 6. Outputs
    print("\n" + "="*50)
    print("📈 TOP 10 HIGHEST-RISK COMBINATIONS 📈")
    print("="*50)
    top_10 = risk_df.sort_values(by='risk_score', ascending=False).head(10)
    print(top_10[['store_id', 'product_id', 'risk_level', 'cost_of_inaction', 'recommended_reorder_qty']].to_string(index=False))
    
    print("\n" + "="*50)
    print(f"💰 TOTAL COST OF INACTION (System-wide): {format_inr(total_coi)}")
    print("="*50 + "\n")
    print("✅ Analysis Complete.")

if __name__ == "__main__":
    main()
