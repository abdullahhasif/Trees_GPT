# test_api.py (Updated with focused prompts)

import requests
import json
import time

API_URL = "http://127.0.0.1:5001/query"

# --- Define focused test queries ---
prompts_to_test = [
    # Basic attribute
    "Show Good status trees",
    # Test specific species name formatting correction
    "Find pin oak trees",
    # Test specific species name mapping (sycamore -> planetree)
    "Any sycamore trees in Queens?",
    # Basic numeric filter
    "Map trees with diameter greater than 40 inches",
    # Combined filter (Attribute + Numeric + Species Mapping)
    "Show me Good sycamore trees larger than 10 inches",
    # Test boroname mapping again
    "How many dead trees in Staten Island?",
    # Test no specific filter
    "show all trees please"
]

# --- Loop through prompts and send requests ---
for prompt in prompts_to_test:
    print(f"\n{'='*15} Testing Prompt: '{prompt}' {'='*15}")
    payload = {"prompt": prompt}
    start_time = time.time() # Start timer

    try:
        response = requests.post(API_URL, json=payload, timeout=60) # Added timeout
        end_time = time.time() # End timer
        duration = end_time - start_time

        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {duration:.2f} seconds")

        if response.status_code == 200:
            try:
                geojson_response = response.json()
                print(f"Response Type: {type(geojson_response)}")

                if isinstance(geojson_response, dict) and geojson_response.get("type") == "FeatureCollection":
                    num_features = len(geojson_response.get("features", []))
                    print(f"Received GeoJSON FeatureCollection with {num_features} features.")
                    # Example output for the first feature if results exist
                    if num_features > 0:
                        first_props = geojson_response["features"][0].get("properties", {})
                        print(f"  -> Example Feature Props: status='{first_props.get('status')}', spc_common='{first_props.get('spc_common')}', tree_dbh='{first_props.get('tree_dbh')}', boroname='{first_props.get('boroname')}'")

                else:
                     print(f"Received unexpected JSON structure: {geojson_response}")

            except json.JSONDecodeError:
                print("Error: Could not decode JSON response from server.")
                print(f"Raw Response Text (first 500 chars): {response.text[:500]}...")
        else:
            print(f"Error: Server returned status code {response.status_code}")
            try:
                 error_details = response.json()
                 print(f"Server Error Details: {error_details}")
            except json.JSONDecodeError:
                 print(f"Server Response Text (first 500 chars): {response.text[:500]}...")


    except requests.exceptions.Timeout:
         print("Error: The request timed out after 60 seconds.")
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to API: {e}")

    print(f"{'='*60}")

print("\nFocused testing complete.")