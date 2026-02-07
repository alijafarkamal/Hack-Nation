"""
Mapper Agent: Identifies medical deserts based on facility capabilities and geography.
Uses geospatial analysis to find underserved regions.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import math
from pydantic import BaseModel
from agents.parser_agent import FacilityCapabilities
from utils.mlflow_tracing import MLflowTracing


class Coordinate(BaseModel):
    """Geographic coordinate."""
    latitude: float
    longitude: float


class MedicalDesert(BaseModel):
    """Represents an identified medical desert region."""
    
    desert_id: str
    region: str
    center_point: Coordinate
    radius_km: float
    missing_capabilities: List[str]
    nearest_facility_id: Optional[str]
    distance_to_nearest_km: float
    affected_population: Optional[int]
    severity_score: float  # 0-1, higher is more severe


class FacilityWithLocation(BaseModel):
    """Facility with geographic location."""
    
    facility_id: str
    facility_name: str
    coordinates: Coordinate
    capabilities: List[str]
    is_critical: bool  # Has emergency/surgery capabilities


class MapperAgent:
    """Agent responsible for identifying medical desert regions."""
    
    def __init__(self):
        """Initialize the Mapper Agent."""
        self.tracing = MLflowTracing()
        
        # Configuration
        self.medical_desert_threshold_km = 50.0  # Distance threshold
        self.critical_capabilities = [
            "emergency",
            "surgery",
            "intensive_care",
            "imaging"
        ]
    
    def identify_medical_deserts(
        self,
        facilities: List[FacilityWithLocation],
        region: str,
        trace_run: bool = True
    ) -> List[MedicalDesert]:
        """
        Identify medical desert regions based on facility distribution.
        
        Args:
            facilities: List of facilities with locations and capabilities
            region: Region name for analysis
            trace_run: Whether to log to MLflow
            
        Returns:
            List of identified medical deserts
        """
        if trace_run:
            self.tracing.start_agent_run(
                "mapper_agent",
                {
                    "region": region,
                    "facility_count": len(facilities),
                    "threshold_km": self.medical_desert_threshold_km
                }
            )
        
        deserts = []
        
        # Find critical care facilities
        critical_facilities = [f for f in facilities if f.is_critical]
        
        if not critical_facilities:
            # Entire region is a desert if no critical facilities
            center = self._calculate_region_center(facilities)
            
            desert = MedicalDesert(
                desert_id=f"{region}_complete_desert",
                region=region,
                center_point=center,
                radius_km=100.0,
                missing_capabilities=self.critical_capabilities,
                nearest_facility_id=None,
                distance_to_nearest_km=float('inf'),
                affected_population=None,
                severity_score=1.0
            )
            
            deserts.append(desert)
        
        else:
            # Analyze each facility's coverage
            for facility in facilities:
                # Find distance to nearest critical facility
                distances = [
                    self._haversine_distance(
                        facility.coordinates,
                        critical_fac.coordinates
                    )
                    for critical_fac in critical_facilities
                    if critical_fac.facility_id != facility.facility_id
                ]
                
                if distances:
                    nearest_distance = min(distances)
                    
                    if nearest_distance > self.medical_desert_threshold_km:
                        # This area is a medical desert
                        nearest_idx = distances.index(nearest_distance)
                        nearest_facility = critical_facilities[nearest_idx]
                        
                        # Determine missing capabilities
                        missing_caps = self._find_missing_capabilities(
                            facility.capabilities,
                            self.critical_capabilities
                        )
                        
                        # Calculate severity
                        severity = self._calculate_severity(
                            nearest_distance,
                            len(missing_caps)
                        )
                        
                        desert = MedicalDesert(
                            desert_id=f"{facility.facility_id}_desert",
                            region=region,
                            center_point=facility.coordinates,
                            radius_km=self.medical_desert_threshold_km,
                            missing_capabilities=missing_caps,
                            nearest_facility_id=nearest_facility.facility_id,
                            distance_to_nearest_km=round(nearest_distance, 2),
                            affected_population=None,  # Would need census data
                            severity_score=severity
                        )
                        
                        deserts.append(desert)
        
        # Sort by severity
        deserts.sort(key=lambda d: d.severity_score, reverse=True)
        
        # Log to MLflow
        if trace_run:
            self.tracing.log_reasoning_step(
                step_name="medical_desert_identification",
                reasoning=f"Identified {len(deserts)} medical desert regions in {region}. "
                          f"Analyzed {len(facilities)} facilities with {len(critical_facilities)} critical care centers.",
                citations=[f"facility_{f.facility_id}" for f in critical_facilities],
                confidence=0.85
            )
            
            self.tracing.log_medical_desert_detection(
                region=region,
                deserts=[d.dict() for d in deserts],
                analysis={
                    "total_deserts": len(deserts),
                    "avg_severity": sum(d.severity_score for d in deserts) / len(deserts) if deserts else 0,
                    "max_distance_km": max((d.distance_to_nearest_km for d in deserts), default=0)
                }
            )
            
            self.tracing.end_agent_run("success", {
                "desert_count": len(deserts),
                "region": region
            })
        
        return deserts
    
    def _haversine_distance(
        self, 
        coord1: Coordinate, 
        coord2: Coordinate
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Args:
            coord1: First coordinate
            coord2: Second coordinate
            
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1 = math.radians(coord1.latitude), math.radians(coord1.longitude)
        lat2, lon2 = math.radians(coord2.latitude), math.radians(coord2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def _calculate_region_center(
        self, 
        facilities: List[FacilityWithLocation]
    ) -> Coordinate:
        """
        Calculate the geographic center of a region.
        
        Args:
            facilities: List of facilities
            
        Returns:
            Center coordinate
        """
        if not facilities:
            return Coordinate(latitude=0.0, longitude=0.0)
        
        avg_lat = sum(f.coordinates.latitude for f in facilities) / len(facilities)
        avg_lon = sum(f.coordinates.longitude for f in facilities) / len(facilities)
        
        return Coordinate(latitude=avg_lat, longitude=avg_lon)
    
    def _find_missing_capabilities(
        self, 
        available: List[str], 
        required: List[str]
    ) -> List[str]:
        """
        Find missing critical capabilities.
        
        Args:
            available: Available capabilities
            required: Required capabilities
            
        Returns:
            List of missing capabilities
        """
        available_lower = [cap.lower() for cap in available]
        
        missing = [
            req for req in required
            if not any(req.lower() in avail for avail in available_lower)
        ]
        
        return missing
    
    def _calculate_severity(
        self, 
        distance_km: float, 
        missing_count: int
    ) -> float:
        """
        Calculate medical desert severity score.
        
        Args:
            distance_km: Distance to nearest critical facility
            missing_count: Number of missing critical capabilities
            
        Returns:
            Severity score (0-1)
        """
        # Distance component (normalized to 0-1, 100km = max)
        distance_score = min(distance_km / 100.0, 1.0)
        
        # Missing capabilities component
        capability_score = missing_count / len(self.critical_capabilities)
        
        # Weighted average (distance 60%, missing capabilities 40%)
        severity = 0.6 * distance_score + 0.4 * capability_score
        
        return round(severity, 2)
    
    def generate_map_data(
        self, 
        deserts: List[MedicalDesert],
        facilities: List[FacilityWithLocation]
    ) -> Dict[str, Any]:
        """
        Generate data structure for map visualization.
        
        Args:
            deserts: List of medical deserts
            facilities: List of facilities
            
        Returns:
            Map-ready data structure
        """
        return {
            "type": "FeatureCollection",
            "features": [
                # Desert polygons
                *[{
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            desert.center_point.longitude,
                            desert.center_point.latitude
                        ]
                    },
                    "properties": {
                        "type": "medical_desert",
                        "desert_id": desert.desert_id,
                        "radius_km": desert.radius_km,
                        "severity": desert.severity_score,
                        "missing_capabilities": desert.missing_capabilities
                    }
                } for desert in deserts],
                
                # Facility markers
                *[{
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            facility.coordinates.longitude,
                            facility.coordinates.latitude
                        ]
                    },
                    "properties": {
                        "type": "facility",
                        "facility_id": facility.facility_id,
                        "name": facility.facility_name,
                        "is_critical": facility.is_critical,
                        "capabilities": facility.capabilities
                    }
                } for facility in facilities]
            ]
        }


if __name__ == "__main__":
    # Quick test
    agent = MapperAgent()
    
    # Create test facilities
    test_facilities = [
        FacilityWithLocation(
            facility_id="FAC-001",
            facility_name="Central Hospital",
            coordinates=Coordinate(latitude=5.6, longitude=-0.2),
            capabilities=["emergency", "surgery", "imaging"],
            is_critical=True
        ),
        FacilityWithLocation(
            facility_id="FAC-002",
            facility_name="Rural Clinic",
            coordinates=Coordinate(latitude=6.2, longitude=-0.8),
            capabilities=["basic_care"],
            is_critical=False
        )
    ]
    
    deserts = agent.identify_medical_deserts(
        test_facilities,
        "Western Region",
        trace_run=False
    )
    
    print(f"\n✅ Mapper Agent test complete")
    print(f"Identified {len(deserts)} medical deserts")
