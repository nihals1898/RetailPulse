# Phase 14 — Power BI semantic model and KPI guidance

This phase prepares a Power BI import interface from the existing SQLite star schema, documents model relationships and KPI definitions, and provides copy-ready DAX measures. The user built the report manually in Power BI Desktop. The PBIX is saved locally but is ignored by Git because its source paths expose the Windows account name. Screenshots were shared during the build but are not stored in this repository.

## Power BI import interface

Run the local pipeline from the repository root:

```powershell
.\.venv\Scripts\python.exe run_sql.py
```

After the completed run, import the seven CSV files in `data/processed/powerbi_model/`:

| CSV file | Table name in the model | Grain |
|---|---|---|
| `dim_customer.csv` | `DimCustomer` | One row per cleaned customer |
| `dim_product.csv` | `DimProduct` | One row per cleaned product |
| `dim_store.csv` | `DimStore` | One row per cleaned store |
| `dim_date.csv` | `DimDate` | One row per calendar day |
| `fact_sales.csv` | `FactSales` | One row per cleaned order item |
| `fact_returns.csv` | `FactReturns` | One row per cleaned return event |
| `fact_inventory.csv` | `FactInventory` | One product/store/snapshot date |

The export is a dedicated copy of the local dimensions and facts, not another aggregation of the Gold summary CSVs. The `dim_date.csv` export omits the unused `date_key = 0` unknown-date row, so its date column has no blank member and can be marked as a date table. Current fact rows do not reference that unknown key. The export counts and folder are recorded in `sql_run_summary.json` under `power_bi_model_export_row_counts` and `power_bi_model_export_directory`.

## Step-by-step in Power BI Desktop

The screenshot you shared shows all seven tables in the **Data** pane. Continue in this order:

1. **Save the model.** Choose **File > Save As** and save it as `RetailPulse.pbix` under `dashboards/powerbi/` in the project. Use **Ctrl+S** after each later section.
2. **Rename the imported tables.** In the right-side **Data** pane, right-click a table name, choose **Rename**, and use the exact names in the table above: `DimCustomer`, `DimProduct`, `DimStore`, `DimDate`, `FactSales`, `FactReturns`, `FactInventory`. Your screenshot currently shows the original lowercase file names. The DAX formulas below use the renamed table names.
3. **Open Model view.** Select the connected-boxes/relationship icon on the left rail. Inspect any relationships Power BI detected automatically. Keep correct dimension-to-fact relationships; delete incorrect or fact-to-fact links.
4. **Create or correct the relationships.** Use **Modeling > Manage relationships > New** (or drag a dimension key onto the matching fact key in Model view). For each row in the relationship table below, check that cardinality is **One-to-many (1:*)**, cross-filter direction is **Single**, and the active setting matches the table. Create all listed links; the FactReturns original-order-date link is the only inactive one. Microsoft's [relationship instructions](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-create-and-manage-relationships) describe the dialog and the Model view drag-and-drop option.
5. **Set the date column's type and mark the date table.** Select `DimDate[date_value]` and set its data type to **Date** if Power BI imported it as Text. Select the `DimDate` table, then use **Table tools > Mark as date table** and choose `date_value`. Power BI checks that the selected dates are unique, nonblank, and continuous. Microsoft documents the [date table setup](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-date-tables).
6. **Add the measures.** Select `FactSales` in the Data pane, then choose **Home > New measure**. Open [`dashboards/powerbi/measures.dax`](../dashboards/powerbi/measures.dax), copy one complete measure definition at a time into the formula bar, and press **Enter** after each. Repeat for all definitions. If Power BI flags an expression, stop at that formula and review the relationship setup and spelling before continuing. Microsoft documents [creating measures](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-tutorial-create-measures).
7. **Format and check the measures.** Format revenue, discounts, refunds, AOV, and inventory value as EUR/currency; format discount rate, revenue growth, and return rate as Percentage; counts and quantities as whole numbers.
8. **Build a first report page.** Switch to Report view. Add Card visuals for `Total Revenue`, `Completed Orders`, `Average Order Value`, and `Customers Purchasing`. Add a Line chart with `DimDate[date_value]` on the X-axis and `Total Revenue` on the Y-axis. Add a single-select date slicer for inventory visuals because inventory values are snapshots.
9. **Save and inspect.** Save with **Ctrl+S**. Check that the line chart moves by date and that product/store filters change sales. Do not publish or share the model as part of this local phase.

Create one relationship at a time and compare it with the exact key pairs below. Do not add a direct connection between FactSales, FactReturns, and FactInventory.

## Semantic model relationships

Rename imported tables as shown above, then create these one-to-many relationships. Set cross-filter direction to **Single**, flowing from the dimension into the fact. Do not create relationships between fact tables.

| Dimension key | Fact key | Active? | Meaning |
|---|---|---:|---|
| `DimCustomer[customer_key]` | `FactSales[customer_key]` | Yes | Sales by customer |
| `DimCustomer[customer_key]` | `FactReturns[customer_key]` | Yes | Returns by customer |
| `DimProduct[product_key]` | `FactSales[product_key]` | Yes | Sales by product |
| `DimProduct[product_key]` | `FactReturns[product_key]` | Yes | Returns by product |
| `DimProduct[product_key]` | `FactInventory[product_key]` | Yes | Inventory by product |
| `DimStore[store_key]` | `FactSales[store_key]` | Yes | Sales by store |
| `DimStore[store_key]` | `FactReturns[store_key]` | Yes | Returns by store |
| `DimStore[store_key]` | `FactInventory[store_key]` | Yes | Inventory by store |
| `DimDate[date_key]` | `FactSales[order_date_key]` | Yes | Sales by order date |
| `DimDate[date_key]` | `FactReturns[return_date_key]` | Yes | Returns by return date (default) |
| `DimDate[date_key]` | `FactReturns[order_date_key]` | No | Returns by original order date |
| `DimDate[date_key]` | `FactInventory[snapshot_date_key]` | Yes | Inventory by snapshot date |

Only one relationship between `DimDate` and `FactReturns` can be active. The DAX file includes a cohort measure that switches from the active return-date relationship to the inactive original-order-date relationship. This follows Power BI's role-playing date dimension pattern. [Microsoft's star-schema guidance](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema/) describes active and inactive relationships for date roles; [relationship guidance](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-relationships-understand) explains one-to-many cardinality and filter direction.

Mark `DimDate[date_value]` as the model's date column after import. The export is a contiguous date range. This enables time-intelligence expressions such as `DATEADD`; Microsoft's [DATEADD reference](https://learn.microsoft.com/en-us/dax/dateadd-function-dax) notes that date-column inputs must form a contiguous interval for this behavior.

## KPI definitions

All sales KPIs below filter to completed orders. The fact table includes other cleaned statuses, so measures apply this rule instead of summing every row.

| KPI | Definition |
|---|---|
| Total Revenue | Sum of `FactSales[net_sales_amount]` for completed order lines, after discounts |
| Gross Sales | Sum of `FactSales[gross_line_amount]` for completed order lines, before discounts |
| Discount Amount / Rate | Completed-line discounts; discount amount divided by gross sales |
| Completed Orders | Distinct completed `order_id` count, not order-line count |
| Customers Purchasing | Distinct customer keys with completed sales in the current filter context |
| Average Order Value | Total Revenue divided by Completed Orders |
| Units Sold | Quantity on completed order lines |
| Revenue MoM Change / Growth | Current Total Revenue minus prior month revenue; growth divides the change by prior month revenue |
| Return Events / Units Returned / Refund Amount | Return-event counts, quantities, and refunds; the default date role is return date |
| Return Rate by Order Date | Units returned divided by units sold for the original order-date cohort |
| Inventory Value / Units on Hand | Snapshot measures. Interpret under one selected snapshot date; do not sum snapshots over time. |

The project models EUR from synthetic data and does not perform currency conversion, tax accounting, or payment settlement reconciliation. AOV is revenue per distinct completed order. Return rate by original order date is a cohort ratio; it can change as later returns are recorded and is not necessarily the same as a return-event rate for the current return month.

The formulas are in [`dashboards/powerbi/measures.dax`](../dashboards/powerbi/measures.dax). In Power BI Desktop, import each CSV using **Get data > Text/CSV**, verify the preview and column types, load, rename tables, add relationships, and create the measures. Set monetary columns to a currency/decimal type, key and count columns to whole numbers, `DimDate[date_value]` to Date, and labels/IDs to Text. Microsoft documents local CSV import in its [CSV data guidance](https://learn.microsoft.com/en-us/power-bi/connect-data/service-comma-separated-value-files).

## Report pages

The user has shared screenshots of these Power BI Desktop pages:

1. **Sales overview:** cards for Total Revenue, Completed Orders, Average Order Value, and Customers Purchasing; a monthly revenue line chart; revenue by category and store.
2. **Product and returns:** product/category revenue and units; Return Rate by Order Date; refunds and return events by return month/reason. Label which date role is being used.
3. **Inventory:** Inventory Value and Units on Hand with a single-select snapshot date slicer; category/store breakdown for that snapshot.

For portfolio evidence, save the completed report as a `.pbix` in a user-selected project location, inspect the relationships and measure formatting, then capture the actual report pages and model view. Keep the imported synthetic-data context visible in any published screenshots. Screenshots were shared during the build, but are not stored in this repository; the `.pbix` path has not been verified here.

## Current status and limits

| Capability | Status |
|---|---|
| Seven-file dimensional-model import interface | Implemented in the local SQL pipeline and covered by the Phase 14 pipeline integration test |
| Model relationship design and KPI definitions | Documented |
| DAX measures | Listed in `dashboards/powerbi/measures.dax`; user reports adding and formatting them in Power BI Desktop |
| Power BI Desktop report pages | User-built; screenshots shared in the project conversation |
| Local `.pbix` file | Present at `dashboards/powerbi/RetailPulse.pbix`; ignored by Git until its source paths are sanitized |
| Published semantic model | Not published |
