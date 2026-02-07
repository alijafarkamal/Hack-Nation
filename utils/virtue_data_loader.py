"""
Data loader for Virtue Foundation Ghana dataset.
Loads and processes real facility data for the medical desert analysis pipeline.
"""
import json
import ast
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import Config


class VirtueFoundationDataLoader:
    """Loads and processes the Virtue Foundation Ghana medical facility dataset."""
    
    def __init__(self):
        """Initialize the data loader."""
        self.config = Config()
        self.data_path = self.config.RAW_DATA_DIR / "facilities_real.csv"
        
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"❌ Virtue Foundation dataset not found: {self.data_path}\n"
                f"💡 Make sure 'facilities_real.csv' is in {self.config.RAW_DATA_DIR}"
            )
    
    def load_raw_data(self) -> pd.DataFrame:
        """
        Load the raw CSV data.
        
        Returns:
            DataFrame with raw facility data
        """
        print(f"📊 Loading Virtue Foundation Ghana dataset...")
        df = pd.read_csv(self.data_path, low_memory=False)
        print(f"✅ Loaded {len(df)} facilities from Ghana")
        return df
    
    def parse_json_column(self, value: Any) -> Any:
        """
        Safely parse JSON/list string columns.
        
        Args:
            value: Value to parse
            
        Returns:
            Parsed value or original if parsing fails
        """
        if pd.isna(value) or value == '[]' or value == '':
            return []
        
        if isinstance(value, (list, dict)):
            return value
        
        try:
            # Try parsing as JSON
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            try:
                # Try parsing as Python literal
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return []
    
    def convert_to_orchestrator_format(
        self, 
        df: pd.DataFrame,
        limit: Optional[int] = None,
        filter_region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert DataFrame to format expected by orchestrator.
        
        Args:
            df: Input DataFrame
            limit: Optional limit on number of facilities
            filter_region: Optional filter by region
            
        Returns:
            List of facilities in orchestrator format
        """
        # Filter by region if specified
        if filter_region:
            df = df[df['address_stateOrRegion'].str.contains(filter_region, case=False, na=False)]
            print(f"🔍 Filtered to {len(df)} facilities in {filter_region}")
        
        # Filter to only facilities (not NGOs)
        df = df[df['organization_type'] == 'facility']
        print(f"🏥 {len(df)} medical facilities (excluding NGOs)")
        
        # Limit if specified
        if limit:
            df = df.head(limit)
            print(f"📊 Limited to {limit} facilities for processing")
        
        facilities = []
        
        for idx, row in df.iterrows():
            # Parse JSON columns
            specialties = self.parse_json_column(row.get('specialties', []))
            procedures = self.parse_json_column(row.get('procedure', []))
            equipment = self.parse_json_column(row.get('equipment', []))
            capabilities = self.parse_json_column(row.get('capability', []))
            
            # Build raw text from available information
            raw_text_parts = []
            
            # Add description if available
            if pd.notna(row.get('description')):
                raw_text_parts.append(row['description'])
            
            # Add specialties
            if specialties:
                specialties_text = "Medical specialties: " + ", ".join(specialties)
                raw_text_parts.append(specialties_text)
            
            # Add capabilities
            if capabilities:
                capabilities_text = "Capabilities: " + "; ".join(capabilities)
                raw_text_parts.append(capabilities_text)
            
            # Add procedures
            if procedures:
                procedures_text = "Procedures available: " + "; ".join(procedures[:10])  # Limit to first 10
                raw_text_parts.append(procedures_text)
            
            # Add equipment
            if equipment:
                equipment_text = "Equipment: " + ", ".join(equipment[:10])  # Limit to first 10
                raw_text_parts.append(equipment_text)
            
            # Add facility info
            if pd.notna(row.get('facilityTypeId')):
                raw_text_parts.append(f"Facility type: {row['facilityTypeId']}")
            
            if pd.notna(row.get('numberDoctors')):
                raw_text_parts.append(f"Number of doctors: {int(row['numberDoctors'])}")
            
            if pd.notna(row.get('capacity')):
                raw_text_parts.append(f"Bed capacity: {int(row['capacity'])}")
            
            # Combine into raw text
            raw_text = ". ".join(raw_text_parts) if raw_text_parts else "No detailed information available"
            
            # Create coordinates (Ghana approximate center if not available)
            # Note: Real dataset doesn't have explicit lat/lon, using approximate Ghana locations
            # In production, you'd geocode the addresses
            city = row.get('address_city', '')
            region = row.get('address_stateOrRegion', '')
            
            # Default Ghana coordinates (will be overridden by geocoding in production)
            coordinates = self._approximate_coordinates(city, region)
            
            facility = {
                "facility_id": row.get('pk_unique_id', f"facility_{idx}"),
                "facility_name": row.get('name', 'Unknown Facility'),
                "raw_text": raw_text,
                "coordinates": coordinates,
                "metadata": {
                    "facility_type": row.get('facilityTypeId'),
                    "region": region,
                    "city": city,
                    "operator_type": row.get('operatorTypeId'),
                    "specialties": specialties,
                    "source_url": row.get('source_url'),
                    "number_doctors": row.get('numberDoctors'),
                    "capacity": row.get('capacity')
                }
            }
            
            facilities.append(facility)
        
        print(f"✅ Converted {len(facilities)} facilities to orchestrator format")
        return facilities
    
    def _approximate_coordinates(self, city: str, region: str) -> Dict[str, float]:
        """
        Approximate coordinates based on city/region.
        In production, use proper geocoding service.
        
        Args:
            city: City name
            region: Region name
            
        Returns:
            Dictionary with latitude and longitude
        """
        # Approximate coordinates for major Ghana regions
        region_coords = {
            "Greater Accra": {"latitude": 5.6037, "longitude": -0.1870},
            "Ashanti": {"latitude": 6.6885, "longitude": -1.6244},
            "Western": {"latitude": 5.1804, "longitude": -1.7511},
            "Eastern": {"latitude": 6.1870, "longitude": -0.6571},
            "Central": {"latitude": 5.4695, "longitude": -0.9969},
            "Volta": {"latitude": 6.5769, "longitude": 0.4502},
            "Northern": {"latitude": 9.5380, "longitude": -0.8502},
            "Upper East": {"latitude": 10.7085, "longitude": -0.9822},
            "Upper West": {"latitude": 10.3164, "longitude": -2.1097},
            "Brong-Ahafo": {"latitude": 7.6150, "longitude": -1.8125},
        }
        
        # Convert region to string if it's not
        region_str = str(region) if pd.notna(region) else ""
        
        # Try to match region
        for reg_name, coords in region_coords.items():
            if region_str and reg_name.lower() in region_str.lower():
                return coords
        
        # Default to Accra (capital)
        return {"latitude": 5.6037, "longitude": -0.1870}
    
    def get_region_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get statistics about facilities by region.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_facilities": len(df[df['organization_type'] == 'facility']),
            "total_ngos": len(df[df['organization_type'] == 'ngo']),
            "facilities_by_region": df[df['organization_type'] == 'facility']['address_stateOrRegion'].value_counts().to_dict(),
            "facilities_by_type": df['facilityTypeId'].value_counts().to_dict(),
            "with_specialties": len(df[df['specialties'].notna()]),
            "with_equipment": len(df[df['equipment'].notna()]),
            "with_capabilities": len(df[df['capability'].notna()]),
            "with_coordinates": 0  # Would need geocoding
        }
        
        return stats


def load_virtue_foundation_data(
    limit: Optional[int] = None,
    filter_region: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to load Virtue Foundation data.
    
    Args:
        limit: Optional limit on number of facilities
        filter_region: Optional filter by region (e.g., "Western", "Greater Accra")
        
    Returns:
        List of facilities in orchestrator format
    """
    loader = VirtueFoundationDataLoader()
    df = loader.load_raw_data()
    
    # Show statistics
    stats = loader.get_region_statistics(df)
    print(f"\n📊 Dataset Statistics:")
    print(f"   Total Facilities: {stats['total_facilities']}")
    print(f"   Total NGOs: {stats['total_ngos']}")
    print(f"   With Specialties: {stats['with_specialties']}")
    print(f"   With Equipment: {stats['with_equipment']}")
    print(f"   With Capabilities: {stats['with_capabilities']}")
    
    if stats['facilities_by_region']:
        print(f"\n📍 Top Regions:")
        for region, count in list(stats['facilities_by_region'].items())[:5]:
            print(f"   {region}: {count} facilities")
    
    # Convert to orchestrator format
    facilities = loader.convert_to_orchestrator_format(df, limit, filter_region)
    
    return facilities


if __name__ == "__main__":
    # Test the loader
    print("🧪 Testing Virtue Foundation Data Loader\n")
    
    facilities = load_virtue_foundation_data(limit=10)
    
    print(f"\n✅ Loaded {len(facilities)} facilities")
    print(f"\n📋 Sample Facility:")
    print(f"   ID: {facilities[0]['facility_id']}")
    print(f"   Name: {facilities[0]['facility_name']}")
    print(f"   Region: {facilities[0]['metadata']['region']}")
    print(f"   Type: {facilities[0]['metadata']['facility_type']}")
    print(f"   Raw Text Length: {len(facilities[0]['raw_text'])} chars")
