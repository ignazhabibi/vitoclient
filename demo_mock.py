"""
Viessmann Library Demo Application.

This script demonstrates the three layers of data abstraction provided by the library:
1. RAW Layer: Direct JSON from API.
2. MODEL Layer: Python Objects with helper methods.
3. FLAT Layer: Validated, simplified key-value pairs (Home Assistant style).
"""

import asyncio
import logging
import sys
import os
import json
import aiohttp

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from vi_api_client import MockViessmannClient, OAuth

# Configure formatted logging
logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

async def main():
    print("🚀 Viessmann Library - Layer Demo")
    print("=================================\n")

    # 1. Initialization (using Mock for reliable demo execution)
    # ----------------------------------------------------------
    print("1. Initialization")
    # minimal auth dummy
    auth = OAuth("client_id", "redirect_url", "tokens.json") 
    client = MockViessmannClient("Vitodens200W", auth)
    
    # Context (Mock IDs)
    inst_id = 123
    gw_serial = "1234567890123456"
    dev_id = "0"
    
    TARGET_FEATURE = "heating.circuits.0.heating.curve"

    # 2. Layer 1: RAW Data
    # --------------------
    print(f"\n2. RAW Layer (get_feature)")
    print("   -> Returns the raw JSON dictionary exactly as the API delivers it.")
    raw_json = await client.get_feature(inst_id, gw_serial, dev_id, TARGET_FEATURE)
    print(f"   Type: {type(raw_json)}")
    print("   Content (Snippet):")
    print(json.dumps(raw_json, indent=2))
    
    # 3. Layer 2: MODEL Data
    # ----------------------
    print(f"\n3. MODEL Layer (get_features_models / Feature.from_api)")
    print("   -> Returns a Python object encapsulating the data and logic.")
    # We can convert raw data to model directly or fetch it
    from vi_api_client.models import Feature
    feature_model = Feature.from_api(raw_json)
    
    print(f"   Type: {type(feature_model)}")
    print(f"   Object: {feature_model}")
    print(f"   Name: {feature_model.name}")
    print(f"   Properties (Keys): {list(feature_model.properties.keys())}")
    print("   -> Note: Still encapsulates the complex structure (slope, shift in one object).")

    # 4. Layer 3: FLAT / EXPANDED Layer
    # ---------------------------------
    print(f"\n4. FLAT Layer (expand())")
    print("   -> Returns a list of simple, scalar features ready for UIs/Sensors.")
    
    flat_features = feature_model.expand()
    print(f"   Type: {type(flat_features)} of List[Feature]")
    print(f"   Count: {len(flat_features)}")
    
    for f in flat_features:
        print(f"   - Entity: {f.name:<45} | Value: {f.formatted_value}")

    print("\n   -> This is what Home Assistant uses to generate sensors.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
