
import json
import os
from typing import Any, Dict, List, Optional

from .api import Client
from .auth import AbstractAuth

class MockAuth(AbstractAuth):
    """Mock authentication provider."""
    
    async def async_get_access_token(self) -> str:
        return "mock_token"

    def __init__(self, websession: Any = None) -> None:
        # Standard AbstractAuth expects a websession, but we don't use it in Mock
        super().__init__(websession)

class MockViessmannClient(Client):
    """
    A mock client that returns static responses from JSON files.
    Useful for testing, CLI usage without credentials, and development.
    """

    def __init__(self, device_name: str, auth: Optional[AbstractAuth] = None) -> None:
        """
        Initialize the mock client.
        
        :param device_name: The name of the mock device (e.g. "Vitodens200W").
                            Must correspond to a file in the fixtures directory.
        :param auth: Optional auth provider (not used for logic, but kept for interface compatibility).
        """
        # Pass dummy auth if none provided, to satisfy superclass
        super().__init__(auth or MockAuth())
        self.device_name = device_name
        self._data_cache = None

    @staticmethod
    def get_available_mock_devices() -> List[str]:
        """Return a list of available mock device names."""
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        if not os.path.exists(fixtures_dir):
            return []
        
        files = [f for f in os.listdir(fixtures_dir) if f.endswith(".json")]
        # Return sorted names without extension
        return sorted([os.path.splitext(f)[0] for f in files])

    def _load_data(self) -> Dict[str, Any]:
        """Load the JSON data for the selected device."""
        if self._data_cache:
            return self._data_cache

        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        file_path = os.path.join(fixtures_dir, f"{self.device_name}.json")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Mock device file not found: {self.device_name}.json. "
                f"Available: {self.get_available_mock_devices()}"
            )

        with open(file_path, "r", encoding="utf-8") as f:
            self._data_cache = json.load(f)
        
        return self._data_cache

    async def get_installations(self) -> List[Dict[str, Any]]:
        """Return a mock installation."""
        return [{
            "id": 99999,
            "description": f"Mock Installation ({self.device_name})",
            "address": {"city": "Mock City"}
        }]

    async def get_gateways(self) -> List[Dict[str, Any]]:
        """Return a mock gateway."""
        return [{
            "serial": "MOCK_GATEWAY_SERIAL",
            "version": "1.0.0",
            "status": "connected"
        }]

    async def get_devices(self, installation_id: int, gateway_serial: str) -> List[Dict[str, Any]]:
        """
        Return the list of devices from the JSON file. 
        The JSON root usually has "data": [ {feature...}, {feature...} ]
        We need to reconstruct "device" objects from the features, or 
        provide a simplified device list if the JSON is just features.
        
        The sample files provided seem to be a FLAT list of all features for a device.
        So we will fake a single device that possesses all these features.
        """
        # In the real API, get_devices returns a list of device summaries.
        # Since our JSON is a dump of features for ONE device, we return one device.
        return [{
            "id": "0",
            "modelId": self.device_name,
            "deviceType": "heating", # Generic default
            "status": "online"
        }]

    async def get_features(self, installation_id: int, gateway_serial: str, device_id: str) -> List[Dict[str, Any]]:
        """Return the list of features from the loaded JSON file."""
        data = self._load_data()
        # The JSON structure in the samples is { "data": [ ...features... ] }
        return data.get("data", [])
    
    # We can rely on the superclass implementation for:
    # - get_feature (it might be inefficient as it calls get_features, but fine for mock)
    # - get_enabled_features
    # - get_features_with_values
    # - get_features_models
    #
    # However, get_feature in the base class does a specific request. 
    # We should override it to query our local list.
    
    async def get_feature(
        self, installation_id: int, gateway_serial: str, device_id: str, feature_name: str
    ) -> Dict[str, Any]:
        """Get a specific feature from the local list."""
        features = await self.get_features(installation_id, gateway_serial, device_id)
        for f in features:
            if f.get("feature") == feature_name:
                return f
        return {} # Not found

    # get_today_consumption depends on Analytics API.
    # We don't have analytics samples yet, so we can return empty or mock data.
    # For now, let's log a warning or return empty.
    async def get_today_consumption(
        self, gateway_serial: str, device_id: str, metric: str = "summary"
    ) -> Any:
        # Mock analytics support could be added later.
        # Returning empty list or None is safer than crashing.
        return []

    async def execute_command(
        self,
        feature: Any, # Use Any to avoid circular import or redefine Type
        command_name: str,
        params: Dict[str, Any] = {},
        **kwargs
    ) -> Dict[str, Any]:
        """Mock execution of a command."""
        final_params = params.copy()
        final_params.update(kwargs)
        # Validate command exists
        if command_name not in feature.commands:
            raise ValueError(
                f"Command '{command_name}' not found in feature '{feature.name}'. "
                f"Available: {list(feature.commands.keys())}"
            )
            
        cmd_def = feature.commands[command_name]
        
        # Check if command is executable
        if "isExecutable" in cmd_def and not cmd_def["isExecutable"]:
             raise ValueError(f"Command '{command_name}' is currently not executable (isExecutable=False).")

        uri = cmd_def.get("uri")
        
        if not uri:
             raise ValueError(f"Command '{command_name}' has no URI definition.")

        # 2. Local Parameter Validation (Helpful error messages)
        cmd_params_def = cmd_def.get("params", {})
        
        missing_params = []
        for param_name, param_info in cmd_params_def.items():
            if param_info.get("required", False):
                if param_name not in final_params:
                    missing_params.append(param_name)
                    continue

            if param_name in final_params:
                value = final_params[param_name]
                p_type = param_info.get("type")
                
                # Type Check
                if p_type == "number":
                    if not isinstance(value, (int, float)):
                         raise TypeError(f"Parameter '{param_name}' must be a number, got {type(value).__name__}")
                    
                    # Number Constraints
                    min_val = param_info.get("min")
                    if min_val is not None and value < min_val:
                         raise ValueError(f"Parameter '{param_name}' ({value}) is less than minimum ({min_val})")
                         
                    max_val = param_info.get("max")
                    if max_val is not None and value > max_val:
                         raise ValueError(f"Parameter '{param_name}' ({value}) is greater than maximum ({max_val})")

                elif p_type == "boolean":
                    if not isinstance(value, bool):
                         # Be strict about booleans to avoid ambiguity
                         raise TypeError(f"Parameter '{param_name}' must be a boolean, got {type(value).__name__}")

                elif p_type == "string":
                    if not isinstance(value, str):
                        raise TypeError(f"Parameter '{param_name}' must be a string, got {type(value).__name__}")
                        
                    # Enum Constraint
                    enum_vals = param_info.get("enum")
                    if enum_vals and value not in enum_vals:
                         raise ValueError(f"Parameter '{param_name}' ('{value}') is not a valid option. Allowed: {enum_vals}")
                    
                    # Regex Constraint
                    import re
                    regex_pattern = param_info.get("constraints", {}).get("regEx")
                    if regex_pattern:
                        if not re.match(regex_pattern, value):
                             raise ValueError(f"Parameter '{param_name}' ('{value}') does not match required pattern: {regex_pattern}")

        if missing_params:
            raise ValueError(
                f"Missing required parameters for command '{command_name}': {missing_params}. "
                f"Required: {[k for k,v in cmd_params_def.items() if v.get('required')]}"
            )

        print(f"[MOCK] Executing command '{command_name}' on feature '{feature.name}' with params: {final_params}")
        # In a real mock, we could update the local JSON/cache to reflect the change.
        # For now, just return success.
        return {"success": True, "reason": "Mock Execution"}
