# Databricks notebook source
# MAGIC %md
# MAGIC # Ghana Medical Facilities - Data Ingestion
# MAGIC 
# MAGIC This notebook ingests and processes raw medical facility data for the Bridging Medical Deserts project.

# COMMAND ----------

# MAGIC %pip install databricks-vectorsearch sentence-transformers pandas

# COMMAND ----------

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, struct

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load Raw Data

# COMMAND ----------

# Read CSV data
df = spark.read.csv(
    "/FileStore/medical_deserts/ghana_facilities.csv",
    header=True,
    inferSchema=True
)

display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Data Quality Checks

# COMMAND ----------

# Check for nulls
print("Null counts:")
df.select([F.count(F.when(F.col(c).isNull(), c)).alias(c) for c in df.columns]).show()

# Check data types
df.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Save to Unity Catalog

# COMMAND ----------

# Save as Delta table
table_name = "main.medical_deserts.facilities_raw"

df.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable(table_name)

print(f"✅ Data saved to {table_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Basic Statistics

# COMMAND ----------

# Facility type distribution
display(df.groupBy("facility_type").count().orderBy("count", ascending=False))

# Regional distribution
display(df.groupBy("region").count())

# COMMAND ----------

print("✅ Data ingestion complete!")
