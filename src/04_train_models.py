import pandas as pd
import numpy as np
import time
from pathlib import Path
from sklearn.model_selection import KFold, train_test_split
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import joblib
from tabulate import tabulate
from statsmodels.tsa.stattools import grangercausalitytests
import warnings
from utils.db_connection import get_engine

warnings.filterwarnings('ignore')

# ---------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ---------------------------------------------------------
BASE_DIR = Path("c:/Users/suraj/OneDrive/Desktop/Predictive Supply Chain Control Tower")
DATA_FILE = BASE_DIR / "data" / "processed" / "ml_ready_dataset.csv"
REPORTS_DIR = BASE_DIR / "reports"
MODELS_DIR = BASE_DIR / "models"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    'day_of_week', 'month', 'is_weekend', 'is_monsoon', 'is_festival',
    'is_festival_season', 'max_temp_c', 'min_temp_c', 'mean_temp_c',
    'precipitation_mm', 'humidity_max_pct', 'wind_speed_max_kmh',
    'weather_severity_index', 'temp_deviation_from_avg', 'rain_intensity_level',
    'sales_lag_7d'
]
TARGET = 'quantity_sold'


def mean_absolute_percentage_error(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    non_zero = y_true != 0
    if not non_zero.any():
        return 0.0
    return np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])) * 100


def load_data():
    """Loads the ML ready dataset from CSV or database if CSV is not found."""
    if DATA_FILE.exists():
        print(f"✅ Loading dataset from {DATA_FILE}")
        df = pd.read_csv(DATA_FILE)
    else:
        print("🔄 CSV not found. Loading from MS-SQL database (vw_SalesWeatherAnalysis)...")
        engine = get_engine()
        df = pd.read_sql("SELECT * FROM vw_SalesWeatherAnalysis", engine)
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
    # Fill any missing values in features just in case
    for col in FEATURES:
        if col in df.columns:
            df[col] = df[col].fillna(0)
            
    return df


def evaluate_models(df):
    """Evaluates 4 models using 5-fold Cross-Validation."""
    print("\n🔄 Starting Model Evaluation with 5-fold CV...")
    
    X = df[FEATURES]
    y = df[TARGET]
    
    models = {
        'Linear Regression': LinearRegression(),
        'Ridge Regression': Ridge(alpha=1.0),
        'Random Forest': RandomForestRegressor(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1),
        'XGBoost': XGBRegressor(n_estimators=200, max_depth=8, learning_rate=0.1, random_state=42, n_jobs=-1)
    }
    
    results = []
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    
    for name, model in models.items():
        print(f"  Training {name}...")
        metrics = {'RMSE': [], 'MAE': [], 'R2': [], 'MAPE': []}
        start_time = time.time()
        
        for train_idx, val_idx in kf.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            model.fit(X_train, y_train)
            preds = model.predict(X_val)
            
            metrics['RMSE'].append(np.sqrt(mean_squared_error(y_val, preds)))
            metrics['MAE'].append(mean_absolute_error(y_val, preds))
            metrics['R2'].append(r2_score(y_val, preds))
            metrics['MAPE'].append(mean_absolute_percentage_error(y_val, preds))
            
        train_time = time.time() - start_time
        results.append({
            'Model': name,
            'RMSE': np.mean(metrics['RMSE']),
            'MAE': np.mean(metrics['MAE']),
            'R²': np.mean(metrics['R2']),
            'MAPE (%)': np.mean(metrics['MAPE']),
            'Time (s)': train_time
        })
        
    results_df = pd.DataFrame(results)
    
    # Save to CSV
    reports_path = REPORTS_DIR / "model_comparison.csv"
    results_df.to_csv(reports_path, index=False)
    print(f"✅ Saved model comparison to {reports_path}\n")
    
    # Print formatted table
    print(tabulate(results_df, headers='keys', tablefmt='psql', showindex=False))
    
    best_model_name = results_df.loc[results_df['RMSE'].idxmin(), 'Model']
    print(f"⭐ Best Model based on RMSE: {best_model_name}")
    
    return best_model_name, models[best_model_name]


def train_best_model(df, best_model_name, best_model):
    """Trains the best model on 80/20 time-based split and extracts feature importances."""
    print(f"\n🔄 Training best model ({best_model_name}) on 80/20 time-split...")
    
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    X_train, y_train = train_df[FEATURES], train_df[TARGET]
    X_test, y_test = test_df[FEATURES], test_df[TARGET]
    
    best_model.fit(X_train, y_train)
    
    # Save model
    model_path = MODELS_DIR / "best_model.pkl"
    joblib.dump(best_model, model_path)
    print(f"✅ Saved best model to {model_path}")
    
    # Feature importances
    if hasattr(best_model, 'feature_importances_'):
        importances = best_model.feature_importances_
        feat_imp_df = pd.DataFrame({
            'Feature': FEATURES,
            'Importance': importances
        }).sort_values('Importance', ascending=False)
        
        feat_imp_path = REPORTS_DIR / "feature_importances.csv"
        feat_imp_df.to_csv(feat_imp_path, index=False)
        print(f"✅ Saved feature importances to {feat_imp_path}")
        
        print("\n📊 Top 5 Features:")
        print(tabulate(feat_imp_df.head(5), headers='keys', tablefmt='psql', showindex=False))
    else:
        print("⚠️ Model does not support feature importances natively.")


def run_granger_causality(df):
    """Performs Granger Causality tests on weather vs product categories."""
    print("\n🔄 Running Granger Causality Tests (Weather -> Sales)...")
    
    weather_vars = ['precipitation_mm', 'mean_temp_c', 'humidity_max_pct']
    categories = df['product_category'].unique() if 'product_category' in df.columns else []
    
    results = []
    maxlag = 7
    
    for category in categories:
        cat_df = df[df['product_category'] == category]
        
        # We need daily aggregate data for granger tests
        if 'date' in cat_df.columns:
            daily_df = cat_df.groupby('date').agg({
                TARGET: 'sum',
                'precipitation_mm': 'mean',
                'mean_temp_c': 'mean',
                'humidity_max_pct': 'mean'
            }).dropna()
            
            if len(daily_df) > maxlag + 10:
                for weather_var in weather_vars:
                    # test if weather_var Granger-causes target
                    data_cols = daily_df[[TARGET, weather_var]]
                    try:
                        gc_res = grangercausalitytests(data_cols, maxlag=maxlag, verbose=False)
                        
                        for lag in range(1, maxlag + 1):
                            # Get p-value of SSR F-test
                            p_val = gc_res[lag][0]['ssr_ftest'][1]
                            f_stat = gc_res[lag][0]['ssr_ftest'][0]
                            
                            results.append({
                                'product_category': category,
                                'weather_variable': weather_var,
                                'lag': lag,
                                'f_statistic': f_stat,
                                'p_value': p_val,
                                'is_significant': p_val < 0.05
                            })
                    except Exception as e:
                        pass # Ignore if test fails due to constant data or other issues

    if results:
        results_df = pd.DataFrame(results)
        gc_path = REPORTS_DIR / "granger_causality_results.csv"
        results_df.to_csv(gc_path, index=False)
        print(f"✅ Saved Granger Causality results to {gc_path}")
        
        # Summary
        sig_results = results_df[results_df['is_significant']]
        print("\n📊 Granger Causality Summary (Significant Predictors p < 0.05):")
        if not sig_results.empty:
            summary = sig_results.groupby(['product_category', 'weather_variable']).size().reset_index(name='sig_lags_count')
            print(tabulate(summary, headers='keys', tablefmt='psql', showindex=False))
        else:
            print("  No significant causal relationships found.")
    else:
        print("⚠️ Could not run Granger tests (not enough data or missing columns).")


if __name__ == "__main__":
    print("🚀 Starting Model Training Script...")
    
    df = load_data()
    
    if df.empty:
        print("❌ Dataset is empty. Exiting.")
        exit(1)
        
    best_model_name, best_model = evaluate_models(df)
    train_best_model(df, best_model_name, best_model)
    run_granger_causality(df)
    
    print("\n✅ Script execution completed successfully!")
