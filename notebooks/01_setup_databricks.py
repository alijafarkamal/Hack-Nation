# Databricks notebook source
# MAGIC %md
# MAGIC # Ghana Healthcare Facility Setup — Run Once
# MAGIC
# MAGIC This notebook handles all data work on Databricks:
# MAGIC 1. Upload + clean the CSV
# MAGIC 2. Add column descriptions for Genie
# MAGIC 3. Create Vector Search index
# MAGIC 4. Configure Genie Space (manual step in UI)
# MAGIC
# MAGIC **Ref:** See AGENT.md → Foundation — Databricks Setup (Notebook)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Upload + Clean Data
# MAGIC
# MAGIC Upload `Virtue_Foundation_Ghana_v0_3_-_Sheet1.csv` to a Volume first:
# MAGIC - Databricks UI → Catalog → your_catalog → your_schema → Volumes → Upload

# COMMAND ----------

from pyspark.sql import functions as F

# TODO: Update these to your actual catalog/schema
CATALOG = "your_catalog"
SCHEMA = "your_schema"
TABLE = f"{CATALOG}.{SCHEMA}.ghana_facilities"

# Read CSV from Volume
df = spark.read.csv(
    f"/Volumes/{CATALOG}/{SCHEMA}/data/Virtue_Foundation_Ghana_v0_3_-_Sheet1.csv",
    header=True,
    inferSchema=True,
)

print(f"Loaded {df.count()} rows")

# COMMAND ----------

# Fix "farmacy" typo (5 records)
df = df.withColumn(
    "facilityTypeId",
    F.when(F.col("facilityTypeId") == "farmacy", "pharmacy").otherwise(
        F.col("facilityTypeId")
    ),
)

# COMMAND ----------

# Normalize region names (53 variations → 16 official regions)
region_map = {
    "Greater Accra Region": "Greater Accra",
    "Accra": "Greater Accra",
    "GREATER ACCRA": "Greater Accra",
    "ASHANTI": "Ashanti",
    "Ashanti Region": "Ashanti",
    "Western Region": "Western",
    "Central Region": "Central",
    "Eastern Region": "Eastern",
    "Volta Region": "Volta",
    "Northern Region": "Northern",
    "Upper East Region": "Upper East",
    "Upper West Region": "Upper West",
    "Bono Region": "Bono",
    "Bono East Region": "Bono East",
    "Ahafo Region": "Ahafo",
    "Savannah Region": "Savannah",
    "North East Region": "North East",
    "Oti Region": "Oti",
    "Western North Region": "Western North",
    # Add more variations as you find them in the data
}

mapping_expr = F.create_map([F.lit(x) for kv in region_map.items() for x in kv])
df = df.withColumn(
    "region_normalized",
    F.coalesce(mapping_expr[F.col("address_stateOrRegion")], F.col("address_stateOrRegion")),
)

# COMMAND ----------

# Save as managed Delta table
df.write.format("delta").mode("overwrite").saveAsTable(TABLE)
print(f"Saved to {TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Add Column Descriptions (Critical for Genie)

# COMMAND ----------

spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN name COMMENT 'Official name of healthcare facility or NGO'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN `procedure` COMMENT 'JSON array of clinical procedures — surgeries, diagnostics, screenings'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN equipment COMMENT 'JSON array of medical devices — MRI, CT, X-ray, surgical tools'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN capability COMMENT 'JSON array of care levels — trauma levels, ICU, accreditations, staffing'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN specialties COMMENT 'JSON array of camelCase medical specialties e.g. cardiology, ophthalmology'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN facilityTypeId COMMENT 'Facility type: hospital, clinic, dentist, pharmacy, or doctor'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN address_stateOrRegion COMMENT 'Ghana region (raw, may need normalization)'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN region_normalized COMMENT 'Cleaned Ghana region name (one of 16 official regions)'")
spark.sql(f"ALTER TABLE {TABLE} ALTER COLUMN address_city COMMENT 'City or town where the facility is located'")

print("Column descriptions added")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Create Vector Search Index
# MAGIC
# MAGIC Ref: https://docs.databricks.com/en/generative-ai/vector-search.html

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create endpoint (one-time) — may take a few minutes
ENDPOINT_NAME = "ghana-medical-vs"
try:
    vsc.create_endpoint(name=ENDPOINT_NAME, endpoint_type="STANDARD")
    print(f"Created endpoint: {ENDPOINT_NAME}")
except Exception as e:
    print(f"Endpoint may already exist: {e}")

# COMMAND ----------

# Create auto-embedding index over free-form text columns
INDEX_NAME = f"{CATALOG}.{SCHEMA}.ghana_facilities_index"

vsc.create_delta_sync_index(
    endpoint_name=ENDPOINT_NAME,
    index_name=INDEX_NAME,
    source_table_name=TABLE,
    pipeline_type="TRIGGERED",
    primary_key="unique_id",  # TODO: verify this column name in the CSV
    embedding_source_columns=[
        {"name": "procedure", "model_endpoint_name": "databricks-gte-large-en"},
        {"name": "equipment", "model_endpoint_name": "databricks-gte-large-en"},
        {"name": "capability", "model_endpoint_name": "databricks-gte-large-en"},
    ],
    columns_to_sync=[
        "name", "facilityTypeId", "address_city",
        "region_normalized", "specialties", "description",
    ],
)

print(f"Created index: {INDEX_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Configure Genie Space (Manual)
# MAGIC
# MAGIC 1. Databricks UI → **Genie** → **Create Genie Space**
# MAGIC 2. Add table: `your_catalog.your_schema.ghana_facilities`
# MAGIC 3. Add custom instructions:
# MAGIC    ```
# MAGIC    This dataset contains 987 healthcare facilities and NGOs in Ghana.
# MAGIC    The procedure/equipment/capability columns are JSON arrays of English strings.
# MAGIC    The specialties column contains JSON arrays of camelCase strings like "cardiology".
# MAGIC    Use LIKE '%keyword%' to search within JSON array columns.
# MAGIC    The region_normalized column has clean Ghana region names.
# MAGIC    ```
# MAGIC 4. Add example SQL queries (see AGENT.md Step 4)
# MAGIC 5. Note the **Genie Space ID** → add to `.env` as `GENIE_SPACE_ID`

# COMMAND ----------

# MAGIC %md
# MAGIC ## Done!
# MAGIC
# MAGIC Update your `.env` with:
# MAGIC ```
# MAGIC DATABRICKS_CATALOG=your_catalog
# MAGIC DATABRICKS_SCHEMA=your_schema
# MAGIC GENIE_SPACE_ID=<from Genie Space UI>
# MAGIC VECTOR_SEARCH_INDEX=your_catalog.your_schema.ghana_facilities_index
# MAGIC VECTOR_SEARCH_ENDPOINT=ghana-medical-vs
# MAGIC ```
# MAGIC
# MAGIC Then run `pytest tests/test_config.py tests/test_tools.py -v` to verify connectivity.
