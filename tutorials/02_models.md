# Tutorial 2: Data Models & Feature Expansion

This tutorial covers how `vi_api_client` represents data. The Viessmann API returns complex, nested JSON objects. Our goal is to make these easy to use for developers and integrations.

## 1. The Challenge

The API returns data in a raw format that separates values, properties, and metadata.
**Example Raw JSON:**
```json
{
  "feature": "heating.circuits.0.heating.curve",
  "properties": {
    "slope": { "value": 1.4, "type": "number" },
    "shift": { "value": 0, "type": "number" }
  }
}
```

A user just wants to know: "What is the slope?". They don't want to parse `properties["slope"]["value"]`.

## 2. The Solution: `models.py`

We use a Python class `Feature` to wrap this data.

### Encapsulation
The `Feature` class stores the raw data but provides properties to access it easily.
- `from_api(data)`: A factory method that creates a `Feature` object from the raw dict.
- `is_enabled`: Checks the "isEnabled" flag.
- `is_ready`: Checks the "isReady" flag.

### The `expand()` Method
This is the most important piece of logic. It "flattens" complex objects into simple key-value pairs.

**Logic Flow:**
1.  **Analyze Keys**: It looks at the keys in `properties`.
2.  **Identify Type**:
    - Is it a simple value (e.g. `properties: { "value": ... }`)? -> Keep as is.
    - Is it a composite (e.g. `slope` + `shift`)? -> Break it apart.
3.  **Generate Scalar Features**: It creates new, smaller `Feature` objects for each part.

**Example Transformation:**
`heating.curve` (Composite)
   ⬇️ `expand()`
1. `heating.curve.slope` = 1.4
2. `heating.curve.shift` = 0

### Code Highlight (`models.py`)

```python
    def expand(self) -> List["Feature"]:
        # Rule 1: It's a simple feature (e.g. just has 'value' and 'status'). 
        # Don't expand, just use it.
        if all(k in primary_keys for k in data_keys):
            return [self]
            
        # Rule 2: It's complex (e.g. 'slope', 'day', 'month').
        # Create a new sub-feature for each key.
        formatted = []
        for key in data_keys:
             formatted.append(self._create_sub_feature(key, ...))
        return formatted
```

## 3. Why this matters
This architecture decouples the **consumption** of data from the **structure** of the API.
- **Home Assistant** doesn't need to know that "heating curve" is a complex object. It just asks for "all features" and gets a list of sensors.
- **Maintenance**: If Viessmann changes the API structure, we only update `models.py`. The rest of the app (CLI, HA) stays the same.
