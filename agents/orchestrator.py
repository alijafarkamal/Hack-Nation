"""
Orchestrator: LangGraph-based coordination of parser, verification, and mapper agents.
Implements the complete medical desert analysis pipeline.
"""
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime
import operator
from langgraph.graph import StateGraph, END
from agents.parser_agent import ParserAgent, FacilityCapabilities
from agents.verification_agent import VerificationAgent, ValidationResult
from agents.mapper_agent import MapperAgent, FacilityWithLocation, MedicalDesert, Coordinate
from utils.mlflow_tracing import MLflowTracing
from config import Config


class OrchestratorState(TypedDict):
    """State passed between agents in the workflow."""
    
    # Input
    region: str
    raw_facilities: List[Dict[str, Any]]  # facility_id, name, raw_text, coordinates
    
    # Parser output
    parsed_capabilities: Annotated[List[FacilityCapabilities], operator.add]
    
    # Verification output
    validation_results: Annotated[List[ValidationResult], operator.add]
    
    # Mapper output
    medical_deserts: List[MedicalDesert]
    
    # Metadata
    run_id: str
    status: str
    errors: Annotated[List[str], operator.add]


class MedicalDesertOrchestrator:
    """
    Main orchestrator for medical desert analysis pipeline.
    Uses LangGraph to coordinate multiple agents.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the orchestrator and all agents.
        
        Args:
            llm: Optional LangChain LLM for parser agent
        """
        self.config = Config()
        self.tracing = MLflowTracing()
        
        # Initialize agents
        self.parser = ParserAgent(llm=llm)
        self.verifier = VerificationAgent()
        self.mapper = MapperAgent()
        
        # Build LangGraph workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow.
        
        Returns:
            Compiled workflow graph
        """
        # Create the graph
        workflow = StateGraph(OrchestratorState)
        
        # Add nodes for each agent
        workflow.add_node("parse", self._parse_node)
        workflow.add_node("verify", self._verify_node)
        workflow.add_node("map", self._map_node)
        
        # Define the flow
        workflow.set_entry_point("parse")
        workflow.add_edge("parse", "verify")
        workflow.add_edge("verify", "map")
        workflow.add_edge("map", END)
        
        # Compile the graph
        return workflow.compile()
    
    def _parse_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node for parsing capabilities from raw text.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with parsed capabilities
        """
        print(f"\n🔄 Step 1/3: Parsing {len(state['raw_facilities'])} facilities...")
        
        parsed_capabilities = []
        errors = []
        
        for facility in state['raw_facilities']:
            try:
                result = self.parser.parse_facility_text(
                    facility_id=facility.get('facility_id', 'unknown'),
                    facility_name=facility.get('facility_name', 'Unknown'),
                    raw_text=facility.get('raw_text', ''),
                    trace_run=False
                )
                parsed_capabilities.append(result)
            
            except Exception as e:
                error_msg = f"Parse error for {facility.get('facility_id')}: {e}"
                print(f"  ❌ {error_msg}")
                errors.append(error_msg)
        
        print(f"✅ Parsed {len(parsed_capabilities)} facilities")
        
        return {
            "parsed_capabilities": parsed_capabilities,
            "errors": errors
        }
    
    def _verify_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node for verifying parsed capabilities.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with validation results
        """
        print(f"\n🔍 Step 2/3: Verifying {len(state['parsed_capabilities'])} facilities...")
        
        validation_results = []
        errors = []
        
        for capabilities in state['parsed_capabilities']:
            try:
                result = self.verifier.verify_capabilities(
                    capabilities,
                    trace_run=False
                )
                validation_results.append(result)
                
                if not result.is_valid:
                    print(f"  ⚠️  {capabilities.facility_name}: {len(result.issues)} issues")
            
            except Exception as e:
                error_msg = f"Verification error for {capabilities.facility_id}: {e}"
                print(f"  ❌ {error_msg}")
                errors.append(error_msg)
        
        valid_count = sum(1 for r in validation_results if r.is_valid)
        print(f"✅ Verified {len(validation_results)} facilities ({valid_count} valid)")
        
        return {
            "validation_results": validation_results,
            "errors": errors
        }
    
    def _map_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node for identifying medical deserts.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with medical desert identification
        """
        print(f"\n🗺️  Step 3/3: Mapping medical deserts in {state['region']}...")
        
        # Convert parsed capabilities to facilities with locations
        facilities_with_locations = []
        
        for i, (capability, facility_data) in enumerate(
            zip(state['parsed_capabilities'], state['raw_facilities'])
        ):
            # Extract coordinates
            coords = facility_data.get('coordinates', {})
            
            if coords:
                # Determine if facility is critical
                capability_types = [cap.capability_type for cap in capability.capabilities]
                is_critical = any(
                    crit_type in capability_types 
                    for crit_type in self.mapper.critical_capabilities
                )
                
                facility_with_loc = FacilityWithLocation(
                    facility_id=capability.facility_id,
                    facility_name=capability.facility_name,
                    coordinates=Coordinate(**coords),
                    capabilities=capability_types,
                    is_critical=is_critical
                )
                
                facilities_with_locations.append(facility_with_loc)
        
        # Identify medical deserts
        medical_deserts = []
        errors = []
        
        try:
            medical_deserts = self.mapper.identify_medical_deserts(
                facilities=facilities_with_locations,
                region=state['region'],
                trace_run=False
            )
            
            print(f"✅ Identified {len(medical_deserts)} medical deserts")
            
            if medical_deserts:
                print(f"\n📊 Top 3 Medical Deserts by Severity:")
                for i, desert in enumerate(medical_deserts[:3]):
                    print(f"   {i+1}. {desert.desert_id}")
                    print(f"      Severity: {desert.severity_score:.2f}")
                    print(f"      Distance to nearest: {desert.distance_to_nearest_km:.1f} km")
                    print(f"      Missing: {', '.join(desert.missing_capabilities)}")
        
        except Exception as e:
            error_msg = f"Mapping error: {e}"
            print(f"  ❌ {error_msg}")
            errors.append(error_msg)
        
        return {
            "medical_deserts": medical_deserts,
            "errors": errors,
            "status": "success" if not errors else "completed_with_errors"
        }
    
    def analyze_region(
        self,
        region: str,
        raw_facilities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run the complete analysis pipeline for a region.
        
        Args:
            region: Region name (e.g., "Western Region, Ghana")
            raw_facilities: List of facilities with raw_text and coordinates
            
        Returns:
            Complete analysis results
        """
        # Start MLflow run
        run_id = self.tracing.start_agent_run(
            "medical_desert_orchestrator",
            {
                "region": region,
                "facility_count": len(raw_facilities)
            }
        )
        
        print(f"\n{'='*60}")
        print(f"🏥 BRIDGING MEDICAL DESERTS - Analysis Pipeline")
        print(f"{'='*60}")
        print(f"Region: {region}")
        print(f"Facilities: {len(raw_facilities)}")
        print(f"Run ID: {run_id}")
        print(f"{'='*60}")
        
        # Initialize state
        initial_state = OrchestratorState(
            region=region,
            raw_facilities=raw_facilities,
            parsed_capabilities=[],
            validation_results=[],
            medical_deserts=[],
            run_id=run_id,
            status="running",
            errors=[]
        )
        
        # Run the workflow
        try:
            final_state = self.workflow.invoke(initial_state)
            
            # Log final results to MLflow
            self.tracing.log_medical_desert_detection(
                region=region,
                deserts=[d.dict() for d in final_state['medical_deserts']],
                analysis={
                    "facility_count": len(raw_facilities),
                    "parsed_count": len(final_state['parsed_capabilities']),
                    "valid_count": sum(
                        1 for v in final_state['validation_results'] if v.is_valid
                    ),
                    "desert_count": len(final_state['medical_deserts']),
                    "errors": final_state['errors']
                }
            )
            
            self.tracing.end_agent_run(
                status=final_state['status'],
                output_data={
                    "desert_count": len(final_state['medical_deserts']),
                    "region": region
                }
            )
            
            print(f"\n{'='*60}")
            print(f"✅ Analysis Complete")
            print(f"{'='*60}")
            
            return self._format_results(final_state)
        
        except Exception as e:
            error_msg = f"Orchestrator error: {e}"
            print(f"\n❌ {error_msg}")
            
            self.tracing.end_agent_run("failed", {"error": error_msg})
            
            return {
                "status": "failed",
                "error": error_msg,
                "region": region
            }
    
    def _format_results(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Format final results for output.
        
        Args:
            state: Final workflow state
            
        Returns:
            Formatted results dictionary
        """
        return {
            "status": state['status'],
            "region": state['region'],
            "run_id": state['run_id'],
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_facilities": len(state['raw_facilities']),
                "parsed_facilities": len(state['parsed_capabilities']),
                "valid_facilities": sum(
                    1 for v in state['validation_results'] if v.is_valid
                ),
                "medical_deserts_identified": len(state['medical_deserts']),
                "errors": len(state['errors'])
            },
            "medical_deserts": [d.dict() for d in state['medical_deserts']],
            "validation_issues": [
                {
                    "facility_id": cap.facility_id,
                    "facility_name": cap.facility_name,
                    "is_valid": val.is_valid,
                    "issues": val.issues,
                    "warnings": val.warnings
                }
                for cap, val in zip(
                    state['parsed_capabilities'],
                    state['validation_results']
                )
                if not val.is_valid
            ],
            "errors": state['errors']
        }


if __name__ == "__main__":
    # Quick test with sample data
    orchestrator = MedicalDesertOrchestrator()
    
    # Sample test data
    test_facilities = [
        {
            "facility_id": "GH-WR-001",
            "facility_name": "Effia-Nkwanta Regional Hospital",
            "raw_text": "Regional referral hospital with 24-hour emergency services, CT scanner, MRI, and 8 surgeons on staff. Provides intensive care and has blood bank.",
            "coordinates": {"latitude": 4.9, "longitude": -1.75}
        },
        {
            "facility_id": "GH-WR-002",
            "facility_name": "Aiyinase Health Center",
            "raw_text": "Basic health services, outpatient care, limited pharmacy. No emergency services. 2 nurses, 1 physician assistant.",
            "coordinates": {"latitude": 5.2, "longitude": -2.1}
        }
    ]
    
    print("\n🧪 Running test analysis...")
    results = orchestrator.analyze_region("Western Region, Ghana", test_facilities)
    
    print(f"\n📊 Results Summary:")
    print(f"   Status: {results['status']}")
    print(f"   Medical Deserts: {results['summary']['medical_deserts_identified']}")
