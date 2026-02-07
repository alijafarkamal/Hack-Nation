"""
Quick Start Script: Run the complete medical desert analysis pipeline.
"""
import sys
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import MedicalDesertOrchestrator
from utils.virtue_data_loader import load_virtue_foundation_data
from config import Config


def load_sample_data():
    """Load Virtue Foundation Ghana medical facility data."""
    try:
        # Load real Virtue Foundation data
        # You can filter by region or limit the number of facilities
        facilities = load_virtue_foundation_data(
            limit=50,  # Process first 50 facilities for demo
            filter_region=None  # Set to "Western" or "Greater Accra" to filter
        )
        return facilities
    
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return []
    
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return []


def main():
    """Run the analysis pipeline."""
    print("🏥 BRIDGING MEDICAL DESERTS - Quick Start")
    print("=" * 60)
    
    # Validate configuration
    config = Config()
    
    print("\n📋 Configuration Check:")
    if not config.DATABRICKS_HOST or not config.DATABRICKS_TOKEN:
        print("⚠️  Databricks credentials not configured")
        print("💡 Set DATABRICKS_HOST and DATABRICKS_TOKEN in .env file")
        print("   (Agent will run in local mode without Databricks features)")
    else:
        print(f"✅ Databricks Host: {config.DATABRICKS_HOST[:30]}...")
        print(f"✅ Token configured")
    
    # Load Virtue Foundation data
    print("\n📊 Loading Virtue Foundation Ghana dataset...")
    facilities = load_sample_data()
    
    if not facilities:
        print("❌ No facility data available")
        return
    
    print(f"✅ Loaded {len(facilities)} facilities from Virtue Foundation dataset")
    
    # Create orchestrator
    print("\n🤖 Initializing agents...")
    orchestrator = MedicalDesertOrchestrator(llm=None)  # No LLM for demo
    print("✅ Orchestrator ready")
    
    # Run analysis
    print("\n" + "=" * 60)
    print("🚀 Starting Analysis Pipeline")
    print("=" * 60 + "\n")
    
    results = orchestrator.analyze_region(
        region="Western Region, Ghana",
        raw_facilities=facilities
    )
    
    # Display results
    print("\n" + "=" * 60)
    print("📊 ANALYSIS RESULTS")
    print("=" * 60)
    
    print(f"\n✅ Status: {results['status']}")
    print(f"📍 Region: {results['region']}")
    print(f"🕐 Timestamp: {results['timestamp']}")
    
    print(f"\n📈 Summary:")
    summary = results['summary']
    print(f"   Total Facilities: {summary['total_facilities']}")
    print(f"   Parsed Successfully: {summary['parsed_facilities']}")
    print(f"   Valid Facilities: {summary['valid_facilities']}")
    print(f"   Medical Deserts Identified: {summary['medical_deserts_identified']}")
    print(f"   Errors: {summary['errors']}")
    
    # Show medical deserts
    if results['medical_deserts']:
        print(f"\n🏜️  MEDICAL DESERTS IDENTIFIED:")
        print(f"   {'='*56}")
        
        for i, desert in enumerate(results['medical_deserts'][:5], 1):
            print(f"\n   {i}. {desert['desert_id']}")
            print(f"      Severity: {desert['severity_score']:.2f} / 1.00")
            print(f"      Distance to nearest critical care: {desert['distance_to_nearest_km']:.1f} km")
            print(f"      Missing capabilities: {', '.join(desert['missing_capabilities'])}")
            print(f"      Location: ({desert['center_point']['latitude']:.4f}, {desert['center_point']['longitude']:.4f})")
    
    # Show validation issues
    if results['validation_issues']:
        print(f"\n⚠️  VALIDATION ISSUES:")
        for issue in results['validation_issues'][:3]:
            print(f"   - {issue['facility_name']}:")
            for problem in issue['issues']:
                print(f"     • {problem}")
    
    print(f"\n" + "=" * 60)
    print(f"✅ Analysis Complete!")
    print(f"💡 MLflow Run ID: {results['run_id']}")
    print(f"=" * 60 + "\n")
    
    # Save results
    output_path = config.PROCESSED_DATA_DIR / f"analysis_results_{results['run_id'][:8]}.json"
    
    import json
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"💾 Results saved to: {output_path}\n")


if __name__ == "__main__":
    main()
