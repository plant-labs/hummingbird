# Databricks job stubs for Hummingbird medallion pipeline
# These notebooks/scripts are designed to run on Databricks; local pipelines mirror the logic.

# COMMAND ----------
# Bronze: land immutable news/social/official JSON

"""
from pyspark.sql import functions as F

bronze_path = "dbfs:/hummingbird/bronze/news/"
df = (
  spark.read.json("/dbfs/hummingbird/landing/news_*.jsonl")
  .withColumn("ingested_at", F.current_timestamp())
)
df.write.format("delta").mode("append").save(bronze_path)
"""

# COMMAND ----------
# Silver: extraction with source-span validation (call external LLM or pandas UDF)

"""
# Pseudo:
# 1. Read bronze CDF
# 2. For each body, call structured extraction with JSON schema ExtractionResult
# 3. DROP rows where any source_span is not a substring of body
# 4. Write silver Delta table hummingbird.silver.extracted_incidents
"""

# COMMAND ----------
# Gold: cluster + corroboration → candidates; sync to Postgres review_queue

"""
# Use Change Data Feed on gold candidates:
# spark.readStream.format("delta").option("readChangeFeed", "true").table("hummingbird.gold.candidates")
# foreachBatch → JDBC upsert into Postgres review_queue
"""
