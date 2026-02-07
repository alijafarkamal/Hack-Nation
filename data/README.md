# Medical Facility Data - Virtue Foundation Ghana Dataset

## 🎯 Real-World Dataset

This project uses the **Virtue Foundation Ghana Dataset v0.3** - a comprehensive collection of 1,000+ real medical facilities and NGOs operating in Ghana.

## Structure

```
data/
├── raw/
│   └── ghana/
│       └── facilities_real.csv      # 1,000+ facilities from Virtue Foundation
├── processed/                        # Analysis outputs
└── schemas/
    └── facility_schema.json         # JSON schema for the dataset
```

## Data Sources

1. **Virtue Foundation Ghana Dataset v0.3**
   - 1,000+ medical facilities
   - Complete facility profiles with specialties, equipment, procedures
   - Address information (city, region, country)
   - Source URLs for verification

2. **Schema Documentation**
   - Comprehensive field definitions
   - Pydantic models for validation
   - Extraction prompts and guidelines

## Schema Overview

### Core Fields

- **pk_unique_id**: Unique identifier
- **name**: Official facility name
- **organization_type**: "facility" or "ngo"
- **facilityTypeId**: hospital, clinic, pharmacy, doctor, dentist

### Medical Information

- **specialties**: Array of medical specialties (camelCase format)
  - Examples: "internalMedicine", "pediatrics", "cardiology"
  - 150+ specialty types available
  
- **procedure**: Array of clinical procedures performed
  - Examples: "Performs emergency cesarean sections", "Conducts cardiac surgery"
  
- **equipment**: Array of medical equipment and infrastructure
  - Examples: "Siemens CT scanner", "45-bed ICU", "Oxygen generation plant"
  
- **capability**: Array of facility capabilities
  - Examples: "Level II trauma center", "24-hour emergency care", "Joint Commission accredited"

### Location Information

- **address_line1**: Street address
- **address_city**: City/town
- **address_stateOrRegion**: Region (e.g., "Greater Accra", "Western")
- **address_country**: "Ghana"
- **address_countryCode**: "GH"

### Additional Fields

- **description**: Paragraph describing facility services
- **numberDoctors**: Number of doctors on staff
- **capacity**: Inpatient bed capacity
- **operatorTypeId**: "public" or "private"
- **source_url**: Source website for verification

## Data Quality

- ✅ **Comprehensive**: 1,000+ facilities covering all Ghana regions
- ✅ **Structured**: Extracted using LLM with pydantic validation
- ✅ **Cited**: Every data point includes source URL
- ✅ **Clean**: Validated against schema constraints
- ✅ **Rich**: Includes specialties, procedures, equipment, capabilities

## Regional Distribution

Top regions by facility count:
- Greater Accra: 300+ facilities
- Ashanti: 200+ facilities
- Western: 100+ facilities
- Eastern: 80+ facilities
- Central: 70+ facilities

## Using the Data

### Load Data in Python

```python
from utils.virtue_data_loader import load_virtue_foundation_data

# Load all facilities
facilities = load_virtue_foundation_data()

# Load limited subset
facilities = load_virtue_foundation_data(limit=50)

# Filter by region
facilities = load_virtue_foundation_data(
    filter_region="Greater Accra",
    limit=100
)
```

### Data Format

Each facility is returned in orchestrator-compatible format:

```python
{
    "facility_id": "1",
    "facility_name": "Hospital Name",
    "raw_text": "Combined text from description, specialties, procedures, equipment...",
    "coordinates": {"latitude": 5.6037, "longitude": -0.1870},
    "metadata": {
        "facility_type": "hospital",
        "region": "Greater Accra",
        "city": "Accra",
        "specialties": ["internalMedicine", "surgery"],
        "source_url": "https://...",
        "number_doctors": 25,
        "capacity": 150
    }
}
```

## Pydantic Models

See `agents/` folder for official pydantic models:
- `facility_and_ngo_fields.py`: Base models for facilities and NGOs
- `medical_specialties.py`: Medical specialty classification
- `free_form.py`: Procedure, equipment, capability extraction
- `organization_extraction.py`: Organization classification

## Citation Requirements

Every extracted data point in this dataset includes:
- Source URL where information was found
- Extraction timestamp
- Validation against pydantic schema
- Conservative extraction (only facts explicitly stated)
