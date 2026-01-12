"""CLI for Viessmann Client."""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Optional, Dict, Any

import aiohttp
from vi_api_client import Client, MockViessmannClient, OAuth

# Default file to store tokens and config
TOKEN_FILE = "tokens.json"

logging.basicConfig(level=logging.INFO, format='%(message)s')
_LOGGER = logging.getLogger(__name__)

def load_config(token_file: str) -> Dict[str, Any]:
    """Load configuration from token file."""
    try:
        with open(token_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}



async def create_session(args) -> aiohttp.ClientSession:
    """Create aiohttp session with optional insecure SSL."""
    if args.insecure:
        print("WARNING: SSL verification disabled via --insecure")
        connector = aiohttp.TCPConnector(ssl=False)
        return aiohttp.ClientSession(connector=connector)
    return aiohttp.ClientSession()

async def cmd_login(args):
    """Handle login command."""
    client_id = args.client_id
    redirect_uri = args.redirect_uri
    
    
    auth = OAuth(client_id, redirect_uri, args.token_file)
    url = auth.get_authorization_url()
    
    print(f"Please visit the following URL to log in:\n\n{url}\n")
    print(f"After verifying, you will be redirected to {redirect_uri}?code=...")
    code = input("Paste the 'code' parameter from the URL here: ").strip()
    
    async with await create_session(args) as session:
        auth.websession = session
        await auth.async_fetch_details_from_code(code)
        
    print(f"Successfully authenticated! Tokens and config saved to {args.token_file}")

def get_client_config(args) -> tuple[str, str]:
    """Get client_id and redirect_uri from args or file."""
    config = load_config(args.token_file)
    
    client_id = args.client_id or os.getenv("VIESSMANN_CLIENT_ID") or config.get("client_id")
    redirect_uri = args.redirect_uri or os.getenv("VIESSMANN_REDIRECT_URI") or config.get("redirect_uri")
    
    if not client_id:
        print(f"Error: Client ID not found. Provide via --client-id or VIESSMANN_CLIENT_ID env var.")
        print("Please run 'login' first or provide --client-id.")
        sys.exit(1)
        
    return client_id, redirect_uri

def get_client_config_safe(args) -> tuple[str, str]:
    """Get config but return empty strings if missing (for mock mode)."""
    # For mock mode, we don't strictly need client_id, so we can be lenient.
    if args.mock_device:
        return "mock_id", "mock_uri"
    return get_client_config(args)

async def cmd_list_devices(args):
    """List installations and devices."""
    client_id, redirect_uri = get_client_config(args)

    async with await create_session(args) as session:
        auth = OAuth(client_id, redirect_uri, args.token_file, session)
        client = Client(auth)

        try:
            installations = await client.get_installations()
            print(f"Found {len(installations)} Installations:")
            for inst in installations:
                inst_id = inst.get("id")
                print(f"- Installation ID: {inst_id}")
                
            gateways = await client.get_gateways()
            print(f"\nFound {len(gateways)} Gateways:")
            for gw in gateways:
                gw_serial = gw.get("serial")
                inst_id = gw.get("installationId")
                print(f"- Gateway: {gw_serial} (Inst: {inst_id})")
                
                devices = await client.get_devices(inst_id, gw_serial)
                print(f"  Devices ({len(devices)}):")
                for dev in devices:
                    dev_id = dev.get("id")
                    dev_type = dev.get("deviceType")
                    model = dev.get("modelId")
                    print(f"  - Device: {dev_id} (Type: {dev_type}, Model: {model})")
                    
        except Exception as e:
            _LOGGER.error("Error listing devices: %s", e)

async def cmd_list_features(args):
    """List all features for a device."""
    client_id, redirect_uri = get_client_config_safe(args)

    async with await create_session(args) as session:
        auth = OAuth(client_id, redirect_uri, args.token_file, session)
        if args.mock_device:
            client = MockViessmannClient(args.mock_device, auth)
            # For mock client, we don't need real installation details,
            # but setting dummy defaults helps downstream logic
            inst_id = 99999
            gw_serial = "MOCK_GATEWAY_SERIAL"
            dev_id = "0"
            if not args.installation_id: args.installation_id = inst_id
            if not args.gateway_serial: args.gateway_serial = gw_serial
            if not args.device_id: args.device_id = dev_id
            print(f"Using Mock Device: {args.mock_device}")
        else:
            client = Client(auth)
        
        try:
            # Auto-discovery if IDs are missing
            inst_id = args.installation_id
            gw_serial = args.gateway_serial
            dev_id = args.device_id
            
            if not (inst_id and gw_serial and dev_id):
                gateways = await client.get_gateways()
                if not gateways:
                    print("No gateways found.")
                    return
                gw = gateways[0]
                gw_serial = gw.get("serial")
                inst_id = gw.get("installationId")
                
                devices = await client.get_devices(inst_id, gw_serial)
                if not devices:
                    print(f"No devices found on gateway {gw_serial}")
                    return
                # Default to device 0 if available, else first one
                target_dev = next((d for d in devices if d.get("id") == "0"), devices[0])
                dev_id = target_dev.get("id")
                print(f"Using Device: {dev_id} (Gateway: {gw_serial}, Inst: {inst_id})")

            
            if args.values:
                # Use model-based fetching to show flat/expanded features
                # accessible to the end user (simulating HA behavior)
                features_models = await client.get_features_models(inst_id, gw_serial, dev_id)
                # We create a dummy device to leverage the property (or just call expand manually)
                # But to fully verify, let's just iterate and expand
                
                print(f"Found {len(features_models)} Raw Features for device {dev_id}:")
                
                flat_list = []
                for f in features_models:
                    if args.enabled and not f.is_enabled:
                        continue
                    flat_list.extend(f.expand())
                    
                print(f"Expanded to {len(flat_list)} Flat Features:")
                for item in flat_list:
                     print(f"- {item.name}: {item.formatted_value}")
            
            else:
                # Standard listing (names only)
                if args.enabled:
                    features = await client.get_enabled_features(inst_id, gw_serial, dev_id)
                    print(f"Found {len(features)} Enabled Features for device {dev_id}:")
                else:
                    features = await client.get_features(inst_id, gw_serial, dev_id)
                    print(f"Found {len(features)} Features for device {dev_id}:")
                
                for f in features:
                    print(f"- {f.get('feature')}")
        except Exception as e:
            _LOGGER.error("Error listing features: %s", e)


async def cmd_get_feature(args):
    """Get a specific feature."""
    client_id, redirect_uri = get_client_config_safe(args)

    async with await create_session(args) as session:
        auth = OAuth(client_id, redirect_uri, args.token_file, session)
        if args.mock_device:
            client = MockViessmannClient(args.mock_device, auth)
            print(f"Using Mock Device: {args.mock_device}")
            # Mock defaults to skip full discovery
            if not args.installation_id: args.installation_id = 99999
            if not args.gateway_serial: args.gateway_serial = "MOCK_GATEWAY_SERIAL" 
            if not args.device_id: args.device_id = "0"
        else:
            client = Client(auth)
        
        try:
            # Auto-discovery if IDs are missing
            inst_id = args.installation_id
            gw_serial = args.gateway_serial
            dev_id = args.device_id
            
            if not (inst_id and gw_serial and dev_id):
                # We need to discover context
                # To capture stdout/logging if needed, but for simple CLI we just call methods
                gateways = await client.get_gateways()
                if not gateways:
                    print("No gateways found.")
                    return
                
                # Pick first gateway
                gw = gateways[0]
                gw_serial = gw.get("serial")
                inst_id = gw.get("installationId")
                
                # Pick priority device (0) over default first found
                devices = await client.get_devices(inst_id, gw_serial)
                if not devices:
                    print(f"No devices found on gateway {gw_serial}")
                    return
                
                target_dev = next((d for d in devices if d.get("id") == "0"), devices[0])
                dev_id = target_dev.get("id")

            feature_data = await client.get_feature(inst_id, gw_serial, dev_id, args.feature_name)
            
            if args.raw:
                print(json.dumps(feature_data, indent=2))
            else:
                from vi_api_client.models import Feature
                f_model = Feature.from_api(feature_data)
                expanded = f_model.expand()
                
                if not expanded:
                     # Fallback if it filters out everything (e.g. empty structural feature)
                     print(f"Feature '{args.feature_name}' exists but has no scalar values (Structural).")
                     print("Use --raw to see underlying structure.")
                
                for item in expanded:
                    print(f"- {item.name}: {item.formatted_value}")

        except Exception as e:
            _LOGGER.error("Error fetching feature: %s", e)

async def cmd_get_consumption(args):
    """Get consumption data."""
    client_id, redirect_uri = get_client_config(args)

    async with await create_session(args) as session:
        auth = OAuth(client_id, redirect_uri, args.token_file, session)
        client = Client(auth)
        
        try:
            # Auto-discovery if IDs are missing
            inst_id = args.installation_id
            gw_serial = args.gateway_serial
            dev_id = args.device_id
            
            if not (inst_id and gw_serial and dev_id):
                gateways = await client.get_gateways()
                if not gateways:
                    print("No gateways found.")
                    return
                
                gw = gateways[0]
                gw_serial = gw.get("serial")
                inst_id = gw.get("installationId")
                
                devices = await client.get_devices(inst_id, gw_serial)
                if not devices:
                    print(f"No devices found on gateway {gw_serial}")
                    return
                
                target_dev = next((d for d in devices if d.get("id") == "0"), devices[0])
                dev_id = target_dev.get("id")
                print(f"Using Device: {dev_id} (Gateway: {gw_serial}, Inst: {inst_id})")

            print(f"Fetching consumption (Metric: {args.metric})...")
            result = await client.get_today_consumption(gw_serial, dev_id, metric=args.metric)
            
            if isinstance(result, list):
                for f in result:
                     print(f"- {f.name}: {f.formatted_value}")
            else:
                print(f"- {result.name}: {result.formatted_value}")
                
        except Exception as e:
            _LOGGER.error("Error fetching consumption: %s", e)

async def cmd_exec(args):
    """Execute a command."""
    client_id, redirect_uri = get_client_config_safe(args)
    
    # Check if user provided JSON string (legacy/complex) or key=value pairs
    params = {}
    
    # args.params is now a list strings (nargs='*')
    # If first arg looks like JSON object, try to parse it as such
    if args.params and len(args.params) == 1 and args.params[0].strip().startswith("{"):
         try:
             params = json.loads(args.params[0])
         except json.JSONDecodeError:
             print("Error: Invalid JSON string provided.")
             return
    elif args.params:
        # Key=Value parsing
        for item in args.params:
            if "=" not in item:
                print(f"Error: Invalid argument format '{item}'. Expected key=value.")
                return
            key, val_str = item.split("=", 1)
            
            # Type inference
            value = val_str
            if val_str.lower() == "true":
                value = True
            elif val_str.lower() == "false":
                value = False
            else:
                try:
                    value = int(val_str)
                except ValueError:
                    try:
                        value = float(val_str)
                    except ValueError:
                        # Try parsing as JSON (e.g. for nested objects or lists)
                        if val_str.startswith("[") or val_str.startswith("{"):
                             try:
                                 value = json.loads(val_str)
                             except json.JSONDecodeError:
                                 pass # Keep as string
            
            params[key] = value

    async with await create_session(args) as session:
        auth = OAuth(client_id, redirect_uri, args.token_file, session)
        if args.mock_device:
            client = MockViessmannClient(args.mock_device, auth)
            print(f"Using Mock Device: {args.mock_device}")
            # Mock defaults
            if not args.installation_id: args.installation_id = 99999
            if not args.gateway_serial: args.gateway_serial = "MOCK_GATEWAY_SERIAL" 
            if not args.device_id: args.device_id = "0"
        else:
            client = Client(auth)
            
        try:
            # Auto-discovery (simplified from cmd_get_feature)
            inst_id = args.installation_id
            gw_serial = args.gateway_serial
            dev_id = args.device_id
            
            if not (inst_id and gw_serial and dev_id):
                 if not args.mock_device:
                    # Minimal discovery if needed for real API
                    gateways = await client.get_gateways()
                    if gateways:
                        gw_serial = gateways[0]["serial"]
                        inst_id = gateways[0]["installationId"]
                        devices = await client.get_devices(inst_id, gw_serial)
                        if devices:
                            # Prioritize device "0" (Heating System) over "gateway" or others
                            target_dev = next((d for d in devices if d.get("id") == "0"), devices[0])
                            dev_id = target_dev["id"]
                            print(f"Auto-selected device {dev_id} on {gw_serial}")

            if not (inst_id and gw_serial and dev_id):
                print("Could not determine context (installation/gateway/device). Please specify args.")
                return

            # 1. Fetch the feature to get metadata (url)
            print(f"Fetching feature '{args.feature_name}'...")
            feature_data = await client.get_feature(inst_id, gw_serial, dev_id, args.feature_name)
            
            from vi_api_client.models import Feature
            feature = Feature.from_api(feature_data)
            
            # 2. Execute
            print(f"Executing '{args.command_name}' with {params}...")
            result = await client.execute_command(feature, args.command_name, params)
            
            print("Success!")
            print(json.dumps(result, indent=2))

        except Exception as e:
            _LOGGER.error("Error executing command: %s", e)

async def cmd_list_commands(args):
    """List all available commands for a device."""
    client_id, redirect_uri = get_client_config_safe(args)

    async with await create_session(args) as session:
        auth = OAuth(client_id, redirect_uri, args.token_file, session)
        if args.mock_device:
            client = MockViessmannClient(args.mock_device, auth)
            print(f"Using Mock Device: {args.mock_device}")
            if not args.installation_id: args.installation_id = 99999
            if not args.gateway_serial: args.gateway_serial = "MOCK_GATEWAY_SERIAL" 
            if not args.device_id: args.device_id = "0"
        else:
            client = Client(auth)
            
        try:
            # Auto-discovery
            inst_id = args.installation_id
            gw_serial = args.gateway_serial
            dev_id = args.device_id
            
            if not (inst_id and gw_serial and dev_id):
                 if not args.mock_device:
                    gateways = await client.get_gateways()
                    if gateways:
                        gw_serial = gateways[0]["serial"]
                        inst_id = gateways[0]["installationId"]
                        devices = await client.get_devices(inst_id, gw_serial)
                        if devices:
                             # Prioritize device "0" (Heating System)
                            target_dev = next((d for d in devices if d.get("id") == "0"), devices[0])
                            dev_id = target_dev["id"]
                            print(f"Using Device: {dev_id} (Gateway: {gw_serial}, Inst: {inst_id})")

            # Fetch all features (using models/raw mostly equivalent here as propertes are always loaded)
            # using get_features_models to get Feature objects directly
            features = await client.get_features_models(inst_id, gw_serial, dev_id)
            
            commandable_features = [f for f in features if f.commands]
            
            print(f"\nFound {len(commandable_features)} features with commands:\n")
            
            for f in commandable_features:
                print(f"Feature: {f.name}")
                for cmd_name, cmd_def in f.commands.items():
                    print(f"  Command: {cmd_name}")
                    params = cmd_def.get("params", {})
                    if not params:
                        print("    (No parameters)")
                    else:
                        for p_name, p_def in params.items():
                            req_str = "*" if p_def.get("required") else ""
                            type_str = p_def.get("type", "unknown")
                            constraints = []
                            if "min" in p_def: constraints.append(f"min={p_def['min']}")
                            if "max" in p_def: constraints.append(f"max={p_def['max']}")
                            if "stepping" in p_def: constraints.append(f"step={p_def['stepping']}")
                            if "enum" in p_def: constraints.append(f"enum={p_def['enum']}")
                            
                            constr_str = f" [{', '.join(constraints)}]" if constraints else ""
                            print(f"    - {p_name}{req_str} ({type_str}){constr_str}")
                print("")

        except Exception as e:
            _LOGGER.error("Error listing commands: %s", e)

def cmd_list_mock_devices(args):
    """List available mock devices."""
    devices = MockViessmannClient.get_available_mock_devices()
    print("Available Mock Devices:")
    for d in devices:
        print(f"- {d}")

def main():
    """Main CLI entrypoint."""
    # Parent parser for common arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--client-id", help="OAuth Client ID (optional if saved)")
    common_parser.add_argument("--redirect-uri", default="http://localhost:4200/", help="OAuth Redirect URI")
    common_parser.add_argument("--token-file", default=TOKEN_FILE, help="Path to save/load tokens")
    common_parser.add_argument("--insecure", action="store_true", help="Disable SSL verification")
    common_parser.add_argument("--mock-device", help="Use a mock device (e.g. Vitodens200W)")

    parser = argparse.ArgumentParser(description="Viessmann API CLI")
    subparsers = parser.add_subparsers(dest="command")

    
    # Login
    parser_login = subparsers.add_parser("login", help="Authenticate with Viessmann", parents=[common_parser])
    
    # List Devices
    parser_list = subparsers.add_parser("list-devices", help="List installations and devices", parents=[common_parser])

    # List Features
    parser_features = subparsers.add_parser("list-features", help="List all features for a device", parents=[common_parser])
    parser_features.add_argument("--installation-id", type=int, help="Installation ID (optional)")
    parser_features.add_argument("--gateway-serial", help="Gateway Serial (optional)")
    parser_features.add_argument("--device-id", help="Device ID (optional)")
    parser_features.add_argument("--enabled", action="store_true", help="List only enabled features")
    parser_features.add_argument("--values", action="store_true", help="Show feature values")
    
    # Get Feature
    parser_feature = subparsers.add_parser("get-feature", help="Get a specific feature", parents=[common_parser])
    parser_feature.add_argument("feature_name", help="Feature Name (e.g. heating.circuits.0)")
    parser_feature.add_argument("--installation-id", type=int, help="Installation ID (optional)")
    parser_feature.add_argument("--gateway-serial", help="Gateway Serial (optional)")
    parser_feature.add_argument("--device-id", help="Device ID (optional)")
    parser_feature.add_argument("--raw", action="store_true", help="Show raw JSON response")
    
    # Get Consumption
    parser_consumption = subparsers.add_parser("get-consumption", help="Get energy consumption for today", parents=[common_parser])
    parser_consumption.add_argument("--metric", default="summary", choices=["summary", "total", "heating", "dhw"], help="Metric to fetch")
    parser_consumption.add_argument("--installation-id", type=int, help="Installation ID (optional)")
    parser_consumption.add_argument("--gateway-serial", help="Gateway Serial (optional)")
    parser_consumption.add_argument("--device-id", help="Device ID (optional)")
    
    # List available mock devices
    subparsers.add_parser("list-mock-devices", help="List available mock devices", parents=[common_parser])
    
    # List Commands
    parser_cmds = subparsers.add_parser("list-commands", help="List all available commands for a device", parents=[common_parser])
    parser_cmds.add_argument("--installation-id", type=int, help="Installation ID (optional)")
    parser_cmds.add_argument("--gateway-serial", help="Gateway Serial (optional)")
    parser_cmds.add_argument("--device-id", help="Device ID (optional)")

    # Exec Command
    parser_exec = subparsers.add_parser("exec", help="Execute a command on a feature (e.g. set curve)", parents=[common_parser])
    parser_exec.add_argument("feature_name", help="Feature Name (e.g. heating.circuits.0.heating.curve)")
    parser_exec.add_argument("command_name", help="Command Name (e.g. setCurve)")
    parser_exec.add_argument("params", nargs="*", help="Parameters (key=value OR single JSON string)")
    parser_exec.add_argument("--installation-id", type=int, help="Installation ID (optional)")
    parser_exec.add_argument("--gateway-serial", help="Gateway Serial (optional)")
    parser_exec.add_argument("--device-id", help="Device ID (optional)")


    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "login":
            if not args.client_id and not os.getenv("VIESSMANN_CLIENT_ID"):
                # Check config one last time before failing
                config = load_config(args.token_file)
                if not config.get("client_id"):
                    print("Error: --client-id is required for initial login (or use VIESSMANN_CLIENT_ID env var).")
                    sys.exit(1)
            asyncio.run(cmd_login(args))
        elif args.command == "list-devices":
            asyncio.run(cmd_list_devices(args))
        elif args.command == "list-features":
            asyncio.run(cmd_list_features(args))
        elif args.command == "get-feature":
            asyncio.run(cmd_get_feature(args))
        elif args.command == "get-consumption":
            asyncio.run(cmd_get_consumption(args))
        elif args.command == "list-mock-devices":
            cmd_list_mock_devices(args)
        elif args.command == "list-commands":
            asyncio.run(cmd_list_commands(args))
        elif args.command == "exec":
            asyncio.run(cmd_exec(args))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
