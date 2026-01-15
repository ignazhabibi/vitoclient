# Tutorial 1: Authentication

This tutorial explains how authentication works in the `vi_api_client` library. Understanding this is crucial because the Viessmann API uses **OAuth2 with PKCE**, a modern and secure standard.

## 1. Key Concepts

### OAuth2
OAuth2 is an authorization framework that enables applications to obtain limited access to user accounts on an HTTP service.
- **Access Token**: The key used to make API requests. Short-lived (e.g., 1 hour).
- **Refresh Token**: A long-lived key used to get a new Access Token without user interaction.
- **Client ID**: Identifies your application.
- **Redirect URI**: Where the user is sent after logging in.

### PKCE (Proof Key for Code Exchange)
PKCE extends OAuth2 to prevent code interception attacks. It involves:
1.  **Code Verifier**: A random secret string created locally.
2.  **Code Challenge**: A hashed version of the verifier sent to the server during the login request.
3.  **Verification**: When exchanging the auth code for a token, the secret verifier is sent. The server hashes it and compares it to the previously received challenge.

## 2. Implementation in `auth.py`

The library encapsulates this logic in the `OAuth` class.

### The Flow
1.  **Init**: `OAuth(client_id, ...)` loads existing tokens from `tokens.json`.
2.  **Login URL**: `get_authorization_url()` generates the link for the user. It also generates the PKCE pair internally.
3.  **Code Exchange**: `async_fetch_details_from_code(code)` takes the code the user got after login, sends it (plus the PKCE verifier) to the API, and gets tokens.
4.  **Auto-Refresh**: `async_get_access_token()` checks if the current token is expired. If so, it uses the refresh token to get a new one automatically.

### Code Highlight (`auth.py`)

```python
    async def async_get_access_token(self) -> str:
        """Return valid access token, refreshing if necessary."""
        if not self._token_info:
            raise ViAuthError("No tokens loaded. Please authenticate first.")

        # Check existing expiration (buffer of 60 seconds)
        now = time.time()
        expires_at = self._token_info.get("expires_at")
        
        # If token is valid, return it immediately
        if expires_at and now < expires_at - 60:
             return self._token_info["access_token"]
        
        # If expired, try to refresh
        if "refresh_token" in self._token_info:
            await self.async_refresh_access_token()
            return self._token_info["access_token"]
```

## 3. Best Practices managed by the Library
- **Token Persistence**: Tokens are saved to disk (`tokens.json`) so users don't have to log in every time.
- **Expiration Handling**: `expires_at` is calculated and saved, ensuring robust checks.
- **Error Handling**: `ViAuthError` is raised for specific auth failures, allowing clean handling in the CLI or UI.
