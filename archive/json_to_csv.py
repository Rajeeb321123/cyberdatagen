import json
import os
from pathlib import Path

import pandas as pd


def convert_json_to_csv(json_dir, csv_dir):
    """
    Convert all JSON files in json_dir to CSV files in csv_dir.
    
    Args:
        json_dir (Path): Directory containing JSON files
        csv_dir (Path): Directory to save CSV files
    """
    # Ensure the CSV directory exists
    csv_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all JSON files in the directory
    json_files = list(json_dir.glob('*.json'))
    
    if not json_files:
        print(f"No JSON files found in {json_dir}")
        return
    
    print(f"Found {len(json_files)} JSON files to convert")
    
    # Process each JSON file
    for json_file in json_files:
        try:
            convert_single_json_to_csv(json_file, csv_dir / f"{json_file.stem}.csv")
            print(f"Converted {json_file.name} to CSV")
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    print(f"CSV conversion complete. Files saved to {csv_dir}")


def convert_single_json_to_csv(json_file_path, csv_file_path):
    """
    Convert a single JSON file to CSV.
    
    Args:
        json_file_path (Path): Path to the JSON file
        csv_file_path (Path): Path to save the CSV file
    """
    # Load the JSON data
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    examples = data.get('examples', [])
    if not examples:
        print(f"No examples found in {json_file_path}")
        return
    
    # Convert to DataFrame with flattened structure
    flattened_data = []
    for example in examples:
        # Create a copy to avoid modifying the original
        example_copy = example.copy()
        
        # Handle indicators which is typically a list
        if 'indicators' in example_copy and isinstance(example_copy['indicators'], list):
            example_copy['indicators'] = '; '.join(example_copy['indicators'])
        
        # Handle other potential list fields (dynamically)
        for key, value in list(example_copy.items()):
            if isinstance(value, list):
                example_copy[key] = '; '.join(str(item) for item in value)
        
        flattened_data.append(example_copy)
    
    # Create DataFrame
    df = pd.DataFrame(flattened_data)
    
    # Save to CSV
    df.to_csv(csv_file_path, index=False)
    

if __name__ == "__main__":
    # Example usage for testing
    json_dir = Path("data/seeds")
    csv_dir = Path("data/seeds/csv")
    convert_json_to_csv(json_dir, csv_dir)