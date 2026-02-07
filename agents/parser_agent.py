"""
Parser Agent: Extracts structured capabilities from unstructured medical text.
Uses Databricks Foundation Models (DBRX) for intelligent parsing.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import BaseOutputParser
except ImportError:
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import BaseOutputParser
from pydantic import BaseModel, Field
from utils.mlflow_tracing import MLflowTracing


class MedicalCapability(BaseModel):
    """Structured representation of a medical facility capability."""
    
    capability_type: str = Field(description="Type of capability (emergency, imaging, surgery, etc.)")
    details: str = Field(description="Specific details about the capability")
    equipment: List[str] = Field(default_factory=list, description="Required equipment")
    staff_required: Dict[str, int] = Field(default_factory=dict, description="Staff requirements")
    availability: str = Field(default="unknown", description="Availability (24/7, business_hours, on_call)")
    confidence: float = Field(default=0.0, description="Extraction confidence (0-1)")
    citation: str = Field(description="Source text citation")


class FacilityCapabilities(BaseModel):
    """Complete capability profile for a medical facility."""
    
    facility_id: str
    facility_name: str
    capabilities: List[MedicalCapability]
    raw_text: str
    extraction_timestamp: str
    overall_confidence: float


class CapabilityOutputParser(BaseOutputParser[FacilityCapabilities]):
    """Custom parser for capability extraction output."""
    
    def parse(self, text: str) -> FacilityCapabilities:
        """Parse LLM output into structured capabilities."""
        try:
            # Try to parse as JSON
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
            else:
                json_str = text.strip()
            
            data = json.loads(json_str)
            return FacilityCapabilities(**data)
        
        except Exception as e:
            # Fallback: return minimal structure
            print(f"⚠️  Parsing error: {e}")
            return FacilityCapabilities(
                facility_id="unknown",
                facility_name="unknown",
                capabilities=[],
                raw_text=text,
                extraction_timestamp=datetime.now().isoformat(),
                overall_confidence=0.0
            )


class ParserAgent:
    """Agent responsible for parsing unstructured medical facility text."""
    
    def __init__(self, llm=None):
        """
        Initialize the Parser Agent.
        
        Args:
            llm: LangChain LLM instance (will use Databricks if provided)
        """
        self.llm = llm
        self.tracing = MLflowTracing()
        self.parser = CapabilityOutputParser()
        
        # Define extraction prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a medical capability extraction expert. 
            Your job is to analyze unstructured text about medical facilities and extract:
            
            1. **Medical Capabilities**: Services offered (emergency care, surgery, imaging, etc.)
            2. **Equipment**: Medical devices and technology available
            3. **Staff**: Types and counts of medical professionals
            4. **Availability**: When services are available (24/7, business hours, etc.)
            
            Extract ALL capabilities mentioned, even if incomplete. For each capability:
            - Classify the type (emergency, imaging, surgery, laboratory, pharmacy, etc.)
            - Extract specific details
            - List any mentioned equipment
            - Note staff requirements if mentioned
            - Estimate availability if mentioned
            - Assign confidence score (0-1) based on clarity of information
            - Provide exact text citation
            
            Return results as JSON following this schema:
            {{
                "facility_id": "string",
                "facility_name": "string",
                "capabilities": [
                    {{
                        "capability_type": "string",
                        "details": "string",
                        "equipment": ["string"],
                        "staff_required": {{"role": count}},
                        "availability": "string",
                        "confidence": 0.95,
                        "citation": "exact text from source"
                    }}
                ],
                "raw_text": "original input",
                "extraction_timestamp": "ISO8601",
                "overall_confidence": 0.85
            }}
            
            Be thorough but conservative in confidence scoring."""),
            ("user", """Extract capabilities from this medical facility description:
            
            Facility ID: {facility_id}
            Facility Name: {facility_name}
            
            Description:
            {raw_text}
            
            Extract all capabilities in JSON format.""")
        ])
    
    def parse_facility_text(
        self, 
        facility_id: str,
        facility_name: str,
        raw_text: str,
        trace_run: bool = True
    ) -> FacilityCapabilities:
        """
        Parse unstructured facility description into structured capabilities.
        
        Args:
            facility_id: Unique facility identifier
            facility_name: Name of the facility
            raw_text: Unstructured text description
            trace_run: Whether to log to MLflow
            
        Returns:
            Structured facility capabilities
        """
        if trace_run:
            self.tracing.start_agent_run(
                "parser_agent",
                {
                    "facility_id": facility_id,
                    "facility_name": facility_name,
                    "input_length": len(raw_text)
                }
            )
        
        try:
            # Format prompt
            messages = self.prompt.format_messages(
                facility_id=facility_id,
                facility_name=facility_name,
                raw_text=raw_text
            )
            
            # If LLM is available, use it
            if self.llm:
                response = self.llm.invoke(messages)
                result_text = response.content if hasattr(response, 'content') else str(response)
            else:
                # Fallback: basic rule-based extraction
                result_text = self._fallback_extraction(facility_id, facility_name, raw_text)
            
            # Parse response
            capabilities = self.parser.parse(result_text)
            
            # Log to MLflow
            if trace_run:
                self.tracing.log_reasoning_step(
                    step_name="capability_extraction",
                    reasoning=f"Extracted {len(capabilities.capabilities)} capabilities from facility description",
                    citations=[cap.citation for cap in capabilities.capabilities],
                    confidence=capabilities.overall_confidence
                )
                
                for cap in capabilities.capabilities:
                    self.tracing.log_citation(
                        claim=f"{cap.capability_type}: {cap.details}",
                        source=raw_text,
                        line_number=None
                    )
                
                self.tracing.end_agent_run("success", capabilities.dict())
            
            return capabilities
        
        except Exception as e:
            print(f"❌ Parser error: {e}")
            
            if trace_run:
                self.tracing.end_agent_run("failed", {"error": str(e)})
            
            # Return minimal structure
            return FacilityCapabilities(
                facility_id=facility_id,
                facility_name=facility_name,
                capabilities=[],
                raw_text=raw_text,
                extraction_timestamp=datetime.now().isoformat(),
                overall_confidence=0.0
            )
    
    def _fallback_extraction(
        self, 
        facility_id: str, 
        facility_name: str, 
        raw_text: str
    ) -> str:
        """
        Simple rule-based extraction when LLM is not available.
        
        Args:
            facility_id: Facility ID
            facility_name: Facility name
            raw_text: Input text
            
        Returns:
            JSON string with extracted capabilities
        """
        capabilities = []
        text_lower = raw_text.lower()
        
        # Simple keyword matching
        if any(word in text_lower for word in ['emergency', '24/7', '24-hour', 'er']):
            capabilities.append({
                "capability_type": "emergency",
                "details": "Emergency services available",
                "equipment": [],
                "staff_required": {},
                "availability": "24/7",
                "confidence": 0.6,
                "citation": raw_text[:100]
            })
        
        if any(word in text_lower for word in ['ct', 'mri', 'x-ray', 'ultrasound', 'scanner']):
            capabilities.append({
                "capability_type": "imaging",
                "details": "Medical imaging available",
                "equipment": ["imaging equipment"],
                "staff_required": {},
                "availability": "unknown",
                "confidence": 0.5,
                "citation": raw_text[:100]
            })
        
        if any(word in text_lower for word in ['surgery', 'operating', 'surgeon']):
            capabilities.append({
                "capability_type": "surgery",
                "details": "Surgical services available",
                "equipment": [],
                "staff_required": {},
                "availability": "unknown",
                "confidence": 0.5,
                "citation": raw_text[:100]
            })
        
        result = {
            "facility_id": facility_id,
            "facility_name": facility_name,
            "capabilities": capabilities,
            "raw_text": raw_text,
            "extraction_timestamp": datetime.now().isoformat(),
            "overall_confidence": 0.5
        }
        
        return json.dumps(result, indent=2)
    
    def batch_parse(
        self, 
        facilities: List[Dict[str, str]]
    ) -> List[FacilityCapabilities]:
        """
        Parse multiple facilities in batch.
        
        Args:
            facilities: List of dicts with facility_id, facility_name, raw_text
            
        Returns:
            List of parsed capabilities
        """
        results = []
        
        print(f"🔄 Parsing {len(facilities)} facilities...")
        
        for i, facility in enumerate(facilities):
            print(f"  [{i+1}/{len(facilities)}] Parsing {facility.get('facility_name', 'unknown')}")
            
            result = self.parse_facility_text(
                facility_id=facility.get("facility_id", f"unknown_{i}"),
                facility_name=facility.get("facility_name", "Unknown Facility"),
                raw_text=facility.get("raw_text", ""),
                trace_run=False  # Disable individual tracing for batch
            )
            
            results.append(result)
        
        print(f"✅ Parsed {len(results)} facilities")
        return results


if __name__ == "__main__":
    # Quick test
    agent = ParserAgent()
    
    test_facility = {
        "facility_id": "TEST-001",
        "facility_name": "Test Hospital",
        "raw_text": "Regional hospital with 24-hour emergency services. Has CT scanner and 3 surgeons on staff."
    }
    
    result = agent.parse_facility_text(
        test_facility["facility_id"],
        test_facility["facility_name"],
        test_facility["raw_text"],
        trace_run=False
    )
    
    print(f"\n✅ Parser Agent test complete")
    print(f"Extracted {len(result.capabilities)} capabilities")
