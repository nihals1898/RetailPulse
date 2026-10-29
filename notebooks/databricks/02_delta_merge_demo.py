# Databricks notebook source
# ruff: noqa: E501, F821
# MAGIC %md
# MAGIC # RetailPulse — Delta Lake merge demo
# MAGIC
# MAGIC A small, repeatable Databricks example of a managed Delta table, conditional upsert, operation history, and time travel. It uses only synthetic inline rows. The first run creates two starting products; the merge batch contains one unchanged row, one changed row, and one new row.

# COMMAND ----------

from decimal import Decimal

from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql import types as T

dbutils.widgets.text("catalog", "main", "Unity Catalog catalog")
dbutils.widgets.text("schema", "retailpulse_demo", "Unity Catalog schema")
catalog = dbutils.widgets.get("catalog").strip()
schema = dbutils.widgets.get("schema").strip()
demo_table = "phase10_product_merge_demo"


def sql_identifier(value: str) -> str:
    if not value or not value.replace("_", "").isalnum():
        raise ValueError("Catalog and schema names may contain only letters, digits, and underscores.")
    return f"`{value}`"


catalog_sql = sql_identifier(catalog)
schema_sql = sql_identifier(schema)
table_sql = f"{catalog_sql}.{schema_sql}.{sql_identifier(demo_table)}"
table_name = f"{catalog}.{schema}.{demo_table}"

print(f"Target Delta table: {table_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create the initial Delta snapshot
# MAGIC
# MAGIC The `saveAsTable` call writes a managed Delta table in Unity Catalog. The table is initialized only if it does not exist; reruns reuse its current snapshot so the merge remains idempotent.

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog_sql}.{schema_sql}")

product_schema = T.StructType(
    [
        T.StructField("product_id", T.StringType(), False),
        T.StructField("product_name", T.StringType(), False),
        T.StructField("list_price", T.DecimalType(10, 2), False),
        T.StructField("source_updated_at", T.StringType(), False),
    ]
)

base_rows = [
    ("DEMO-P001", "RetailPulse Demo Product A", Decimal("19.99"), "2026-01-01T00:00:00Z"),
    ("DEMO-P002", "RetailPulse Demo Product B", Decimal("29.99"), "2026-01-01T00:00:00Z"),
]

if not spark.catalog.tableExists(table_name):
    (
        spark.createDataFrame(base_rows, schema=product_schema)
        .write.format("delta")
        .mode("errorifexists")
        .saveAsTable(table_name)
    )

delta_table = DeltaTable.forName(spark, table_name)
pre_merge_version = delta_table.history(1).select("version").first()["version"]
pre_merge = {row["product_id"]: row for row in spark.table(table_name).collect()}
print(f"Pre-merge version: {pre_merge_version}; rows: {len(pre_merge)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Merge changes
# MAGIC
# MAGIC The source contains an unchanged match, an update, and a new row. The matched-update predicate skips the unchanged record. `MERGE` commits the resulting changes as one new Delta table version.

# COMMAND ----------

unchanged_row = pre_merge["DEMO-P001"]
changed_price = Decimal("31.24")
merge_rows = [
    (
        "DEMO-P001",
        unchanged_row["product_name"],
        unchanged_row["list_price"],
        unchanged_row["source_updated_at"],
    ),
    ("DEMO-P002", "RetailPulse Demo Product B", changed_price, "2026-01-15T00:00:00Z"),
    ("DEMO-P003", "RetailPulse Demo Product C", Decimal("24.99"), "2026-01-15T00:00:00Z"),
]
source_df = spark.createDataFrame(merge_rows, schema=product_schema)

(
    delta_table.alias("target")
    .merge(source_df.alias("source"), "target.product_id = source.product_id")
    .whenMatchedUpdate(
        condition=(
            "source.list_price <> target.list_price "
            "OR source.source_updated_at > target.source_updated_at"
        ),
        set={
            "product_name": "source.product_name",
            "list_price": "source.list_price",
            "source_updated_at": "source.source_updated_at",
        },
    )
    .whenNotMatchedInsertAll()
    .execute()
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify the current and previous snapshots

# COMMAND ----------

current = {row["product_id"]: row for row in spark.table(table_name).collect()}
history = DeltaTable.forName(spark, table_name).history(2)
latest_operation = history.orderBy(F.desc("version")).first()
historical = spark.sql(f"SELECT * FROM {table_sql} VERSION AS OF {pre_merge_version}")
historical_rows = {row["product_id"]: row for row in historical.collect()}

assert len(current) == len(pre_merge) + (0 if "DEMO-P003" in pre_merge else 1)
assert current["DEMO-P002"]["list_price"] == changed_price
assert current["DEMO-P001"]["list_price"] == pre_merge["DEMO-P001"]["list_price"]
assert current["DEMO-P003"]["list_price"] == Decimal("24.99")
assert historical_rows["DEMO-P002"]["list_price"] == pre_merge["DEMO-P002"]["list_price"]

display(history.select("version", "timestamp", "operation", "operationMetrics"))
display(spark.table(table_name).orderBy("product_id"))
print("Current version:", latest_operation["version"])
print("All merge and time-travel checks passed.")
