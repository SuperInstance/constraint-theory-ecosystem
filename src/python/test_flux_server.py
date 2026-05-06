#!/usr/bin/env python3
"""
Integration tests for FLUX Constraint Engine REST API Server

Run with:
    python -m pytest test_flux_server.py -v
    python -m pytest test_flux_server.py::test_health_check -v

Requirements:
    pip install pytest flask
"""

import json
import pytest
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

from flux_server import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['API_KEYS'] = {'test-key-123', 'test-key-456'}

    with app.test_client() as client:
        yield client


@pytest.fixture
def valid_headers():
    """Valid API headers."""
    return {
        'Content-Type': 'application/json',
        'X-API-Key': 'test-key-123'
    }


@pytest.fixture
def sample_constraints():
    """Sample constraint definitions."""
    return [
        {"name": "temperature", "lo": 20, "hi": 80},
        {"name": "pressure", "lo": 10, "hi": 50}
    ]


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check_returns_200(self, client, valid_headers):
        """Health check should return 200 with valid API key."""
        response = client.get('/health', headers=valid_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'version' in data
        assert 'uptime_seconds' in data
        assert 'timestamp' in data
        assert isinstance(data['uptime_seconds'], int)

    def test_health_check_missing_api_key(self, client):
        """Health check should require API key."""
        response = client.get('/health')
        assert response.status_code == 401

        data = response.get_json()
        assert data['error']['code'] == 'MISSING_API_KEY'

    def test_health_check_invalid_api_key(self, client):
        """Health check should reject invalid API key."""
        headers = {'X-API-Key': 'invalid-key'}
        response = client.get('/health', headers=headers)
        assert response.status_code == 403

        data = response.get_json()
        assert data['error']['code'] == 'INVALID_API_KEY'


class TestSingleValueCheck:
    """Test single value constraint checking."""

    def test_check_valid_data_returns_result(self, client, valid_headers, sample_constraints):
        """Valid constraint check should return proper result."""
        payload = {
            "constraints": sample_constraints,
            "value": 25
        }

        response = client.post('/check', headers=valid_headers, json=payload)
        assert response.status_code == 200

        data = response.get_json()
        assert 'error_mask' in data
        assert 'severity' in data
        assert 'violated_lo' in data
        assert 'violated_hi' in data
        assert 'details' in data
        assert data['severity'] == 'pass'
        assert len(data['details']) == 2

    def test_check_violation_high(self, client, valid_headers, sample_constraints):
        """Value exceeding constraints should be detected."""
        payload = {
            "constraints": sample_constraints,
            "value": 95  # Above temperature hi=80 and pressure hi=50
        }

        response = client.post('/check', headers=valid_headers, json=payload)
        assert response.status_code == 200

        data = response.get_json()
        assert data['severity'] == 'critical'
        assert data['violated_hi'] is True
        assert data['violated_lo'] is False
        assert data['error_mask'] > 0

        # Check details
        for detail in data['details']:
            assert not detail['passed']
            assert 'violation_type' in detail
            assert detail['violation_type'] == 'high'

    def test_check_violation_low(self, client, valid_headers, sample_constraints):
        """Value below constraints should be detected."""
        payload = {
            "constraints": sample_constraints,
            "value": 5  # Below temperature lo=20 and pressure lo=10
        }

        response = client.post('/check', headers=valid_headers, json=payload)
        assert response.status_code == 200

        data = response.get_json()
        assert data['severity'] in ['warning', 'critical']
        assert data['violated_lo'] is True
        assert data['error_mask'] > 0

    def test_check_invalid_data_returns_400(self, client, valid_headers):
        """Invalid constraint data should return 400."""
        invalid_payloads = [
            {},  # Missing data
            {"constraints": []},  # Empty constraints
            {"constraints": [{"name": "temp", "lo": 20}]},  # Missing hi
            {"constraints": [{"name": "temp", "lo": "invalid", "hi": 80}]},  # Invalid number
            {"constraints": [{"name": "temp", "lo": 80, "hi": 20}]},  # lo >= hi
            {"value": 25},  # Missing constraints
            {"constraints": [{"name": "temp", "lo": 20, "hi": 80}]},  # Missing value
            {"constraints": [{"name": "temp", "lo": 20, "hi": 80}], "value": "invalid"}  # Invalid value
        ]

        for payload in invalid_payloads:
            response = client.post('/check', headers=valid_headers, json=payload)
            assert response.status_code == 400
            data = response.get_json()
            assert 'error' in data

    def test_check_missing_api_key(self, client, sample_constraints):
        """Check endpoint should require API key."""
        payload = {
            "constraints": sample_constraints,
            "value": 25
        }

        response = client.post('/check', json=payload)
        assert response.status_code == 401


class TestBatchCheck:
    """Test batch value constraint checking."""

    def test_batch_check_works(self, client, valid_headers, sample_constraints):
        """Batch check should process multiple values."""
        payload = {
            "constraints": sample_constraints,
            "values": [25, 45, 75, 95]
        }

        response = client.post('/check/batch', headers=valid_headers, json=payload)
        assert response.status_code == 200

        data = response.get_json()
        assert 'results' in data
        assert 'stats' in data
        assert len(data['results']) == 4

        # Check stats
        stats = data['stats']
        assert stats['total'] == 4
        assert 'pass' in stats
        assert 'critical' in stats

        # Verify individual results
        for i, result in enumerate(data['results']):
            assert 'value' in result
            assert result['value'] == payload['values'][i]
            assert 'severity' in result
            assert 'details' in result

    def test_batch_check_invalid_values(self, client, valid_headers, sample_constraints):
        """Batch check should validate values."""
        invalid_payloads = [
            {"constraints": sample_constraints},  # Missing values
            {"constraints": sample_constraints, "values": []},  # Empty values
            {"constraints": sample_constraints, "values": [25, "invalid", 75]},  # Invalid value type
        ]

        for payload in invalid_payloads:
            response = client.post('/check/batch', headers=valid_headers, json=payload)
            assert response.status_code == 400


class TestPresets:
    """Test preset management endpoints."""

    def test_presets_list_returns_all_10(self, client, valid_headers):
        """Presets endpoint should return all available presets."""
        response = client.get('/presets', headers=valid_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert 'presets' in data
        presets = data['presets']

        # Should have all 10 presets
        expected_presets = [
            'aviation', 'medical', 'automotive', 'nuclear', 'energy',
            'maritime', 'railway', 'robotics', 'space', 'underwater'
        ]

        for preset in expected_presets:
            assert preset in presets
            assert 'name' in presets[preset]
            assert 'description' in presets[preset]
            assert 'constraint_count' in presets[preset]
            assert isinstance(presets[preset]['constraint_count'], int)

    def test_specific_preset_returns_correct_constraints(self, client, valid_headers):
        """Specific preset should return detailed constraints."""
        response = client.get('/presets/aviation', headers=valid_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert data['name'] == 'aviation'
        assert 'display_name' in data
        assert 'description' in data
        assert 'version' in data
        assert 'constraints' in data

        # Check constraint structure
        constraints = data['constraints']
        assert len(constraints) > 0
        for constraint in constraints:
            assert 'name' in constraint
            assert 'lo' in constraint
            assert 'hi' in constraint
            assert isinstance(constraint['lo'], (int, float))
            assert isinstance(constraint['hi'], (int, float))

    def test_unknown_preset_returns_404(self, client, valid_headers):
        """Unknown preset should return 404."""
        response = client.get('/presets/unknown_preset', headers=valid_headers)
        assert response.status_code == 404

        data = response.get_json()
        assert data['error']['code'] == 'PRESET_NOT_FOUND'

    def test_presets_missing_api_key(self, client):
        """Presets endpoints should require API key."""
        response = client.get('/presets')
        assert response.status_code == 401


class TestBenchmark:
    """Test benchmark endpoint."""

    def test_benchmark_returns_timing_data(self, client, valid_headers):
        """Benchmark should return performance metrics."""
        response = client.get('/benchmark?iterations=1000&constraints=3', headers=valid_headers)
        assert response.status_code == 200

        data = response.get_json()
        assert 'benchmark_id' in data
        assert 'timestamp' in data
        assert 'config' in data
        assert 'results' in data
        assert 'environment' in data

        # Check config
        config = data['config']
        assert config['iterations'] == 1000
        assert config['constraint_count'] == 3

        # Check results
        results = data['results']
        assert 'total_checks' in results
        assert 'total_duration_ms' in results
        assert 'checks_per_second' in results
        assert 'checks_per_second_M' in results
        assert results['total_checks'] == 3000  # iterations * constraints

    def test_benchmark_invalid_parameters(self, client, valid_headers):
        """Benchmark should validate parameters."""
        invalid_params = [
            "?iterations=0",
            "?iterations=20000000",  # Too many
            "?constraints=0",
            "?constraints=10",  # Too many (max 8)
        ]

        for params in invalid_params:
            response = client.get(f'/benchmark{params}', headers=valid_headers)
            assert response.status_code == 400


class TestEdgeCases:
    """Test edge cases and boundary values."""

    def test_saturation_limits(self, client, valid_headers):
        """Test INT8 saturation limits."""
        constraints = [{"name": "test", "lo": -127, "hi": 127}]

        # Test extreme values
        extreme_values = [-200, -127, 0, 127, 200]
        for value in extreme_values:
            payload = {"constraints": constraints, "value": value}
            response = client.post('/check', headers=valid_headers, json=payload)
            assert response.status_code == 200

            data = response.get_json()
            # Value should be clamped to [-127, 127] range
            result_value = data['details'][0]['value']
            assert -127 <= result_value <= 127

    def test_boundary_values(self, client, valid_headers):
        """Test exact boundary values."""
        constraints = [{"name": "test", "lo": 10, "hi": 90}]

        boundary_tests = [
            (9, False),   # Just below lo
            (10, True),   # Exactly lo
            (50, True),   # Middle
            (90, True),   # Exactly hi
            (91, False),  # Just above hi
        ]

        for value, should_pass in boundary_tests:
            payload = {"constraints": constraints, "value": value}
            response = client.post('/check', headers=valid_headers, json=payload)
            assert response.status_code == 200

            data = response.get_json()
            assert data['details'][0]['passed'] == should_pass

    def test_single_constraint(self, client, valid_headers):
        """Test with single constraint."""
        payload = {
            "constraints": [{"name": "single", "lo": 0, "hi": 100}],
            "value": 50
        }

        response = client.post('/check', headers=valid_headers, json=payload)
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['details']) == 1
        assert data['details'][0]['passed'] is True

    def test_maximum_constraints(self, client, valid_headers):
        """Test with maximum number of constraints (8)."""
        constraints = []
        for i in range(8):
            constraints.append({
                "name": f"constraint_{i}",
                "lo": i * 10,
                "hi": (i + 1) * 10 + 50
            })

        payload = {"constraints": constraints, "value": 25}
        response = client.post('/check', headers=valid_headers, json=payload)
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['details']) == 8


class TestConcurrentRequests:
    """Test concurrent request handling."""

    def test_concurrent_requests(self, client, valid_headers, sample_constraints):
        """Test handling multiple concurrent requests."""
        def make_request():
            payload = {
                "constraints": sample_constraints,
                "value": 25
            }
            response = client.post('/check', headers=valid_headers, json=payload)
            return response.status_code == 200

        # Run 10 concurrent requests
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in as_completed(futures)]

        # All requests should succeed
        assert all(results)

    def test_concurrent_batch_requests(self, client, valid_headers, sample_constraints):
        """Test concurrent batch requests."""
        def make_batch_request(values):
            payload = {
                "constraints": sample_constraints,
                "values": values
            }
            response = client.post('/check/batch', headers=valid_headers, json=payload)
            return response.status_code == 200, len(response.get_json()['results'])

        # Different value sets for each request
        value_sets = [
            [10, 20, 30],
            [40, 50, 60],
            [70, 80, 90],
            [15, 35, 55],
            [25, 45, 65]
        ]

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_batch_request, values) for values in value_sets]
            results = [future.result() for future in as_completed(futures)]

        # All requests should succeed with correct number of results
        for success, count in results:
            assert success
            assert count == 3


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_malformed_json(self, client, valid_headers):
        """Test handling of malformed JSON."""
        response = client.post('/check',
                             headers=valid_headers,
                             data="invalid json")
        assert response.status_code == 400

    def test_empty_request_body(self, client, valid_headers):
        """Test handling of empty request body."""
        response = client.post('/check', headers=valid_headers)
        assert response.status_code == 400

    def test_very_large_batch(self, client, valid_headers, sample_constraints):
        """Test handling of large batch requests."""
        large_values = list(range(1000))  # 1000 values
        payload = {
            "constraints": sample_constraints,
            "values": large_values
        }

        response = client.post('/check/batch', headers=valid_headers, json=payload)
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['results']) == 1000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])