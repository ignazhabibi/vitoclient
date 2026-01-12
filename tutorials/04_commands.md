# Tutorial 04: Executing Commands

This tutorial demonstrates how to modify device settings by executing commands.

## Prerequisites

Ensure you have authenticated and have a valid `client` instance (see [01_authentication.md](01_authentication.md)).

## The Concept

Viessmann features usually separate **Properties** (Read) and **Commands** (Write).
To change a value (e.g. heating curve slope), you execute a command (e.g. `setCurve`) on the feature.

## Step-by-Step

### 1. Fetch the Feature
You need the feature object first to get the command metadata (URL).

```python
# Fetch the raw feature (not flattened)
feature_data = await client.get_feature(
    installation_id, 
    gateway_serial, 
    device_id, 
    "heating.circuits.0.heating.curve"
)
feature = Feature.from_api(feature_data)
```

### 2. Check Available Commands
You can inspect what commands are available for this feature.

```python
print(feature.commands.keys())
# Output: dict_keys(['setCurve'])
```

### 3. Execute the Command
Use `client.execute_command` to send the new values. Parameters must match the API requirements.
You can pass parameters as a dictionary or simply as keyword arguments (kwargs).

```python
# Option 1: Using kwargs (Cleaner)
result = await client.execute_command(feature, "setCurve", slope=1.4, shift=0)

# Option 2: Using dictionary
# params = {"slope": 1.4, "shift": 0}
# result = await client.execute_command(feature, "setCurve", **params)

if result.get("success"):
    print("Command executed successfully!")
else:
    print(f"Error: {result}")
```

> [!NOTE]
> The client automatically validates parameters against API constraints locally:
> - **Types**: Ensures numbers are numbers, booleans are bools.
> - **Constraints**: Checks `min`, `max`, `stepping`, and `enum` values.
> - **Patterns**: Validates `regEx` matches.
> If a check fails, it raises a `ValueError` or `TypeError` immediately with a descriptive message.


## Important Notes

1. **Parameters**: The parameters must mirror the JSON structure expected by the API. use `vi-client get <feature>` to inspect the constraints in the `commands` section.
2. **Context**: Logic for dependent parameters (e.g. sending both slope and shift) must be handled by your application logic. The client just sends what you pass it.
3. **Mocking**: The `MockViessmannClient` supports `execute_command` and will return a success response without performing network calls.
