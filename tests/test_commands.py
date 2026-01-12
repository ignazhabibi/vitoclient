
import pytest
from vi_api_client.models import Feature
from vi_api_client import MockViessmannClient

@pytest.fixture
def feature_with_commands():
    data = {
        "feature": "heating.curve",
        "commands": {
            "setCurve": {
                "uri": "https://api.vi/commands/setCurve",
                "params": {
                    "slope": {"required": True, "type": "number", "min": 0.2, "max": 3.5, "stepping": 0.1},
                    "shift": {"required": True, "type": "number", "min": -13, "max": 40, "stepping": 1},
                    "mode":  {"required": False, "type": "string"}
                }
            },
            "simpleCmd": {
                "uri": "https://api.vi/commands/simpleCmd",
                "params": {}
            }
        }
    }
    return Feature.from_api(data)

@pytest.mark.asyncio
async def test_execute_command_success_kwargs(feature_with_commands):
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    # Test valid kwargs execution
    result = await client.execute_command(
        feature_with_commands, 
        "setCurve", 
        slope=1.4, 
        shift=0
    )
    assert result["success"] is True

@pytest.mark.asyncio
async def test_execute_command_success_mixed(feature_with_commands):
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    # Test mixed params (dict) and kwargs
    params = {"slope": 1.4}
    result = await client.execute_command(
        feature_with_commands, 
        "setCurve", 
        params=params,
        shift=5
    )
    assert result["success"] is True

@pytest.mark.asyncio
async def test_validation_missing_param(feature_with_commands):
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    # Missing required 'shift'
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(
            feature_with_commands, 
            "setCurve", 
            slope=1.4
        )
    assert "Missing required parameters" in str(excinfo.value)
    assert "shift" in str(excinfo.value)

@pytest.mark.asyncio
async def test_validation_unknown_command(feature_with_commands):
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(
            feature_with_commands, 
            "invalidCmd"
        )
    assert "Command 'invalidCmd' not found" in str(excinfo.value)

@pytest.mark.asyncio
async def test_cmd_without_uri(feature_with_commands):
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    # Create invalid feature manually
    feat = Feature(name="broken", commands={"oops": {}}, is_enabled=True, is_ready=True, properties={})
    
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(feat, "oops")
    assert "has no URI definition" in str(excinfo.value)

@pytest.mark.asyncio
async def test_not_executable(feature_with_commands):
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    # Create feature where command is disabled
    cmds = {
        "disabledCmd": {
            "uri": "https://api.vi/cmd", 
            "isExecutable": False,
            "params": {}
        }
    }
    feat = Feature(name="test", commands=cmds, is_enabled=True, is_ready=True, properties={})
    
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(feat, "disabledCmd")
        
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(feat, "disabledCmd")
        
    assert "is currently not executable" in str(excinfo.value)

@pytest.mark.asyncio
async def test_validation_constraints(feature_with_commands):
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    # 1. Min Value
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(feature_with_commands, "setCurve", slope=0.1, shift=0)
    assert "less than minimum" in str(excinfo.value)

    # 2. Max Value
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(feature_with_commands, "setCurve", slope=5.0, shift=0)
    assert "greater than maximum" in str(excinfo.value)

    # 3. Type Error (slope expects number)
    with pytest.raises(TypeError) as excinfo:
        await client.execute_command(feature_with_commands, "setCurve", slope="high", shift=0)
    assert "must be a number" in str(excinfo.value)

@pytest.mark.asyncio
async def test_validation_enum_regex():
    client = MockViessmannClient("Vitodens200W", auth=None)
    
    cmds = {
        "setMode": {
            "uri": "http://api/cmd",
            "params": {
                "mode": {"required": True, "type": "string", "enum": ["eco", "comfort"]}
            }
        },
        "setDate": {
            "uri": "http://api/cmd",
            "params": {
                "date": {"required": True, "type": "string", "constraints": {"regEx": r"^\d{4}-\d{2}-\d{2}$"}}
            }
        }
    }
    feat = Feature(name="test", commands=cmds, is_enabled=True, is_ready=True, properties={})

    # Enum
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(feat, "setMode", mode="invalid")
    assert "not a valid option" in str(excinfo.value)

    # Regex
    with pytest.raises(ValueError) as excinfo:
        await client.execute_command(feat, "setDate", date="01.01.2023")
    assert "does not match required pattern" in str(excinfo.value)

    # Success cases
    assert (await client.execute_command(feat, "setMode", mode="eco"))["success"] is True
    assert (await client.execute_command(feat, "setDate", date="2023-01-01"))["success"] is True
