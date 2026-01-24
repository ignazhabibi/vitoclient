from vi_api_client.parsing import parse_feature_flat


def test_hysteresis_parsing():
    raw_feature = {
        "feature": "heating.dhw.temperature.hysteresis",
        "properties": {
            "switchOffValue": {"type": "number", "value": 2},
            "switchOnValue": {"type": "number", "value": 8},
            "value": {"type": "number", "value": 8},
        },
        "commands": {
            "setHysteresis": {
                "isExecutable": True,
                "name": "setHysteresis",
                "params": {
                    "hysteresis": {
                        "constraints": {"min": 1, "max": 10, "stepping": 0.5},
                        "required": True,
                        "type": "number",
                    }
                },
            },
            "setHysteresisSwitchOffValue": {
                "isExecutable": True,
                "name": "setHysteresisSwitchOffValue",
                "params": {
                    "hysteresis": {
                        "constraints": {"min": 0, "max": 2.5, "stepping": 0.5},
                        "required": True,
                        "type": "number",
                    }
                },
            },
            "setHysteresisSwitchOnValue": {
                "isExecutable": True,
                "name": "setHysteresisSwitchOnValue",
                "params": {
                    "hysteresis": {
                        "constraints": {"min": 1, "max": 10, "stepping": 0.5},
                        "required": True,
                        "type": "number",
                    }
                },
            },
        },
        "isEnabled": True,
        "isReady": True,
    }

    features = parse_feature_flat(raw_feature)

    # We expect 3 features:
    # 1. heating.dhw.temperature.hysteresis (mapped from 'value', via setHysteresis)
    # 2. heating.dhw.temperature.hysteresis.switchOnValue (via setHysteresisSwitchOnValue)
    # 3. heating.dhw.temperature.hysteresis.switchOffValue (via setHysteresisSwitchOffValue)

    assert len(features) == 3

    f_val = next(f for f in features if f.name == "heating.dhw.temperature.hysteresis")
    f_on = next(f for f in features if f.name.endswith(".switchOnValue"))
    f_off = next(f for f in features if f.name.endswith(".switchOffValue"))

    # Check Controls
    assert f_val.is_writable
    assert f_val.control.command_name == "setHysteresis"

    # These currently FAIL because of the missing mapping logic
    assert f_on.is_writable
    assert f_on.control.command_name == "setHysteresisSwitchOnValue"

    assert f_off.is_writable
    assert f_off.control.command_name == "setHysteresisSwitchOffValue"
