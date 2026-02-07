"""
Unity Catalog integration for data governance and management.
Handles catalog/schema creation and table management.
"""
from typing import Dict, Any, Optional, List
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import CatalogInfo, SchemaInfo
from config import Config


class UnityCatalogManager:
    """Manages Unity Catalog resources for medical desert project."""
    
    def __init__(self):
        """Initialize Unity Catalog client."""
        self.config = Config()
        
        self.client = WorkspaceClient(
            host=self.config.DATABRICKS_HOST,
            token=self.config.DATABRICKS_TOKEN
        )
        
        self.catalog_name = self.config.UNITY_CATALOG_NAME
        self.schema_name = self.config.UNITY_SCHEMA_NAME
    
    def setup_catalog_schema(self) -> None:
        """Create catalog and schema if they don't exist."""
        try:
            # Check/create catalog
            try:
                self.client.catalogs.get(self.catalog_name)
                print(f"✅ Catalog exists: {self.catalog_name}")
            except Exception:
                print(f"🔧 Creating catalog: {self.catalog_name}")
                self.client.catalogs.create(
                    name=self.catalog_name,
                    comment="Medical Desert Analysis Project"
                )
            
            # Check/create schema
            try:
                self.client.schemas.get(f"{self.catalog_name}.{self.schema_name}")
                print(f"✅ Schema exists: {self.schema_name}")
            except Exception:
                print(f"🔧 Creating schema: {self.schema_name}")
                self.client.schemas.create(
                    name=self.schema_name,
                    catalog_name=self.catalog_name,
                    comment="Medical facility data and embeddings"
                )
            
            print(f"✅ Unity Catalog setup complete")
            
        except Exception as e:
            print(f"⚠️  Unity Catalog setup error: {e}")
            print(f"💡 Make sure you have Unity Catalog access in Databricks")
    
    def create_facilities_table_ddl(self) -> str:
        """
        Generate DDL for facilities table.
        
        Returns:
            SQL CREATE TABLE statement
        """
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.catalog_name}.{self.schema_name}.facilities (
            facility_id STRING NOT NULL,
            name STRING,
            region STRING,
            district STRING,
            facility_type STRING,
            capabilities_raw STRING,
            equipment ARRAY<STRING>,
            staff_count MAP<STRING, INT>,
            coordinates STRUCT<latitude: DOUBLE, longitude: DOUBLE>,
            capability_embedding ARRAY<FLOAT>,
            last_updated TIMESTAMP,
            source_document STRING,
            extraction_confidence FLOAT,
            CONSTRAINT facilities_pk PRIMARY KEY (facility_id)
        )
        USING DELTA
        COMMENT 'Medical facilities with extracted capabilities and embeddings'
        TBLPROPERTIES (
            'delta.enableChangeDataFeed' = 'true',
            'delta.columnMapping.mode' = 'name'
        );
        """
        return ddl
    
    def create_medical_deserts_table_ddl(self) -> str:
        """
        Generate DDL for medical deserts analysis results table.
        
        Returns:
            SQL CREATE TABLE statement
        """
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.catalog_name}.{self.schema_name}.medical_deserts (
            desert_id STRING NOT NULL,
            region STRING,
            center_point STRUCT<latitude: DOUBLE, longitude: DOUBLE>,
            radius_km FLOAT,
            missing_capabilities ARRAY<STRING>,
            affected_population INT,
            nearest_facility_id STRING,
            distance_to_nearest_km FLOAT,
            analysis_timestamp TIMESTAMP,
            agent_run_id STRING,
            CONSTRAINT deserts_pk PRIMARY KEY (desert_id)
        )
        USING DELTA
        COMMENT 'Identified medical desert regions'
        TBLPROPERTIES (
            'delta.enableChangeDataFeed' = 'true'
        );
        """
        return ddl
    
    def create_agent_traces_table_ddl(self) -> str:
        """
        Generate DDL for agent reasoning traces.
        
        Returns:
            SQL CREATE TABLE statement
        """
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.catalog_name}.{self.schema_name}.agent_traces (
            trace_id STRING NOT NULL,
            agent_name STRING,
            step_name STRING,
            reasoning TEXT,
            citations ARRAY<STRING>,
            confidence FLOAT,
            input_data MAP<STRING, STRING>,
            output_data MAP<STRING, STRING>,
            execution_time_ms BIGINT,
            timestamp TIMESTAMP,
            mlflow_run_id STRING,
            CONSTRAINT traces_pk PRIMARY KEY (trace_id)
        )
        USING DELTA
        COMMENT 'Agent reasoning traces for audit trail'
        TBLPROPERTIES (
            'delta.enableChangeDataFeed' = 'true'
        );
        """
        return ddl
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        Get information about a table.
        
        Args:
            table_name: Name of the table (e.g., "facilities")
            
        Returns:
            Table metadata
        """
        full_name = f"{self.catalog_name}.{self.schema_name}.{table_name}"
        
        try:
            table = self.client.tables.get(full_name)
            return {
                "name": table.name,
                "catalog": table.catalog_name,
                "schema": table.schema_name,
                "type": table.table_type,
                "comment": table.comment,
                "storage_location": table.storage_location,
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type_name,
                        "comment": col.comment
                    }
                    for col in (table.columns or [])
                ]
            }
        except Exception as e:
            print(f"⚠️  Error getting table info: {e}")
            return {}
    
    def generate_setup_sql_file(self, output_path: str = "setup_unity_catalog.sql") -> str:
        """
        Generate a complete SQL file for Unity Catalog setup.
        
        Args:
            output_path: Path to save SQL file
            
        Returns:
            Path to generated file
        """
        sql_content = f"""-- Unity Catalog Setup for Bridging Medical Deserts
-- Generated automatically - Review before executing

-- 1. Create Catalog
CREATE CATALOG IF NOT EXISTS {self.catalog_name}
COMMENT 'Medical Desert Analysis Project';

-- 2. Create Schema
CREATE SCHEMA IF NOT EXISTS {self.catalog_name}.{self.schema_name}
COMMENT 'Medical facility data and embeddings';

-- 3. Facilities Table
{self.create_facilities_table_ddl()}

-- 4. Medical Deserts Table
{self.create_medical_deserts_table_ddl()}

-- 5. Agent Traces Table
{self.create_agent_traces_table_ddl()}

-- 6. Create Views
CREATE OR REPLACE VIEW {self.catalog_name}.{self.schema_name}.facilities_summary AS
SELECT 
    region,
    COUNT(*) as facility_count,
    COUNT(DISTINCT facility_type) as facility_types,
    AVG(extraction_confidence) as avg_confidence
FROM {self.catalog_name}.{self.schema_name}.facilities
GROUP BY region;

-- 7. Grant permissions (adjust as needed)
-- GRANT USE CATALOG ON CATALOG {self.catalog_name} TO `data_analysts`;
-- GRANT SELECT ON TABLE {self.catalog_name}.{self.schema_name}.facilities TO `data_analysts`;

SELECT 'Unity Catalog setup complete!' as status;
"""
        
        full_path = self.config.PROJECT_ROOT / output_path
        with open(full_path, 'w') as f:
            f.write(sql_content)
        
        print(f"📄 SQL setup file generated: {full_path}")
        return str(full_path)


if __name__ == "__main__":
    # Quick test
    uc_manager = UnityCatalogManager()
    
    print("\n📋 Generated DDL Statements:")
    print("\n--- Facilities Table ---")
    print(uc_manager.create_facilities_table_ddl())
    
    print("\n✅ Unity Catalog manager initialized successfully")
