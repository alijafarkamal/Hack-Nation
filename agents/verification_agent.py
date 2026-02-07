"""
Verification Agent: Validates extracted capabilities for quality and completeness.
Detects anomalies and suspicious claims.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
from agents.parser_agent import FacilityCapabilities, MedicalCapability
from utils.mlflow_tracing import MLflowTracing


class ValidationResult(BaseModel):
    """Result of capability validation."""
    
    is_valid: bool
    confidence: float
    issues: List[str]
    warnings: List[str]
    recommendations: List[str]


class VerificationAgent:
    """Agent responsible for verifying extracted medical capabilities."""
    
    def __init__(self):
        """Initialize the Verification Agent."""
        self.tracing = MLflowTracing()
        
        # Define validation rules
        self.min_confidence_threshold = 0.5
        self.critical_capabilities = [
            "emergency",
            "surgery",
            "intensive_care"
        ]
    
    def verify_capabilities(
        self, 
        capabilities: FacilityCapabilities,
        trace_run: bool = True
    ) -> ValidationResult:
        """
        Verify the quality and completeness of extracted capabilities.
        
        Args:
            capabilities: Parsed facility capabilities
            trace_run: Whether to log to MLflow
            
        Returns:
            Validation result with issues and recommendations
        """
        if trace_run:
            self.tracing.start_agent_run(
                "verification_agent",
                {
                    "facility_id": capabilities.facility_id,
                    "capability_count": len(capabilities.capabilities)
                }
            )
        
        issues = []
        warnings = []
        recommendations = []
        
        # Check 1: Overall confidence
        if capabilities.overall_confidence < self.min_confidence_threshold:
            issues.append(
                f"Low overall confidence: {capabilities.overall_confidence:.2f} "
                f"(threshold: {self.min_confidence_threshold})"
            )
        
        # Check 2: Empty capabilities
        if not capabilities.capabilities:
            issues.append("No capabilities extracted from facility description")
            recommendations.append("Review raw text for parsing issues")
        
        # Check 3: Individual capability confidence
        low_confidence_caps = [
            cap for cap in capabilities.capabilities 
            if cap.confidence < self.min_confidence_threshold
        ]
        
        if low_confidence_caps:
            warnings.append(
                f"{len(low_confidence_caps)} capabilities have low confidence scores"
            )
        
        # Check 4: Missing critical details
        for cap in capabilities.capabilities:
            if cap.capability_type in self.critical_capabilities:
                if not cap.details or cap.details == "unknown":
                    warnings.append(
                        f"Critical capability '{cap.capability_type}' lacks details"
                    )
                
                if cap.availability == "unknown":
                    recommendations.append(
                        f"Verify availability for {cap.capability_type} services"
                    )
        
        # Check 5: Suspicious patterns
        suspicious = self._detect_suspicious_claims(capabilities)
        if suspicious:
            warnings.extend(suspicious)
        
        # Check 6: Equipment-staff alignment
        alignment_issues = self._check_equipment_staff_alignment(capabilities)
        if alignment_issues:
            warnings.extend(alignment_issues)
        
        # Check 7: Citation quality
        missing_citations = [
            cap for cap in capabilities.capabilities 
            if not cap.citation or len(cap.citation) < 10
        ]
        
        if missing_citations:
            warnings.append(
                f"{len(missing_citations)} capabilities missing proper citations"
            )
        
        # Determine overall validation status
        is_valid = len(issues) == 0
        
        # Calculate validation confidence
        validation_confidence = self._calculate_validation_confidence(
            capabilities, issues, warnings
        )
        
        result = ValidationResult(
            is_valid=is_valid,
            confidence=validation_confidence,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations
        )
        
        # Log to MLflow
        if trace_run:
            self.tracing.log_reasoning_step(
                step_name="capability_verification",
                reasoning=f"Validated {len(capabilities.capabilities)} capabilities. "
                          f"Found {len(issues)} issues, {len(warnings)} warnings",
                citations=[],
                confidence=validation_confidence
            )
            
            self.tracing.end_agent_run(
                "success" if is_valid else "warning",
                result.dict()
            )
        
        return result
    
    def _detect_suspicious_claims(
        self, 
        capabilities: FacilityCapabilities
    ) -> List[str]:
        """
        Detect potentially suspicious or unrealistic claims.
        
        Args:
            capabilities: Facility capabilities
            
        Returns:
            List of suspicious patterns found
        """
        suspicious = []
        
        # Check for excessive capabilities
        if len(capabilities.capabilities) > 20:
            suspicious.append(
                f"Unusually high number of capabilities ({len(capabilities.capabilities)}). "
                "Verify against source document."
            )
        
        # Check for conflicting information
        has_advanced_surgery = any(
            'surgery' in cap.capability_type.lower() and 
            any(eq in ['MRI', 'CT', 'advanced'] for eq in cap.equipment)
            for cap in capabilities.capabilities
        )
        
        has_minimal_staff = any(
            cap.staff_required and sum(cap.staff_required.values()) < 2
            for cap in capabilities.capabilities
        )
        
        if has_advanced_surgery and has_minimal_staff:
            suspicious.append(
                "Advanced surgical capabilities claimed with minimal staff. Verify accuracy."
            )
        
        return suspicious
    
    def _check_equipment_staff_alignment(
        self, 
        capabilities: FacilityCapabilities
    ) -> List[str]:
        """
        Check if equipment and staff capabilities are aligned.
        
        Args:
            capabilities: Facility capabilities
            
        Returns:
            List of alignment issues
        """
        issues = []
        
        # Define equipment-staff requirements
        equipment_staff_map = {
            "CT": ["radiologist", "technician"],
            "MRI": ["radiologist", "technician"],
            "surgery": ["surgeon", "anesthesiologist", "nurse"],
            "ICU": ["doctor", "nurse"]
        }
        
        for cap in capabilities.capabilities:
            for equipment in cap.equipment:
                required_staff = equipment_staff_map.get(equipment, [])
                
                if required_staff and cap.staff_required:
                    staff_roles = [role.lower() for role in cap.staff_required.keys()]
                    
                    missing_staff = [
                        staff for staff in required_staff 
                        if not any(staff in role for role in staff_roles)
                    ]
                    
                    if missing_staff:
                        issues.append(
                            f"{equipment} equipment present but missing {', '.join(missing_staff)}"
                        )
        
        return issues
    
    def _calculate_validation_confidence(
        self,
        capabilities: FacilityCapabilities,
        issues: List[str],
        warnings: List[str]
    ) -> float:
        """
        Calculate overall validation confidence score.
        
        Args:
            capabilities: Facility capabilities
            issues: List of validation issues
            warnings: List of warnings
            
        Returns:
            Confidence score (0-1)
        """
        base_confidence = capabilities.overall_confidence
        
        # Penalize for issues and warnings
        issue_penalty = len(issues) * 0.2
        warning_penalty = len(warnings) * 0.05
        
        confidence = max(0.0, base_confidence - issue_penalty - warning_penalty)
        
        return round(confidence, 2)
    
    def batch_verify(
        self, 
        facilities_capabilities: List[FacilityCapabilities]
    ) -> List[ValidationResult]:
        """
        Verify multiple facilities in batch.
        
        Args:
            facilities_capabilities: List of parsed capabilities
            
        Returns:
            List of validation results
        """
        results = []
        
        print(f"🔍 Verifying {len(facilities_capabilities)} facilities...")
        
        for i, caps in enumerate(facilities_capabilities):
            print(f"  [{i+1}/{len(facilities_capabilities)}] Verifying {caps.facility_name}")
            
            result = self.verify_capabilities(caps, trace_run=False)
            results.append(result)
        
        # Summary statistics
        valid_count = sum(1 for r in results if r.is_valid)
        avg_confidence = sum(r.confidence for r in results) / len(results)
        
        print(f"✅ Verification complete")
        print(f"   Valid: {valid_count}/{len(results)}")
        print(f"   Avg confidence: {avg_confidence:.2f}")
        
        return results


if __name__ == "__main__":
    # Quick test
    from agents.parser_agent import FacilityCapabilities, MedicalCapability
    
    agent = VerificationAgent()
    
    # Create test capability
    test_caps = FacilityCapabilities(
        facility_id="TEST-001",
        facility_name="Test Hospital",
        capabilities=[
            MedicalCapability(
                capability_type="emergency",
                details="24-hour emergency services",
                equipment=["basic"],
                staff_required={"doctors": 2, "nurses": 5},
                availability="24/7",
                confidence=0.9,
                citation="Has 24-hour emergency with 2 doctors"
            )
        ],
        raw_text="Test description",
        extraction_timestamp=datetime.now().isoformat(),
        overall_confidence=0.85
    )
    
    result = agent.verify_capabilities(test_caps, trace_run=False)
    
    print(f"\n✅ Verification Agent test complete")
    print(f"Valid: {result.is_valid}")
    print(f"Issues: {len(result.issues)}")
    print(f"Warnings: {len(result.warnings)}")
