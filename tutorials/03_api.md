# Tutorial 3: API Client & Layered Architecture

This tutorial explains the high-level architecture of `api.py`. The `Client` class is the main entry point for using the library.

## 1. The Big Picture

The library is designed in layers (see `demo.py` for a runnable example):

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

## 4. Error Handling
We use custom exceptions defined in `exceptions.py`:
- `ViConnectionError`: Network down, API 500/404 errors.
- `ViAuthError`: Token expired, Bad credentials.

By catching these specific errors, your application can react intelligently (e.g., "Retry later" vs "Ask user for password again").
