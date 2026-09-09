-- =============================================================================
-- PREDICTIVE SUPPLY CHAIN CONTROL TOWER — MS-SQL Star Schema
-- =============================================================================
-- Database: SupplyChainControlTower
-- Brand:    MegaMart India (Fictional Indian Retail Chain)
-- Run this script in SSMS to create all tables.
-- =============================================================================

-- Create the database (if not exists)
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'SupplyChainControlTower')
BEGIN
    CREATE DATABASE SupplyChainControlTower;
END
GO

USE SupplyChainControlTower;
GO

-- =============================================================================
-- DIMENSION TABLES
-- =============================================================================

-- ─── Dim_Date ───────────────────────────────────────────────────────────────
-- Date dimension with Indian fiscal year and major Indian festivals
IF OBJECT_ID('dbo.Dim_Date', 'U') IS NOT NULL DROP TABLE dbo.Dim_Date;
CREATE TABLE dbo.Dim_Date (
    date_key            INT             PRIMARY KEY,    -- YYYYMMDD format
    full_date           DATE            NOT NULL UNIQUE,
    day_of_week         TINYINT         NOT NULL,       -- 0=Monday, 6=Sunday
    day_name            VARCHAR(10)     NOT NULL,       -- Monday, Tuesday, etc.
    day_of_month        TINYINT         NOT NULL,
    week_of_year        TINYINT         NOT NULL,
    month_number        TINYINT         NOT NULL,
    month_name          VARCHAR(10)     NOT NULL,
    quarter             TINYINT         NOT NULL,
    year                SMALLINT        NOT NULL,
    is_weekend          BIT             NOT NULL DEFAULT 0,
    is_holiday          BIT             NOT NULL DEFAULT 0,
    holiday_name        VARCHAR(50)     NULL,
    indian_fiscal_year  VARCHAR(10)     NOT NULL,       -- e.g., 'FY2024-25'
    season              VARCHAR(15)     NOT NULL,       -- Summer/Monsoon/Autumn/Winter
    is_monsoon          BIT             NOT NULL DEFAULT 0,
    is_festival_season  BIT             NOT NULL DEFAULT 0
);
GO

-- ─── Dim_Store ──────────────────────────────────────────────────────────────
-- 10 MegaMart store locations across India
IF OBJECT_ID('dbo.Dim_Store', 'U') IS NOT NULL DROP TABLE dbo.Dim_Store;
CREATE TABLE dbo.Dim_Store (
    store_key           INT             PRIMARY KEY IDENTITY(1,1),
    store_id            VARCHAR(10)     NOT NULL UNIQUE,
    store_name          VARCHAR(50)     NOT NULL,
    city                VARCHAR(30)     NOT NULL,
    state               VARCHAR(30)     NOT NULL,
    region              VARCHAR(10)     NOT NULL,       -- North/South/East/West
    latitude            DECIMAL(8,4)    NOT NULL,
    longitude           DECIMAL(8,4)    NOT NULL,
    warehouse_capacity  INT             NOT NULL,
    created_at          DATETIME2       NOT NULL DEFAULT GETDATE()
);
GO

-- ─── Dim_Product ────────────────────────────────────────────────────────────
-- 20 products across weather-sensitive and neutral categories
IF OBJECT_ID('dbo.Dim_Product', 'U') IS NOT NULL DROP TABLE dbo.Dim_Product;
CREATE TABLE dbo.Dim_Product (
    product_key             INT             PRIMARY KEY IDENTITY(1,1),
    product_id              VARCHAR(10)     NOT NULL UNIQUE,
    product_name            VARCHAR(50)     NOT NULL,
    category                VARCHAR(30)     NOT NULL,       -- Rain/Heat/Cold/Neutral
    weather_sensitivity     VARCHAR(15)     NOT NULL,       -- High/Medium/Low/None
    unit_price_inr          DECIMAL(10,2)   NOT NULL,
    unit_cost_inr           DECIMAL(10,2)   NOT NULL,
    margin_pct              DECIMAL(5,2)    NOT NULL,       -- Profit margin %
    supplier_lead_time_days INT             NOT NULL,       -- Days to restock
    reorder_point           INT             NOT NULL,       -- Min stock to trigger reorder
    max_stock_level         INT             NOT NULL,
    created_at              DATETIME2       NOT NULL DEFAULT GETDATE()
);
GO

-- ─── Dim_Weather_Condition ──────────────────────────────────────────────────
-- WMO weather code mapping with severity levels
IF OBJECT_ID('dbo.Dim_Weather_Condition', 'U') IS NOT NULL DROP TABLE dbo.Dim_Weather_Condition;
CREATE TABLE dbo.Dim_Weather_Condition (
    weather_code        INT             PRIMARY KEY,
    description         VARCHAR(50)     NOT NULL,
    severity_level      VARCHAR(10)     NOT NULL,       -- Clear/Mild/Moderate/Severe/Extreme
    severity_score      TINYINT         NOT NULL        -- 1-5
);
GO

-- =============================================================================
-- FACT TABLES
-- =============================================================================

-- ─── Fact_Sales ─────────────────────────────────────────────────────────────
-- Daily sales transactions per store per product
IF OBJECT_ID('dbo.Fact_Sales', 'U') IS NOT NULL DROP TABLE dbo.Fact_Sales;
CREATE TABLE dbo.Fact_Sales (
    sale_id             BIGINT          PRIMARY KEY IDENTITY(1,1),
    date_key            INT             NOT NULL,
    store_key           INT             NOT NULL,
    product_key         INT             NOT NULL,
    quantity_sold       INT             NOT NULL,
    unit_price_inr      DECIMAL(10,2)   NOT NULL,
    total_revenue_inr   DECIMAL(12,2)   NOT NULL,
    total_cost_inr      DECIMAL(12,2)   NOT NULL,
    profit_inr          DECIMAL(12,2)   NOT NULL,

    CONSTRAINT FK_Sales_Date    FOREIGN KEY (date_key)    REFERENCES dbo.Dim_Date(date_key),
    CONSTRAINT FK_Sales_Store   FOREIGN KEY (store_key)   REFERENCES dbo.Dim_Store(store_key),
    CONSTRAINT FK_Sales_Product FOREIGN KEY (product_key) REFERENCES dbo.Dim_Product(product_key)
);
GO

-- Index for common query patterns
CREATE NONCLUSTERED INDEX IX_FactSales_DateStore 
    ON dbo.Fact_Sales(date_key, store_key) INCLUDE (product_key, quantity_sold);
CREATE NONCLUSTERED INDEX IX_FactSales_Product 
    ON dbo.Fact_Sales(product_key) INCLUDE (date_key, quantity_sold);
GO

-- ─── Fact_Weather ───────────────────────────────────────────────────────────
-- Daily weather observations per store location
IF OBJECT_ID('dbo.Fact_Weather', 'U') IS NOT NULL DROP TABLE dbo.Fact_Weather;
CREATE TABLE dbo.Fact_Weather (
    weather_id              BIGINT          PRIMARY KEY IDENTITY(1,1),
    date_key                INT             NOT NULL,
    store_key               INT             NOT NULL,
    weather_code            INT             NULL,
    max_temp_c              DECIMAL(5,2)    NULL,
    min_temp_c              DECIMAL(5,2)    NULL,
    mean_temp_c             DECIMAL(5,2)    NULL,
    precipitation_mm        DECIMAL(7,2)    NULL,
    wind_speed_max_kmh      DECIMAL(6,2)    NULL,
    humidity_max_pct        DECIMAL(5,2)    NULL,
    humidity_min_pct        DECIMAL(5,2)    NULL,
    weather_severity_index  DECIMAL(5,2)    NULL,       -- Composite score 0-100
    is_extreme_weather      BIT             NOT NULL DEFAULT 0,
    data_source             VARCHAR(20)     NOT NULL DEFAULT 'open-meteo',

    CONSTRAINT FK_Weather_Date  FOREIGN KEY (date_key)  REFERENCES dbo.Dim_Date(date_key),
    CONSTRAINT FK_Weather_Store FOREIGN KEY (store_key) REFERENCES dbo.Dim_Store(store_key),
    CONSTRAINT UQ_Weather_DateStore UNIQUE (date_key, store_key)
);
GO

-- ─── Fact_Predictions ───────────────────────────────────────────────────────
-- ML-generated demand predictions with confidence intervals
IF OBJECT_ID('dbo.Fact_Predictions', 'U') IS NOT NULL DROP TABLE dbo.Fact_Predictions;
CREATE TABLE dbo.Fact_Predictions (
    prediction_id           BIGINT          PRIMARY KEY IDENTITY(1,1),
    date_key                INT             NOT NULL,
    store_key               INT             NOT NULL,
    product_key             INT             NOT NULL,
    predicted_qty           DECIMAL(10,2)   NOT NULL,
    lower_bound_80          DECIMAL(10,2)   NULL,       -- 80% confidence interval lower
    upper_bound_80          DECIMAL(10,2)   NULL,       -- 80% confidence interval upper
    lower_bound_95          DECIMAL(10,2)   NULL,       -- 95% confidence interval lower
    upper_bound_95          DECIMAL(10,2)   NULL,       -- 95% confidence interval upper
    model_name              VARCHAR(30)     NOT NULL,
    model_version           VARCHAR(20)     NOT NULL,
    prediction_date         DATETIME2       NOT NULL DEFAULT GETDATE(),

    CONSTRAINT FK_Pred_Date     FOREIGN KEY (date_key)    REFERENCES dbo.Dim_Date(date_key),
    CONSTRAINT FK_Pred_Store    FOREIGN KEY (store_key)   REFERENCES dbo.Dim_Store(store_key),
    CONSTRAINT FK_Pred_Product  FOREIGN KEY (product_key) REFERENCES dbo.Dim_Product(product_key)
);
GO

CREATE NONCLUSTERED INDEX IX_FactPredictions_DateStore
    ON dbo.Fact_Predictions(date_key, store_key, product_key);
GO

-- ─── Fact_Stockout_Risk ─────────────────────────────────────────────────────
-- Stockout risk assessments with cost-of-inaction
IF OBJECT_ID('dbo.Fact_Stockout_Risk', 'U') IS NOT NULL DROP TABLE dbo.Fact_Stockout_Risk;
CREATE TABLE dbo.Fact_Stockout_Risk (
    risk_id                     BIGINT          PRIMARY KEY IDENTITY(1,1),
    assessment_date             DATE            NOT NULL,
    store_key                   INT             NOT NULL,
    product_key                 INT             NOT NULL,
    current_inventory           INT             NOT NULL,
    predicted_demand_7day       DECIMAL(10,2)   NOT NULL,
    predicted_demand_upper_95   DECIMAL(10,2)   NOT NULL,  -- Worst case demand
    supplier_lead_time_days     INT             NOT NULL,
    safety_stock_needed         INT             NOT NULL,
    risk_score                  DECIMAL(5,4)    NOT NULL,  -- 0.0000 to 1.0000
    risk_level                  VARCHAR(10)     NOT NULL,  -- LOW/MEDIUM/HIGH/CRITICAL
    cost_of_inaction_inr        DECIMAL(14,2)   NOT NULL,  -- Estimated lost revenue ₹
    recommended_reorder_qty     INT             NOT NULL,
    assessed_at                 DATETIME2       NOT NULL DEFAULT GETDATE(),

    CONSTRAINT FK_Risk_Store    FOREIGN KEY (store_key)   REFERENCES dbo.Dim_Store(store_key),
    CONSTRAINT FK_Risk_Product  FOREIGN KEY (product_key) REFERENCES dbo.Dim_Product(product_key)
);
GO

CREATE NONCLUSTERED INDEX IX_FactRisk_Level
    ON dbo.Fact_Stockout_Risk(risk_level) INCLUDE (store_key, product_key, cost_of_inaction_inr);
GO

-- =============================================================================
-- SEED DATA — Dimension Tables
-- =============================================================================

-- ─── Seed Dim_Store ─────────────────────────────────────────────────────────
INSERT INTO dbo.Dim_Store (store_id, store_name, city, state, region, latitude, longitude, warehouse_capacity)
VALUES
    ('STR001', 'MegaMart Mumbai Central',    'Mumbai',       'Maharashtra',      'West',  19.0800, 72.8800, 50000),
    ('STR002', 'MegaMart Delhi NCR',         'New Delhi',    'Delhi',            'North', 28.6100, 77.2100, 55000),
    ('STR003', 'MegaMart Bangalore HSR',     'Bengaluru',    'Karnataka',        'South', 12.9700, 77.5900, 45000),
    ('STR004', 'MegaMart Chennai T Nagar',   'Chennai',      'Tamil Nadu',       'South', 13.0800, 80.2700, 42000),
    ('STR005', 'MegaMart Hyderabad Hitech',  'Hyderabad',    'Telangana',        'South', 17.3900, 78.4900, 40000),
    ('STR006', 'MegaMart Kolkata Salt Lake', 'Kolkata',      'West Bengal',      'East',  22.5700, 88.3600, 38000),
    ('STR007', 'MegaMart Pune Hinjewadi',    'Pune',         'Maharashtra',      'West',  18.5200, 73.8600, 35000),
    ('STR008', 'MegaMart Ahmedabad SG',      'Ahmedabad',    'Gujarat',          'West',  23.0200, 72.5700, 36000),
    ('STR009', 'MegaMart Jaipur Malviya',    'Jaipur',       'Rajasthan',        'North', 26.9200, 75.7900, 32000),
    ('STR010', 'MegaMart Lucknow Gomti',     'Lucknow',      'Uttar Pradesh',    'North', 26.8500, 80.9500, 30000);
GO

-- ─── Seed Dim_Product ───────────────────────────────────────────────────────
-- Categories: Rain-driven, Heat-driven, Cold-driven, Neutral (control group)
INSERT INTO dbo.Dim_Product 
    (product_id, product_name, category, weather_sensitivity, unit_price_inr, unit_cost_inr, margin_pct, supplier_lead_time_days, reorder_point, max_stock_level)
VALUES
    -- Rain-driven products
    ('PRD001', 'Umbrella',          'Rain',     'High',     499.00,   199.00,  60.12,  3,  200,  2000),
    ('PRD002', 'Raincoat',          'Rain',     'High',     899.00,   399.00,  55.62,  5,  150,  1500),
    ('PRD003', 'Waterproof Bag',    'Rain',     'Medium',   1299.00,  649.00,  50.04,  7,  100,  1000),
    ('PRD004', 'Gumboots',          'Rain',     'High',     749.00,   349.00,  53.40,  5,  120,  1200),

    -- Heat-driven products
    ('PRD005', 'AC Unit',           'Heat',     'High',     34999.00, 24999.00, 28.57, 14,  30,   300),
    ('PRD006', 'Air Cooler',        'Heat',     'High',     7999.00,  4999.00, 37.50,  7,  80,   800),
    ('PRD007', 'Table Fan',         'Heat',     'Medium',   1999.00,  999.00,  50.03,  5,  150,  1500),
    ('PRD008', 'Cold Drinks (Case)','Heat',     'Medium',   599.00,   359.00,  40.07,  2,  500,  5000),
    ('PRD009', 'Ice Cream (Box)',   'Heat',     'Medium',   349.00,   199.00,  42.98,  1,  400,  4000),
    ('PRD010', 'Sunscreen',         'Heat',     'Low',      599.00,   299.00,  50.08,  5,  200,  2000),
    ('PRD011', 'Sunglasses',        'Heat',     'Low',      1499.00,  599.00,  60.04,  7,  100,  1000),

    -- Cold-driven products
    ('PRD012', 'Room Heater',       'Cold',     'High',     3499.00,  1999.00, 42.87,  7,  60,   600),
    ('PRD013', 'Blanket',           'Cold',     'High',     1999.00,  999.00,  50.03,  5,  150,  1500),
    ('PRD014', 'Hot Beverages (Kg)','Cold',     'Medium',   449.00,   249.00,  44.54,  2,  300,  3000),
    ('PRD015', 'Jacket',            'Cold',     'High',     2999.00,  1499.00, 50.02,  10, 80,   800),
    ('PRD016', 'Thermal Wear',      'Cold',     'Medium',   999.00,   499.00,  50.05,  7,  100,  1000),

    -- Neutral products (control group — should NOT correlate with weather)
    ('PRD017', 'Basmati Rice (5Kg)','Neutral',  'None',     599.00,   449.00,  25.04,  3,  500,  5000),
    ('PRD018', 'Cooking Oil (5L)',  'Neutral',  'None',     749.00,   599.00,  20.03,  3,  500,  5000),
    ('PRD019', 'Toothpaste',        'Neutral',  'None',     199.00,   119.00,  40.20,  3,  400,  4000),
    ('PRD020', 'Detergent (Kg)',    'Neutral',  'None',     349.00,   219.00,  37.25,  3,  400,  4000);
GO

-- ─── Seed Dim_Weather_Condition ─────────────────────────────────────────────
-- WMO weather codes with severity mapping
INSERT INTO dbo.Dim_Weather_Condition (weather_code, description, severity_level, severity_score)
VALUES
    (0,  'Clear sky',                   'Clear',    1),
    (1,  'Mainly clear',               'Clear',    1),
    (2,  'Partly cloudy',              'Mild',     2),
    (3,  'Overcast',                   'Mild',     2),
    (45, 'Fog',                        'Moderate', 3),
    (48, 'Depositing rime fog',        'Moderate', 3),
    (51, 'Light drizzle',              'Mild',     2),
    (53, 'Moderate drizzle',           'Moderate', 3),
    (55, 'Dense drizzle',              'Moderate', 3),
    (56, 'Light freezing drizzle',     'Moderate', 3),
    (57, 'Dense freezing drizzle',     'Severe',   4),
    (61, 'Slight rain',               'Moderate', 3),
    (63, 'Moderate rain',             'Severe',   4),
    (65, 'Heavy rain',                'Extreme',  5),
    (66, 'Light freezing rain',        'Severe',   4),
    (67, 'Heavy freezing rain',        'Extreme',  5),
    (71, 'Slight snowfall',            'Moderate', 3),
    (73, 'Moderate snowfall',          'Severe',   4),
    (75, 'Heavy snowfall',             'Extreme',  5),
    (77, 'Snow grains',               'Moderate', 3),
    (80, 'Slight rain showers',        'Moderate', 3),
    (81, 'Moderate rain showers',      'Severe',   4),
    (82, 'Violent rain showers',       'Extreme',  5),
    (85, 'Slight snow showers',        'Moderate', 3),
    (86, 'Heavy snow showers',         'Extreme',  5),
    (95, 'Thunderstorm',              'Severe',   4),
    (96, 'Thunderstorm with slight hail', 'Extreme', 5),
    (99, 'Thunderstorm with heavy hail',  'Extreme', 5);
GO

-- =============================================================================
-- POPULATE Dim_Date (2024-01-01 to 2025-12-31)
-- =============================================================================
-- Uses a recursive CTE to generate 2 years of dates with Indian context
;WITH DateSeries AS (
    SELECT CAST('2024-01-01' AS DATE) AS dt
    UNION ALL
    SELECT DATEADD(DAY, 1, dt)
    FROM DateSeries
    WHERE dt < '2025-12-31'
)
INSERT INTO dbo.Dim_Date (
    date_key, full_date, day_of_week, day_name, day_of_month,
    week_of_year, month_number, month_name, quarter, year,
    is_weekend, is_holiday, holiday_name, indian_fiscal_year,
    season, is_monsoon, is_festival_season
)
SELECT
    CAST(FORMAT(dt, 'yyyyMMdd') AS INT)         AS date_key,
    dt                                           AS full_date,
    (DATEPART(WEEKDAY, dt) + 5) % 7             AS day_of_week,  -- 0=Mon, 6=Sun
    DATENAME(WEEKDAY, dt)                        AS day_name,
    DAY(dt)                                      AS day_of_month,
    DATEPART(ISO_WEEK, dt)                       AS week_of_year,
    MONTH(dt)                                    AS month_number,
    DATENAME(MONTH, dt)                          AS month_name,
    DATEPART(QUARTER, dt)                        AS quarter,
    YEAR(dt)                                     AS year,
    CASE WHEN DATEPART(WEEKDAY, dt) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend,
    0 AS is_holiday,
    NULL AS holiday_name,
    CASE
        WHEN MONTH(dt) >= 4 THEN 'FY' + CAST(YEAR(dt) AS VARCHAR) + '-' + RIGHT(CAST(YEAR(dt)+1 AS VARCHAR), 2)
        ELSE 'FY' + CAST(YEAR(dt)-1 AS VARCHAR) + '-' + RIGHT(CAST(YEAR(dt) AS VARCHAR), 2)
    END AS indian_fiscal_year,
    CASE
        WHEN MONTH(dt) IN (3, 4, 5)     THEN 'Summer'
        WHEN MONTH(dt) IN (6, 7, 8, 9)  THEN 'Monsoon'
        WHEN MONTH(dt) IN (10, 11)       THEN 'Autumn'
        ELSE 'Winter'
    END AS season,
    CASE WHEN MONTH(dt) IN (6, 7, 8, 9) THEN 1 ELSE 0 END AS is_monsoon,
    CASE WHEN MONTH(dt) IN (10, 11) THEN 1 ELSE 0 END AS is_festival_season
FROM DateSeries
OPTION (MAXRECURSION 800);
GO

-- ─── Mark Indian Holidays & Festivals ───────────────────────────────────────
-- 2024 Festivals
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Republic Day'       WHERE full_date = '2024-01-26';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Holi'               WHERE full_date IN ('2024-03-25', '2024-03-26');
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Independence Day'   WHERE full_date = '2024-08-15';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Ganesh Chaturthi'   WHERE full_date = '2024-09-07';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Navratri'           WHERE full_date BETWEEN '2024-10-03' AND '2024-10-12';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Dussehra'           WHERE full_date = '2024-10-12';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Diwali'             WHERE full_date IN ('2024-11-01', '2024-11-02', '2024-11-03');
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Christmas'          WHERE full_date = '2024-12-25';

-- 2025 Festivals
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Republic Day'       WHERE full_date = '2025-01-26';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Holi'               WHERE full_date IN ('2025-03-14', '2025-03-15');
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Eid ul-Fitr'        WHERE full_date = '2025-03-31';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Independence Day'   WHERE full_date = '2025-08-15';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Ganesh Chaturthi'   WHERE full_date = '2025-08-27';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Navratri'           WHERE full_date BETWEEN '2025-09-22' AND '2025-10-02';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Dussehra'           WHERE full_date = '2025-10-02';
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Diwali'             WHERE full_date IN ('2025-10-20', '2025-10-21', '2025-10-22');
UPDATE dbo.Dim_Date SET is_holiday = 1, holiday_name = 'Christmas'          WHERE full_date = '2025-12-25';
GO

-- Update festival_season flag for Navratri-Diwali period
UPDATE dbo.Dim_Date SET is_festival_season = 1 
WHERE (full_date BETWEEN '2024-10-01' AND '2024-11-05')
   OR (full_date BETWEEN '2025-09-20' AND '2025-10-25');
GO

-- =============================================================================
-- VIEWS for Power BI
-- =============================================================================

-- ─── View: Sales with Weather Context ───────────────────────────────────────
IF OBJECT_ID('dbo.vw_SalesWeatherAnalysis', 'V') IS NOT NULL DROP VIEW dbo.vw_SalesWeatherAnalysis;
GO
CREATE VIEW dbo.vw_SalesWeatherAnalysis AS
SELECT
    d.full_date,
    d.day_name,
    d.month_name,
    d.season,
    d.is_monsoon,
    d.is_holiday,
    d.holiday_name,
    d.is_festival_season,
    s.store_name,
    s.city,
    s.state,
    s.region,
    p.product_name,
    p.category,
    p.weather_sensitivity,
    fs.quantity_sold,
    fs.total_revenue_inr,
    fs.profit_inr,
    fw.max_temp_c,
    fw.min_temp_c,
    fw.precipitation_mm,
    fw.weather_severity_index,
    fw.is_extreme_weather,
    wc.description AS weather_description,
    wc.severity_level
FROM dbo.Fact_Sales fs
JOIN dbo.Dim_Date d          ON fs.date_key    = d.date_key
JOIN dbo.Dim_Store s         ON fs.store_key   = s.store_key
JOIN dbo.Dim_Product p       ON fs.product_key = p.product_key
LEFT JOIN dbo.Fact_Weather fw ON fs.date_key   = fw.date_key AND fs.store_key = fw.store_key
LEFT JOIN dbo.Dim_Weather_Condition wc ON fw.weather_code = wc.weather_code;
GO

-- ─── View: Stockout Risk Dashboard ──────────────────────────────────────────
IF OBJECT_ID('dbo.vw_StockoutRiskDashboard', 'V') IS NOT NULL DROP VIEW dbo.vw_StockoutRiskDashboard;
GO
CREATE VIEW dbo.vw_StockoutRiskDashboard AS
SELECT
    sr.assessment_date,
    s.store_name,
    s.city,
    s.region,
    p.product_name,
    p.category,
    sr.current_inventory,
    sr.predicted_demand_7day,
    sr.predicted_demand_upper_95,
    sr.risk_score,
    sr.risk_level,
    sr.cost_of_inaction_inr,
    sr.recommended_reorder_qty,
    p.supplier_lead_time_days
FROM dbo.Fact_Stockout_Risk sr
JOIN dbo.Dim_Store s   ON sr.store_key   = s.store_key
JOIN dbo.Dim_Product p ON sr.product_key = p.product_key;
GO

-- ─── View: Predictions with Actuals ─────────────────────────────────────────
IF OBJECT_ID('dbo.vw_PredictionsVsActuals', 'V') IS NOT NULL DROP VIEW dbo.vw_PredictionsVsActuals;
GO
CREATE VIEW dbo.vw_PredictionsVsActuals AS
SELECT
    d.full_date,
    s.store_name,
    s.city,
    p.product_name,
    p.category,
    fp.predicted_qty,
    fp.lower_bound_80,
    fp.upper_bound_80,
    fp.lower_bound_95,
    fp.upper_bound_95,
    fp.model_name,
    fs.quantity_sold AS actual_qty,
    ABS(fp.predicted_qty - ISNULL(fs.quantity_sold, 0)) AS absolute_error
FROM dbo.Fact_Predictions fp
JOIN dbo.Dim_Date d    ON fp.date_key    = d.date_key
JOIN dbo.Dim_Store s   ON fp.store_key   = s.store_key
JOIN dbo.Dim_Product p ON fp.product_key = p.product_key
LEFT JOIN dbo.Fact_Sales fs ON fp.date_key = fs.date_key 
    AND fp.store_key = fs.store_key 
    AND fp.product_key = fs.product_key;
GO

PRINT '✅ Star schema created successfully for SupplyChainControlTower!';
PRINT '   Tables: Dim_Date, Dim_Store, Dim_Product, Dim_Weather_Condition';
PRINT '           Fact_Sales, Fact_Weather, Fact_Predictions, Fact_Stockout_Risk';
PRINT '   Views:  vw_SalesWeatherAnalysis, vw_StockoutRiskDashboard, vw_PredictionsVsActuals';
GO
