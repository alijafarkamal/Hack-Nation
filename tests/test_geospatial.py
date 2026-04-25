"""Local geospatial unit tests (no Databricks)."""

import pytest

from src.nodes.geospatial import (
    find_desert_states,
    find_facilities_within_radius,
    haversine_km,
)


def test_haversine_delhi_mumbai_roughly():
    d = haversine_km(28.61, 77.20, 19.08, 72.88)
    assert 1000 < d < 1600


def test_haversine_same_point():
    d = haversine_km(12.9, 77.5, 12.9, 77.5)
    assert d == pytest.approx(0.0, abs=0.01)


def test_desert_states_missing_specialty():
    sample = [
        {"state_normalized": "Maharashtra", "specialties": '["cardiology","ophthalmology"]'},
        {"state_normalized": "Bihar", "specialties": '["familyMedicine"]'},
    ]
    deserts = find_desert_states(sample, "ophthalmology")
    assert "Bihar" in deserts
    assert "Maharashtra" not in deserts


def test_find_facilities_within_radius_keys():
    fac = [
        {"name": "A", "latitude": 28.61, "longitude": 77.20},
        {"name": "B", "latitude": 40.0, "longitude": -74.0},
    ]
    r = find_facilities_within_radius(fac, 28.61, 77.20, 50)
    assert r and r[0]["name"] == "A"
