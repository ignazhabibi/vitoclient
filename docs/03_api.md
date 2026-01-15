# Tutorial 3: API Client & Layered Architecture

This tutorial explains the high-level architecture of `api.py`. The `Client` class is the main entry point for using the library.

## 1. The Big Picture

The library is designed in layers (see `demo_mock.py` for a runnable example):

1.  **Network Layer (`auth.py`)**: Handles HTTP, Tokens, SSL.
2.  **API Layer (`api.py`)**: Knows the URLs (`/iot/v2/...`), Handles Errors (`ViConnectionError`).
3.  **Model Layer (`models.py`)**: Interpretation and Logic.

## 2. The `Client` Class

The `Client` in `api.py` acts as a facade. It provides clean async methods for every major API operation.

### Dependency Injection
The client doesn't know *how* to authenticate. It just takes an `auth` object in its constructor.
```python
client = Client(auth)
```
This is good design ("Inversion of Control") because it lets us easily swap real authentication for a mock or test authentication without changing the Client code.

### Asynchronous I/O
All network operations are `async`. This is standard for modern Python web & IoT apps. It allows the program to do other things while waiting for the server to reply.
- `async def`: Defines a coroutine.
- `await`: Pauses execution until the result is ready.

## 3. The "Get Features" Stack

Let's trace what happens when you call `get_features_with_values`:

1.  **`get_features_with_values(...)`**: (High Level)
    - Goal: "Give me simple sensors."
    - Calls -> `get_enabled_features()`
    
2.  **`get_enabled_features(...)`**: (Mid Level)
    - Goal: "Give me raw data, but only the active stuff."
    - Calls -> `get_features()`
    - Filters list using `item.get("isEnabled")`.

3.  **`get_features(...)`**: (Low Level)
    - Goal: "Valid HTTP Request to specific URL."
    - Constructs URL: `.../devices/{id}/features`
    - Calls -> `self.auth.request("GET", url)`
    - Checks Output: `if resp.status != 200: raise ViConnectionError`
    - Returns: Raw JSON.

## 4. Full Installation Status (Integration Pattern)

For integrations like Home Assistant that need to fetch the entire state of an installation at once, use `get_full_installation_status`.

```python
devices = await client.get_full_installation_status(installation_id)
# Returns List[Device] with all features loaded (and flattened versions available)
```

This method is efficient because it performs the necessary API calls in bulk (Gateway -> Devices -> Features) to build a complete picture.

## 5. Error Handling
We use a comprehensive exception hierarchy defined in `exceptions.py` (e.g. `ViConnectionError`, `ViAuthError`, `ViNotFoundError`, `ViValidationError`).

See [06_error_handling.md](06_error_handling.md) for full details on handling errors.

## 6. Command Execution
The API also supports writing values back to the device.
- Method: `client.execute_command(feature, command_name, params)`
- Logic:
    1. Looks up the command in the `Feature` object.
    2. Validates parameters locally (fail fast).
    3. Sends a POST request to the command's URI.
