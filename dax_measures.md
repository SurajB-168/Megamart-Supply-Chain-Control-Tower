# 📊 Power BI DAX Measures Reference

This document serves as the central repository for all DAX measures created for the MegaMart Predictive Supply Chain Control Tower project. 

## 1. CORRELATION ANALYSIS

### Weather-Sales Correlation Coefficient (Pearson)
```dax
Weather_Sales_Correlation = 
VAR AvgSales = AVERAGEX(fact_sales, fact_sales[total_revenue_inr])
VAR AvgWeather = AVERAGEX(fact_weather, fact_weather[temperature_c]) // Can be changed based on weather metric
VAR Numerator = SUMX(
    NATURALINNERJOIN(fact_sales, fact_weather),
    (fact_sales[total_revenue_inr] - AvgSales) * (fact_weather[temperature_c] - AvgWeather)
)
VAR DenomSales = SQRT(SUMX(fact_sales, POWER(fact_sales[total_revenue_inr] - AvgSales, 2)))
VAR DenomWeather = SQRT(SUMX(fact_weather, POWER(fact_weather[temperature_c] - AvgWeather, 2)))
RETURN DIVIDE(Numerator, DenomSales * DenomWeather, BLANK())
```
* **Table:** `fact_sales` / `fact_weather`
* **Description:** Calculates the Pearson correlation coefficient between daily sales and a specific weather metric (e.g., temperature or rainfall).
* **Best Visual:** Scatter Plot, KPI Card

### Monsoon Impact Index
```dax
Monsoon_Impact_Index = 
VAR AvgSalesMonsoon = CALCULATE(AVERAGE(fact_sales[total_revenue_inr]), dim_date[season] = "Monsoon")
VAR AvgSalesNonMonsoon = CALCULATE(AVERAGE(fact_sales[total_revenue_inr]), dim_date[season] <> "Monsoon")
RETURN DIVIDE(AvgSalesMonsoon - AvgSalesNonMonsoon, AvgSalesNonMonsoon, 0)
```
* **Table:** `fact_sales`
* **Description:** Measures the percentage difference in average sales during the monsoon season compared to the rest of the year.
* **Best Visual:** Clustered Bar Chart (by Product), Card

---

## 2. DEMAND METRICS

### Total Revenue
```dax
Total_Revenue = SUM(fact_sales[total_revenue_inr])
```
* **Table:** `fact_sales`
* **Description:** The sum of all revenue generated in INR.
* **Best Visual:** Card, Line Chart

### Total Profit
```dax
Total_Profit = SUM(fact_sales[profit_inr])
```
* **Table:** `fact_sales`
* **Description:** The sum of all profit generated in INR.
* **Best Visual:** Card, Waterfall Chart

### Profit Margin %
```dax
Profit_Margin_% = DIVIDE([Total_Profit], [Total_Revenue], 0)
```
* **Table:** `fact_sales`
* **Description:** The ratio of profit to total revenue, displayed as a percentage.
* **Best Visual:** Gauge, Card

### 7-Day Rolling Avg Sales
```dax
7_Day_Rolling_Avg_Sales = 
AVERAGEX(
    DATESINPERIOD(dim_date[date], LASTDATE(dim_date[date]), -7, DAY),
    [Total_Revenue]
)
```
* **Table:** `fact_sales`
* **Description:** Smoothed sales trend over the last 7 days.
* **Best Visual:** Line Chart

### YoY Sales Growth %
```dax
YoY_Sales_Growth_% = 
VAR SalesThisYear = [Total_Revenue]
VAR SalesLastYear = CALCULATE([Total_Revenue], SAMEPERIODLASTYEAR(dim_date[date]))
RETURN DIVIDE(SalesThisYear - SalesLastYear, SalesLastYear, 0)
```
* **Table:** `fact_sales`
* **Description:** Year-over-year percentage growth in total revenue.
* **Best Visual:** KPI Visual, Line and Stacked Column Chart

### Sales Per Store
```dax
Sales_Per_Store = DIVIDE([Total_Revenue], DISTINCTCOUNT(fact_sales[store_id]), 0)
```
* **Table:** `fact_sales`
* **Description:** Average revenue generated per store.
* **Best Visual:** Map, Bar Chart

---

## 3. STOCKOUT RISK MEASURES

### Stockout Risk Flag
```dax
Stockout_Risk_Flag = 
SWITCH(
    TRUE(),
    fact_stockout_alerts[risk_level] = "Critical", "#FF0000", -- Red
    fact_stockout_alerts[risk_level] = "High", "#FFA500", -- Orange/Yellow
    fact_stockout_alerts[risk_level] = "Medium", "#FFFF00", -- Yellow
    fact_stockout_alerts[risk_level] = "Low", "#00FF00", -- Green
    "#000000" -- Black default
)
```
* **Table:** `fact_stockout_alerts`
* **Description:** Returns a hex color code based on the assessed stockout risk level.
* **Best Visual:** Conditional Formatting for Tables/Matrices

### Cost of Inaction Total
```dax
Cost_of_Inaction_Total = SUM(fact_stockout_alerts[cost_of_inaction_inr])
```
* **Table:** `fact_stockout_alerts`
* **Description:** The total potential lost profit if stockouts occur. Format as ₹.
* **Best Visual:** Card, Treemap (by Product/Store)

### High Risk Product Count
```dax
High_Risk_Product_Count = 
CALCULATE(
    COUNTROWS(fact_stockout_alerts),
    fact_stockout_alerts[risk_level] IN {"High", "Critical"}
)
```
* **Table:** `fact_stockout_alerts`
* **Description:** Count of products currently at High or Critical risk of stockout.
* **Best Visual:** Multi-row Card, KPI

### Days Until Stockout
```dax
Days_Until_Stockout = 
VAR CurrentInv = SUM(fact_inventory[current_stock_level])
VAR AvgDailySales = [7_Day_Rolling_Avg_Sales]
RETURN DIVIDE(CurrentInv, AvgDailySales, BLANK())
```
* **Table:** `fact_inventory`
* **Description:** Estimated number of days until inventory is depleted.
* **Best Visual:** Table, Matrix, Scatter Plot (vs Cost of Inaction)

---

## 4. FORECAST MEASURES

### Forecast Accuracy %
```dax
Forecast_Accuracy_% = 
VAR Actuals = SUM(fact_sales[total_revenue_inr])
VAR Predicted = SUM(fact_predictions[predicted_demand])
RETURN 1 - DIVIDE(ABS(Predicted - Actuals), Actuals, BLANK())
```
* **Table:** `fact_predictions`
* **Description:** Measure of how close the predicted demand was to actual sales.
* **Best Visual:** Gauge, Card, Line Chart

### Prediction Confidence Band Width
```dax
Prediction_Confidence_Band_Width = SUM(fact_predictions[upper_95_ci]) - SUM(fact_predictions[lower_95_ci])
```
* **Table:** `fact_predictions`
* **Description:** The range of the 95% confidence interval, indicating forecast uncertainty.
* **Best Visual:** Ribbon Chart, Error Bars in Line Chart

### Forecast vs Actual Variance
```dax
Forecast_vs_Actual_Variance = SUM(fact_predictions[predicted_demand]) - SUM(fact_sales[quantity_sold])
```
* **Table:** `fact_predictions` / `fact_sales`
* **Description:** The absolute difference in units between predicted and actual sales.
* **Best Visual:** Waterfall Chart, Matrix

---

## 5. WEATHER IMPACT

### Weather Severity Score
```dax
Weather_Severity_Score = AVERAGE(fact_weather[weather_severity_index])
```
* **Table:** `fact_weather`
* **Description:** The average severity index of weather events.
* **Best Visual:** Card, Map tooltip

### Extreme Weather Days
```dax
Extreme_Weather_Days = 
CALCULATE(
    COUNTROWS(fact_weather),
    fact_weather[is_extreme_weather] = 1
)
```
* **Table:** `fact_weather`
* **Description:** Total number of days classified as having extreme weather.
* **Best Visual:** Card, Column Chart

### Rain Sales Multiplier
```dax
Rain_Sales_Multiplier = 
VAR RainySales = CALCULATE(AVERAGE(fact_sales[total_revenue_inr]), fact_weather[precipitation_mm] > 0)
VAR ClearSales = CALCULATE(AVERAGE(fact_sales[total_revenue_inr]), fact_weather[precipitation_mm] = 0)
RETURN DIVIDE(RainySales, ClearSales, 1)
```
* **Table:** `fact_sales` / `fact_weather`
* **Description:** Ratio of average daily sales on rainy days versus clear days. Best used filtered to Rain category products.
* **Best Visual:** Tornado Chart, Clustered Bar

---

## 6. CONDITIONAL FORMATTING RULES

### Risk Level Color Rules for Tables
- **Rule Type:** Format by Field Value
- **Based on field:** `[Stockout_Risk_Flag]`
- **Applies to:** Background color of `product_name`, `store_id`, `risk_level` columns in the Alert Matrix.

### Traffic Light KPI Indicators
```dax
Forecast_Accuracy_KPI_Color = 
SWITCH(
    TRUE(),
    [Forecast_Accuracy_%] >= 0.85, "#00FF00", -- Green (Excellent)
    [Forecast_Accuracy_%] >= 0.70, "#FFFF00", -- Yellow (Acceptable)
    "#FF0000" -- Red (Needs Review)
)
```
- **Rule Type:** Format by Field Value
- **Based on field:** `[Forecast_Accuracy_KPI_Color]`
- **Applies to:** Font color or icon color for the Forecast Accuracy metric.
