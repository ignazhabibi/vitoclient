"""Viessmann API Client."""

from typing import Any, Dict, List, Union

from .auth import AbstractAuth
from .const import ENDPOINT_INSTALLATIONS, ENDPOINT_GATEWAYS, ENDPOINT_ANALYTICS_THERMAL, API_BASE_URL
from .exceptions import ViConnectionError
from .models import Device, Feature

class Client:
    """Client for Viessmann API."""

    def __init__(self, auth: AbstractAuth) -> None:
        """Initialize the client."""
        self.auth = auth

    async def get_installations(self) -> List[Dict[str, Any]]:
        """Get list of installations."""
        url = f"{API_BASE_URL}{ENDPOINT_INSTALLATIONS}"
        async with await self.auth.request("GET", url) as resp:
            if resp.status != 200:
                raise ViConnectionError(f"Error fetching installations: {resp.status}")
            data = await resp.json()
            return data.get("data", [])

    async def get_gateways(self) -> List[Dict[str, Any]]:
        """Get list of gateways."""
        url = f"{API_BASE_URL}{ENDPOINT_GATEWAYS}"
        async with await self.auth.request("GET", url) as resp:
            if resp.status != 200:
                raise ViConnectionError(f"Error fetching gateways: {resp.status}")
            data = await resp.json()
            return data.get("data", [])

    async def get_devices(self, installation_id: int, gateway_serial: str) -> List[Dict[str, Any]]:
        """Get devices for a specific gateway."""
        url = f"{API_BASE_URL}{ENDPOINT_INSTALLATIONS}/{installation_id}/gateways/{gateway_serial}/devices"
        async with await self.auth.request("GET", url) as resp:
            if resp.status != 200:
                # 404 might mean no devices or wrong IDs
                text = await resp.text()
                raise ViConnectionError(f"Error fetching devices: {resp.status} - {text}")
            data = await resp.json()
            return data.get("data", [])

    async def get_features(self, installation_id: int, gateway_serial: str, device_id: str) -> List[Dict[str, Any]]:
        """Get all features for a device."""
        url = f"{API_BASE_URL}/iot/v2/features/installations/{installation_id}/gateways/{gateway_serial}/devices/{device_id}/features"
        async with await self.auth.request("GET", url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ViConnectionError(f"Error fetching features: {resp.status} - {text}")
            data = await resp.json()
            # The API response structure for features usually wraps them in 'data' list
            return data.get("data", [])
    
    async def get_feature(
        self, installation_id: int, gateway_serial: str, device_id: str, feature_name: str
    ) -> Dict[str, Any]:
        """Get a specific feature."""
        # Note: Sending a request for a specific feature by name is usually done by appending it to the URL
        # e.g. .../features/heating.circuits.0
        url = f"{API_BASE_URL}/iot/v2/features/installations/{installation_id}/gateways/{gateway_serial}/devices/{device_id}/features/{feature_name}"
        async with await self.auth.request("GET", url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ViConnectionError(f"Error fetching feature {feature_name}: {resp.status} - {text}")
            data = await resp.json()
            return data.get("data", {})

    async def get_enabled_features(self, installation_id: int, gateway_serial: str, device_id: str) -> List[Dict[str, Any]]:
        """Get only enabled features for a device.
        
        This includes the full feature object with properties and values.
        """
        features = await self.get_features(installation_id, gateway_serial, device_id)
        return [f for f in features if f.get("isEnabled")]

    async def get_features_with_values(
        self, installation_id: int, gateway_serial: str, device_id: str, only_enabled: bool = True
    ) -> List[Dict[str, str]]:
        """Get features with their formatted values nicely extracted.
        
        Returns a list of dicts with 'name' and 'value' keys.
        """
        if only_enabled:
            features = await self.get_enabled_features(installation_id, gateway_serial, device_id)
        else:
            features = await self.get_features(installation_id, gateway_serial, device_id)
            
        results = []
        for f in features:
            feature_model = Feature.from_api(f)
            # Expand potentially complex features
            for flat_f in feature_model.expand():
                results.append({
                    "name": flat_f.name, 
                    "value": flat_f.formatted_value
                })
            
        return results

    async def get_features_models(
        self, installation_id: int, gateway_serial: str, device_id: str
    ) -> List[Feature]:
        """Get all features as typed objects."""
        features = await self.get_features(installation_id, gateway_serial, device_id)
        return [Feature.from_api(f) for f in features]
        
    async def get_devices_models(
        self, installation_id: int, gateway_serial: str
    ) -> List[Device]:
        """Get devices as typed objects."""
        devices = await self.get_devices(installation_id, gateway_serial)
        return [
            Device.from_api(d, gateway_serial, installation_id) 
            for d in devices
        ]

    async def get_full_installation_status(
        self, installation_id: int
    ) -> List[Device]:
        """Fetch full status of an installation (Gateways -> Devices -> Features).
        
        This is designed for the UpdateCoordinator pattern to fetch everything in one go.
        
        Returns a hierarchical structure:
        List[Device]
          -> Device (with properties like ID, Model, Connectivity)
             -> Features (List of Feature Models, containing commands/constraints)
             -> Features Flat (Flattened list for easy property access)
        """
        gateways = await self.get_gateways()
        all_devices = []
        
        for gw in gateways:
            gw_serial = gw["serial"]
            # Get devices for this gateway
            devices = await self.get_devices_models(installation_id, gw_serial)
            
            for device in devices:
                # Fetch features for each device
                features = await self.get_features_models(installation_id, gw_serial, device.id)
                device.features = features
                all_devices.append(device)
                
        return all_devices
    
    async def execute_command(
        self,
        feature: Feature,
        command_name: str,
        params: Dict[str, Any] = {},
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a command on a feature.
        
        Supports passing parameters as a dictionary OR as keyword arguments.
        
        Example:
            client.execute_command(feat, "setCurve", slope=1.4, shift=0)
            
        :param feature: The Feature object containing the command definition.
        :param command_name: The name of the command to execute (e.g. 'setCurve').
        :param params: Dictionary of parameters for the command (optional).
        :param kwargs: parameters passed as keyword arguments (merged with params).
        :return: Response from the API (usually success status).
        """
        # Merge params
        final_params = params.copy()
        final_params.update(kwargs)

        # 1. Validate command exists
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

        # 3. Execute POST
        async with await self.auth.request("POST", uri, json=final_params) as resp:
            if resp.status not in [200, 201, 202]:
                text = await resp.text()
                raise ViConnectionError(
                    f"Error executing command '{command_name}': {resp.status} - {text}"
                )
            return await resp.json()

    async def get_today_consumption(
        self,
        gateway_serial: str,
        device_id: str,
        metric: str = "summary"
    ) -> Union[Feature, List[Feature]]:
        """Fetch energy consumption for the current day.
        
        Convenience wrapper around the Analytics API.
        
        :param metric: One of 'summary', 'total', 'heating', 'dhw'.
                       'summary' returns a List of all 3 features (efficient).
                       Others return a single Feature object.
        :return: Feature object or List of Feature objects.
        """
        from datetime import datetime
        
        # Calculate start/end for "Today"
        now = datetime.now()
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end_dt = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
        
        # Map metric to API property names
        mapping = {
            "total": "heating.power.consumption.total",
            "heating": "heating.power.consumption.heating",
            "dhw": "heating.power.consumption.dhw"
        }
        
        if metric == "summary":
            properties = list(mapping.values())
        elif metric in mapping:
            properties = [mapping[metric]]
        else:
            raise ValueError(f"Invalid metric: {metric}. Must be 'summary', 'total', 'heating', or 'dhw'.")
        
        # Reuse the generic fetcher
        raw_data = await self.get_aggregated_consumption(
            gateway_serial, device_id, start_dt, end_dt, properties, resolution="1d"
        )
        
        # Parse response based on actual structure:
        # { "data": { "data": { "summary": { "prop": value, ... } } } }
        features = []
        
        # Navigate to summary dict
        data_block = raw_data.get("data", {}).get("data", {})
        summary = data_block.get("summary", {})
        
        for prop_name in properties:
            # Extract value directly from summary dict
            val = summary.get(prop_name, 0.0)
            
            f = Feature(
                name=f"analytics.{prop_name}",
                properties={"value": {"value": val, "unit": "kilowattHour"}}, 
                is_enabled=True,
                is_ready=True
            )
            features.append(f)
            
        if metric != "summary" and len(features) == 1:
            return features[0]
            
        return features

    async def get_aggregated_consumption(
        self,
        gateway_serial: str,
        device_id: str,
        start_dt: str,
        end_dt: str,
        properties: List[str],
        resolution: str = "1d"
    ) -> Dict[str, Any]:
        """Fetch aggregated energy data from the Analytics API (Raw Access)."""
        url = f"{API_BASE_URL}{ENDPOINT_ANALYTICS_THERMAL}"
        
        payload = {
            "gateway_id": gateway_serial,
            "device_id": str(device_id),
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "properties": properties,
            "resolution": resolution
        }
        
        async with await self.auth.request("POST", url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ViConnectionError(f"Error fetching analytics: {resp.status} - {text}")
            return await resp.json()
