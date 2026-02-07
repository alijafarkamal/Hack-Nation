"""Phase 3 tests — Geospatial math (pure local, no Databricks calls).

These verify Haversine distance and medical desert detection logic.
Can run without any Databricks credentials.

Usage: pytest tests/test_geospatial.py -v
"""

import pytest

from src.nodes.geospatial import (
    find_desert_regions,
    find_facilities_within_radius,
    haversine_km,
)


class TestHaversine:
    """Test Haversine distance calculations."""

    def test_accra_to_kumasi(self):
        """Haversine between Accra and Kumasi should be ~250 km."""
        d = haversine_km(5.6037, -0.1870, 6.6885, -1.6244)
        assert 240 < d < 260

    def test_same_point_is_zero(self):
        """Distance from a point to itself should be 0."""
        d = haversine_km(5.6037, -0.1870, 5.6037, -0.1870)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_accra_to_tamale(self):
        """Haversine between Accra and Tamale should be ~500-600 km."""
        d = haversine_km(5.6037, -0.1870, 9.4034, -0.8393)
        assert 400 < d < 600


class TestDesertDetection:
    """Test medical desert identification."""

    def test_finds_missing_specialty(self):
        """Regions without ophthalmology should be flagged as deserts."""
        sample = [
            {"region_normalized": "Greater Accra", "specialties": '["cardiology","ophthalmology"]'},
            {"region_normalized": "Northern", "specialties": '["familyMedicine"]'},
        ]
        deserts = find_desert_regions(sample, specialty="ophthalmology")
        assert "Northern" in deserts
        assert "Greater Accra" not in deserts

    def test_empty_array_is_desert(self):
        """[] in specialties means no specialties found — region IS a desert for all."""
        sample = [{"region_normalized": "Upper East", "specialties": "[]"}]
        deserts = find_desert_regions(sample, specialty="cardiology")
        assert "Upper East" in deserts

    def test_all_covered_returns_empty(self):
        """If all regions have the specialty, no deserts."""
        sample = [
            {"region_normalized": "Greater Accra", "specialties": '["cardiology"]'},
            {"region_normalized": "Ashanti", "specialties": '["cardiology"]'},
        ]
        deserts = find_desert_regions(sample, specialty="cardiology")
        assert len(deserts) == 0

    def test_missing_region_skipped(self):
        """Facilities with no region_normalized should be skipped, not crash."""
        sample = [
            {"region_normalized": None, "specialties": '["cardiology"]'},
            {"region_normalized": "Northern", "specialties": "[]"},
        ]
        deserts = find_desert_regions(sample, specialty="cardiology")
        assert "Northern" in deserts


class TestFacilitiesWithinRadius:
    """Test radius-based facility search."""

    def test_finds_nearby_facilities(self):
        """Facilities within 300km of Accra should include Kumasi (~250km)."""
        facilities = [
            {"name": "Kumasi Hospital", "lat": 6.6885, "lon": -1.6244},
            {"name": "Tamale Hospital", "lat": 9.4034, "lon": -0.8393},
        ]
        results = find_facilities_within_radius(facilities, 5.6037, -0.1870, 300)
        names = [r["name"] for r in results]
        assert "Kumasi Hospital" in names
        assert "Tamale Hospital" not in names

    def test_missing_coords_skipped(self):
        """Facilities without lat/lon should be skipped, not crash."""
        facilities = [
            {"name": "No Coords", "lat": None, "lon": None},
            {"name": "Accra Clinic", "lat": 5.6037, "lon": -0.1870},
        ]
        results = find_facilities_within_radius(facilities, 5.6037, -0.1870, 10)
        assert len(results) == 1
        assert results[0]["name"] == "Accra Clinic"
