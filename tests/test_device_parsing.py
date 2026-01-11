
import pytest
from vi_api_client import MockViessmannClient

@pytest.mark.asyncio
async def test_mock_client_parsing(available_mock_devices):
    """Test that the MockClient can parse all provided sample files without error."""
    
    # Iterate over all available devices
    for device_name in available_mock_devices:
        client = MockViessmannClient(device_name)
        
        # Test 1: Get Features (Raw)
        features = await client.get_features(0, "mock", "0")
        assert len(features) > 0, f"{device_name}: No features found"
        
        # Test 2: Get Features (Models)
        features_models = await client.get_features_models(0, "mock", "0")
        assert len(features_models) == len(features), f"{device_name}: Model count mismatch"
        
        # Test 3: Flattening
        # Ensure expand() works without crashing on any feature of any device
        flat_count = 0
        for f in features_models:
            expanded = f.expand()
            flat_count += len(expanded)
            # Basic sanity check on values
            for item in expanded:
                # Accessing formatted_value triggers value/unit logic
                assert isinstance(item.formatted_value, str)
                
        print(f"Device {device_name}: {len(features)} raw features -> {flat_count} flat features")

@pytest.mark.asyncio
async def test_mock_specific_feature():
    """Test fetching a specific feature from the mock."""
    # We know Vitodens200W has 'heating.burner'
    client = MockViessmannClient("Vitodens200W")
    
    feature = await client.get_feature(0, "mock", "0", "heating.burner")
    assert feature is not None
    assert feature.get("feature") == "heating.burner"
    
    # Test missing feature
    missing = await client.get_feature(0, "mock", "0", "non_existent.feature")
    assert missing == {}

@pytest.mark.asyncio
async def test_mock_device_list():
    """Test getting the device list."""
    client = MockViessmannClient("Vitocal200")
    devices = await client.get_devices(0, "mock")
    
    assert len(devices) == 1
    assert devices[0]["modelId"] == "Vitocal200"

@pytest.mark.asyncio
async def test_feature_filtering_and_expansion():
    """Test that empty features are filtered and schedules are expanded."""
    client = MockViessmannClient("Vitodens200W")
    features_models = await client.get_features_models(0, "mock", "0")
    
    # Flatten features manually to inspect
    flat_features = []
    for f in features_models:
        flat_features.extend(f.expand())
        
    flat_names = [f.name for f in flat_features]
    
    # 1. Test Filtering: 'heating.operating' (pure structure) should be GONE
    assert "heating.operating" not in flat_names, "Empty structural feature was not filtered out"
    
    # 2. Test Expansion: 'heating.circuits.0.heating.schedule' should be PRESENT (expanded)
    # It should have active and entries
    schedule_active = next((f for f in flat_features if f.name == "heating.circuits.0.heating.schedule.active"), None)
    schedule_entries = next((f for f in flat_features if f.name == "heating.circuits.0.heating.schedule.entries"), None)
    
    assert schedule_active is not None, "Schedule active status missing"
    assert schedule_entries is not None, "Schedule entries missing"
    assert isinstance(schedule_entries.value, dict), "Schedule entries should be a dictionary"

@pytest.mark.asyncio
async def test_redundant_suffix_removal():
    """Test that redundant suffixes (e.g. name.name) are removed."""
    # Vitocal252 has 'heating.circuits.0.name' with property 'name'
    client = MockViessmannClient("Vitocal252")
    features_models = await client.get_features_models(0, "mock", "0")
    
    flat_features = []
    for f in features_models:
        flat_features.extend(f.expand())
    
    flat_names = [f.name for f in flat_features]
    
    # Check for the clean name
    assert "heating.circuits.0.name" in flat_names, "Clean name feature missing"
    # Check that the redundant one is GONE
    assert "heating.circuits.0.name.name" not in flat_names, "Redundant name.name feature present"
