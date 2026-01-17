# app.py (Further Prompt Refinement for Species/Status Accuracy)

import os
import json
import google.generativeai as genai
import geopandas as gpd
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import warnings
from flask_cors import CORS

# --- Configuration & Initialization ---
# ... (Same as before: load_dotenv, warnings, app, CORS, API_KEY, CSV_FILE_PATH, MAX_FEATURES_RETURNED) ...
load_dotenv()
warnings.filterwarnings("ignore", category=FutureWarning)
app = Flask(__name__)
CORS(app)
API_KEY = os.getenv("GEMINI_API_KEY")
CSV_FILE_PATH = "nyc_tree_census_2005.csv"
MAX_FEATURES_RETURNED = 100000

if not API_KEY: raise ValueError("GEMINI_API_KEY not set.")
# ... (Same genai configuration, model definition) ...
genai.configure(api_key=API_KEY)
generation_config = {"temperature": 0.2, "top_p": 1, "top_k": 1, "max_output_tokens": 2048, "response_mime_type": "application/json"}
safety_settings = [ {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
model = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config, safety_settings=safety_settings)

trees_gdf = None

# --- Data Loading and Preparation (Unchanged from previous) ---
def load_and_prepare_data(csv_path):
    # ... (Same as the version that included coordinate cleaning) ...
    global trees_gdf
    try:
        print(f"Loading data from {csv_path}...")
        try: df = pd.read_csv(csv_path, encoding='utf-8', low_memory=False)
        except UnicodeDecodeError: print("UTF-8 failed, trying latin-1..."); df = pd.read_csv(csv_path, encoding='latin-1', low_memory=False)
        print(f"Loaded {len(df)} rows.")
        if 'tree_dbh' in df.columns: print("Converting 'tree_dbh' to numeric..."); df['tree_dbh'] = pd.to_numeric(df['tree_dbh'], errors='coerce')
        else: print("Warning: 'tree_dbh' column not found.")
        if 'latitude' in df.columns and 'longitude' in df.columns:
            print("Validating and cleaning coordinates..."); df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce'); df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
            original_count = len(df); df = df.dropna(subset=['latitude', 'longitude']); df = df[(df['latitude'].between(-90, 90)) & (df['longitude'].between(-180, 180))]; epsilon = 0.0001; df = df[~((df['latitude'].abs() < epsilon) & (df['longitude'].abs() < epsilon))]
            valid_coord_count = len(df);
            if original_count > valid_coord_count: print(f"Removed {original_count - valid_coord_count} rows with invalid/missing/zero coordinates.")
            print("Converting to GeoDataFrame..."); trees_gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326"); print(f"GeoDataFrame created successfully with {len(trees_gdf)} features.")
        else: print("Error: Could not find 'latitude' and 'longitude' columns."); trees_gdf = None
    except FileNotFoundError: print(f"Error: Data file not found at {csv_path}"); trees_gdf = None
    except Exception as e: print(f"Error loading or processing data: {e}"); trees_gdf = None


# --- LLM Prompting Function (REFINED AGAIN) ---
def get_filter_criteria_from_llm(user_prompt):
    """Sends the user prompt to Gemini and asks for structured filter criteria for NYC trees."""

    # --- UPDATED: Added more explicit examples and strictness ---
    available_properties_info = """
    - status (string): Condition of the tree. MUST use one of these exact values: 'Good', 'Poor', 'Excellent', 'Dead'.
    - tree_dbh (number): Diameter in inches. Supports >, <, >=, <=, ==. Assumes > 0 unless specified.
    - spc_common (string): Common species name. Use '==' comparison. MUST follow the 'PRIMARY, VARIETY' format when applicable. Case MUST match examples EXACTLY.
        - Examples:
            - User says 'pin oak' -> Return value 'OAK, PIN'
            - User says 'norway maple' -> Return value 'MAPLE, NORWAY'
            - User says 'callery pear' -> Return value 'PEAR, CALLERY'
            - User says 'honeylocust' -> Return value 'honeylocust' (single name)
            - User says 'sycamore' -> Return value 'LONDON PLANETREE' (Special case)
    - boroname (string): Borough name ('Brooklyn', 'Manhattan', 'Bronx', 'Queens', 'Staten Island'). Map 'Staten Island' to value '5'. Use '==' comparison.
    - zipcode (string): 5-digit zip code. Use '==' comparison.
    - address (string): Street address. Use '==' comparison only if specific address given.
    - sidw_crack (string): Sidewalk cracking ('Yes'/'No'). Map presence/absence queries to exact 'Yes'/'No'. Use '=='.
    - inf_wires (string): Wire conflicts ('Yes'/'No'). Map presence/absence queries to exact 'Yes'/'No'. Use '=='.
    - trunk_dmg (string): Trunk damage ('Yes'/'No'). Map presence/absence queries to exact 'Yes'/'No'. Use '=='.
    """

    prompt = f"""
    Analyze the following user query about NYC street trees (2005 census). STRICTLY follow the formatting and value rules provided.
    Available properties for filtering are:
    {available_properties_info}

    Extract filtering criteria based *only* on these properties.
    Return criteria as a JSON object: {{"filters": [{{"field": "...", "operator": "...", "value": "..."}}]}}.
    - For 'status', 'spc_common', 'boroname', 'sidw_crack', 'inf_wires', 'trunk_dmg', the 'value' in the JSON MUST EXACTLY match the specified formats and examples (including case). Use operator '=='.
    - For 'zipcode' and 'address', use operator '==' with the value provided by the user.
    - For 'tree_dbh', use numeric operators (>, <, >=, <=, ==) and convert values to numbers. Assume tree_dbh > 0 if operator is > or >=.
    - If no filters match, return {{"filters": []}}.

    Example Query: "Show Callery Pear excellent trees smaller than 4 inches diameter"
    Example JSON Output:
    {{
      "filters": [
        {{ "field": "spc_common", "operator": "==", "value": "PEAR, CALLERY" }},
        {{ "field": "status", "operator": "==", "value": "Excellent" }},
        {{ "field": "tree_dbh", "operator": "<", "value": 4 }}
      ]
    }}

    Example Query: "Map trees with no wire conflicts"
    Example JSON Output:
    {{
      "filters": [
        {{ "field": "inf_wires", "operator": "==", "value": "No" }}
      ]
    }}

    User Query: "{user_prompt}"

    JSON Output:
    """
    # ... (LLM call and error handling remain the same) ...
    try:
        print(f"\nSending prompt to Gemini:\n---\nUser Query: {user_prompt}\n---")
        response = model.generate_content(prompt)
        print(f"Received response text from Gemini:\n---\n{response.text}\n---")
        criteria = json.loads(response.text)
        if isinstance(criteria, dict) and isinstance(criteria.get("filters"), list):
             print(f"Parsed criteria: {criteria}"); return criteria
        else: print(f"Warning: Unexpected JSON structure: {criteria}"); return {"filters": []}
    except json.JSONDecodeError as e: print(f"Error decoding JSON: {e}\nRaw: {response.text}"); return None
    except Exception as e: print(f"Error calling Gemini API: {e}"); return None


# --- Data Filtering Function (Unchanged from previous) ---
def filter_geodataframe(gdf, criteria):
    # ... (Same as the version with default DBH filter and binary field handling) ...
    if gdf is None: print("Error: GeoDataFrame not loaded."); return None
    if criteria is None or not criteria.get("filters"):
        print("No filters to apply.");
        if 'tree_dbh' in gdf.columns and pd.api.types.is_numeric_dtype(gdf['tree_dbh']): print("Applying default filter: tree_dbh > 0"); return gdf[gdf['tree_dbh'] > 0].copy()
        return gdf.copy()
    filtered_gdf = gdf.copy(); print(f"Applying filters: {criteria['filters']}")
    has_dbh_filter = any(f.get('field') == 'tree_dbh' for f in criteria['filters'])
    if not has_dbh_filter and 'tree_dbh' in filtered_gdf.columns and pd.api.types.is_numeric_dtype(filtered_gdf['tree_dbh']):
        print("Applying default filter: tree_dbh > 0"); initial_size = len(filtered_gdf)
        filtered_gdf = filtered_gdf[filtered_gdf['tree_dbh'] > 0]
        print(f"Filtered {initial_size - len(filtered_gdf)} rows with tree_dbh <= 0. Size now: {len(filtered_gdf)}")
    for f in criteria["filters"]:
        field, op, value = f.get("field"), f.get("operator"), f.get("value")
        if not all([field, op, value is not None]): print(f"Skipping invalid filter: {f}"); continue
        if field not in filtered_gdf.columns: print(f"Warning: Field '{field}' not found."); continue
        try:
            col = filtered_gdf[field]; current_mask = None
            string_fields = ['status', 'spc_common', 'boroname', 'zipcode', 'address']
            binary_fields = ['sidw_crack', 'inf_wires', 'trunk_dmg']
            if field in string_fields or field in binary_fields:
                if op == "==": current_mask = col.astype(str).str.lower() == str(value).lower() # Backend still uses lower() for robustness
                else: print(f"Unsupported op '{op}' for string/binary field '{field}'."); continue
            elif field == 'tree_dbh':
                 try:
                    numeric_value = float(value); sql_op = "=" if op == "==" else op
                    if sql_op == "=": current_mask = (col == numeric_value)
                    elif sql_op == ">": current_mask = (col > numeric_value)
                    elif sql_op == "<": current_mask = (col < numeric_value)
                    elif sql_op == ">=": current_mask = (col >= numeric_value)
                    elif sql_op == "<=": current_mask = (col <= numeric_value)
                    else: print(f"Unsupported numeric op '{op}'."); continue
                    current_mask = current_mask.fillna(False)
                 except ValueError: print(f"Cannot convert value '{value}' to numeric."); continue
            else: print(f"Filtering not implemented for field '{field}'."); continue
            if current_mask is not None:
                 rows_before = len(filtered_gdf); filtered_gdf = filtered_gdf[current_mask]
                 rows_after = len(filtered_gdf); print(f"Filter: {field} {op} {value} -> {rows_after} rows remain ({rows_before - rows_after} removed)")
                 if filtered_gdf.empty: print("Filtered DataFrame empty. Stopping."); break
        except Exception as e: print(f"Error applying filter {f}: {e}."); continue
    print(f"Filtering complete. Size before limit: {len(filtered_gdf)} features.")
    return filtered_gdf


# --- Flask API Endpoint (Unchanged from previous) ---
@app.route('/')
def serve_index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS)"""
    return send_from_directory('.', filename)

@app.route('/query', methods=['POST'])
def handle_query():
    # ... (Same as the version with feature limit and metadata addition) ...
    global trees_gdf
    if trees_gdf is None: print("Data not loaded. Attempting load..."); load_and_prepare_data(CSV_FILE_PATH);
    if trees_gdf is None: return jsonify({"error": "Tree data unavailable."}), 500
    data = request.get_json();
    if not data or 'prompt' not in data: return jsonify({"error": "Missing 'prompt'."}), 400
    user_prompt = data['prompt']; print(f"\n--- Received Query ---\nUser Prompt: {user_prompt}")
    criteria = get_filter_criteria_from_llm(user_prompt)
    if criteria is None: return jsonify({"error": "LLM filter criteria failure."}), 500
    filtered_result_gdf = filter_geodataframe(trees_gdf, criteria)
    metadata = {'results_limited': False}
    if filtered_result_gdf is not None and not filtered_result_gdf.empty:
        num_results = len(filtered_result_gdf)
        if num_results > MAX_FEATURES_RETURNED:
            print(f"Warning: Query matched {num_results}, applying limit {MAX_FEATURES_RETURNED}.")
            metadata['results_limited'] = True; metadata['original_count'] = num_results; metadata['limit_applied'] = MAX_FEATURES_RETURNED
            filtered_result_gdf = filtered_result_gdf.head(MAX_FEATURES_RETURNED).copy()
            print(f"Returning limited set: {len(filtered_result_gdf)} features.")
        filtered_result_gdf = filtered_result_gdf[filtered_result_gdf.geometry.notna()]
        if not filtered_result_gdf.empty:
             filtered_result_gdf = filtered_result_gdf.replace({np.nan: None})
             result_geojson = json.loads(filtered_result_gdf.to_json())
             result_geojson['metadata'] = metadata
             print(f"Returning {len(filtered_result_gdf)} features.")
        else: result_geojson = {"type": "FeatureCollection", "features": [], "metadata": metadata}; print("No features with valid geometry.")
    else: result_geojson = {"type": "FeatureCollection", "features": [], "metadata": metadata}; print("No matching features or filtering error.")
    return jsonify(result_geojson)


# --- Main Execution ---
if __name__ == '__main__':
    load_and_prepare_data(CSV_FILE_PATH)
    app.run(host='0.0.0.0', port=5001, debug=True)