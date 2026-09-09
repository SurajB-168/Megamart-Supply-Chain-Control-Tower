import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_data():
    print("🔄 Initializing data generation parameters...")
    np.random.seed(42)
    
    # Configuration
    START_DATE = '2024-01-01'
    END_DATE = '2025-12-31'
    
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.abspath(os.path.join(script_dir, '..', 'data', 'raw'))
    os.makedirs(output_dir, exist_ok=True)
    
    # Store Definitions
    stores = {
        'STR001': 'Mumbai', 'STR002': 'New Delhi', 'STR003': 'Bengaluru',
        'STR004': 'Chennai', 'STR005': 'Hyderabad', 'STR006': 'Kolkata',
        'STR007': 'Pune', 'STR008': 'Ahmedabad', 'STR009': 'Jaipur',
        'STR010': 'Lucknow'
    }
    
    # Regional Weather Multipliers (Summer, Monsoon, Winter)
    # 1.0 means baseline, >1.0 means stronger seasonal effect
    city_multipliers = {
        'Mumbai':    {'summer': 1.2, 'monsoon': 5.0, 'winter': 1.0},
        'New Delhi': {'summer': 3.5, 'monsoon': 2.5, 'winter': 4.0},
        'Bengaluru': {'summer': 1.5, 'monsoon': 2.0, 'winter': 1.5},
        'Chennai':   {'summer': 2.5, 'monsoon': 3.0, 'winter': 1.0},
        'Hyderabad': {'summer': 2.0, 'monsoon': 2.0, 'winter': 1.5},
        'Kolkata':   {'summer': 2.5, 'monsoon': 4.0, 'winter': 1.8},
        'Pune':      {'summer': 1.8, 'monsoon': 3.5, 'winter': 1.5},
        'Ahmedabad': {'summer': 3.0, 'monsoon': 2.0, 'winter': 2.0},
        'Jaipur':    {'summer': 3.5, 'monsoon': 1.5, 'winter': 3.0},
        'Lucknow':   {'summer': 3.0, 'monsoon': 2.0, 'winter': 3.5}
    }
    
    # Product Definitions
    products = {
        'Rain': ['PRD001', 'PRD002', 'PRD003', 'PRD004'],
        'Heat': ['PRD005', 'PRD006', 'PRD007', 'PRD008', 'PRD009', 'PRD010', 'PRD011'],
        'Cold': ['PRD012', 'PRD013', 'PRD014', 'PRD015', 'PRD016'],
        'Neutral': ['PRD017', 'PRD018', 'PRD019', 'PRD020']
    }
    
    prices = {
        'PRD001': 499, 'PRD002': 899, 'PRD003': 1299, 'PRD004': 749,
        'PRD005': 34999, 'PRD006': 7999, 'PRD007': 1999, 'PRD008': 599, 'PRD009': 349, 'PRD010': 599, 'PRD011': 1499,
        'PRD012': 3499, 'PRD013': 1999, 'PRD014': 449, 'PRD015': 2999, 'PRD016': 999,
        'PRD017': 599, 'PRD018': 749, 'PRD019': 199, 'PRD020': 349
    }
    
    costs = {
        'PRD001': 199, 'PRD002': 399, 'PRD003': 649, 'PRD004': 349,
        'PRD005': 24999, 'PRD006': 4999, 'PRD007': 999, 'PRD008': 359, 'PRD009': 199, 'PRD010': 299, 'PRD011': 599,
        'PRD012': 1999, 'PRD013': 999, 'PRD014': 249, 'PRD015': 1499, 'PRD016': 499,
        'PRD017': 449, 'PRD018': 599, 'PRD019': 119, 'PRD020': 219
    }
    
    # Base demands by category
    base_demands = {
        'Rain': 22,    # avg of 15-30
        'Heat': 18,    # avg of 10-25
        'Cold': 15,    # avg of 10-20
        'Neutral': 60  # avg of 40-80
    }
    
    product_mapping = {}
    for cat, prods in products.items():
        for p in prods:
            product_mapping[p] = cat
            
    print("📊 Building date grid...")
    dates = pd.date_range(start=START_DATE, end=END_DATE)
    df = pd.MultiIndex.from_product(
        [dates, list(stores.keys()), list(product_mapping.keys())],
        names=['date', 'store_id', 'product_id']
    ).to_frame(index=False)
    
    # Add metadata
    df['city'] = df['store_id'].map(stores)
    df['category'] = df['product_id'].map(product_mapping)
    df['unit_price'] = df['product_id'].map(prices)
    df['unit_cost'] = df['product_id'].map(costs)
    df['day_of_week'] = df['date'].dt.dayofweek
    df['month'] = df['date'].dt.month
    
    print("🔄 Calculating seasonal and weekly multipliers...")
    # Base lambda for poisson distribution
    df['base_demand'] = df['category'].map(base_demands)
    
    # Day of week multiplier (20% dip on Monday, 15% spike on weekends)
    def get_dow_multiplier(dow):
        if dow == 0: return 0.8
        elif dow >= 5: return 1.15
        return 1.0
    
    df['dow_mult'] = df['day_of_week'].map(get_dow_multiplier)
    
    # Seasonal Multipliers based on category and city
    df['season_mult'] = 1.0
    
    # Summer (Mar-Jun) -> Heat
    summer_mask = (df['category'] == 'Heat') & (df['month'].isin([3, 4, 5, 6]))
    df.loc[summer_mask, 'season_mult'] = df.loc[summer_mask, 'city'].map(lambda c: city_multipliers[c]['summer'])
    
    # Monsoon (Jun-Sep) -> Rain
    monsoon_mask = (df['category'] == 'Rain') & (df['month'].isin([6, 7, 8, 9]))
    df.loc[monsoon_mask, 'season_mult'] = df.loc[monsoon_mask, 'city'].map(lambda c: city_multipliers[c]['monsoon'])
    
    # Winter (Nov-Feb) -> Cold
    winter_mask = (df['category'] == 'Cold') & (df['month'].isin([11, 12, 1, 2]))
    df.loc[winter_mask, 'season_mult'] = df.loc[winter_mask, 'city'].map(lambda c: city_multipliers[c]['winter'])
    
    # Festival Multipliers (30-50% spike)
    # Diwali, Holi, Navratri, Independence Day
    festival_dates = [
        '2024-11-01', '2024-11-02', '2024-11-03', '2025-10-20', '2025-10-21', '2025-10-22', # Diwali
        '2024-03-25', '2025-03-14', # Holi
        '2024-10-03', '2024-10-12', '2025-09-22', '2025-10-02', # Navratri approx bounds
        '2024-08-15', '2025-08-15' # Independence Day
    ]
    festival_dates = pd.to_datetime(festival_dates)
    df['fest_mult'] = 1.0
    df.loc[df['date'].isin(festival_dates), 'fest_mult'] = np.random.uniform(1.3, 1.5, size=df['date'].isin(festival_dates).sum())
    
    print("📈 Generating sales figures...")
    # Calculate final lambda
    df['final_lambda'] = df['base_demand'] * df['dow_mult'] * df['season_mult'] * df['fest_mult']
    
    # Generate quantity sold using Poisson distribution
    df['quantity_sold'] = np.random.poisson(df['final_lambda'])
    
    # Financials
    df['total_revenue'] = df['quantity_sold'] * df['unit_price']
    df['total_cost'] = df['quantity_sold'] * df['unit_cost']
    df['profit'] = df['total_revenue'] - df['total_cost']
    
    # Clean up dataframe
    sales_df = df[['date', 'store_id', 'product_id', 'quantity_sold', 'unit_price', 'unit_cost', 'total_revenue', 'total_cost', 'profit']]
    
    print("📦 Generating inventory data...")
    # Inventory Simulation
    inventory_data = []
    
    for store in stores.keys():
        for prod in product_mapping.keys():
            # Get max sales observed in a month to estimate max stock level
            max_daily_sales = df[(df['store_id'] == store) & (df['product_id'] == prod)]['quantity_sold'].max()
            max_stock = max(50, int(max_daily_sales * 14)) # Approx 2 weeks cover
            
            # Simulate current inventory
            current_inventory = np.random.randint(int(max_stock * 0.1), max_stock)
            last_restock = dates[-1] - timedelta(days=np.random.randint(1, 15))
            
            inventory_data.append({
                'store_id': store,
                'product_id': prod,
                'current_inventory': current_inventory,
                'last_restock_date': last_restock.strftime('%Y-%m-%d')
            })
            
    inventory_df = pd.DataFrame(inventory_data)
    
    print("💾 Saving files...")
    sales_file = os.path.join(output_dir, 'sales_data.csv')
    inv_file = os.path.join(output_dir, 'current_inventory.csv')
    
    sales_df.to_csv(sales_file, index=False)
    inventory_df.to_csv(inv_file, index=False)
    
    print(f"✅ Generated {len(sales_df)} sales records.")
    print(f"✅ Generated {len(inventory_df)} inventory records.")
    print(f"✅ Saved to: {output_dir}")
    print("Summary Stats:")
    print(sales_df[['quantity_sold', 'total_revenue', 'profit']].describe())

if __name__ == "__main__":
    generate_data()
