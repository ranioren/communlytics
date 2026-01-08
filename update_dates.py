import pandas as pd
from datetime import datetime
import os

# Load the CSV
input_path = os.path.join("channel extraction", "merged_data.csv")
output_path = os.path.join("channel extraction", "merged_data_updated.csv")
backup_path = os.path.join("channel extraction", "merged_data_backup.csv")

print(f"Loading data from {input_path}...")
df = pd.read_csv(input_path)

# Create backup
print(f"Creating backup at {backup_path}...")
df.to_csv(backup_path, index=False)

# Function to update year in timestamp
def update_year(timestamp_str):
    try:
        # Parse the timestamp
        dt = pd.to_datetime(timestamp_str)
        
        # Define year updates
        year_updates = {
            2017: 2025,
            2018: 2024,
            2019: 2025,
            2022: 2025
        }
        
        # Update year based on original year
        original_year = dt.year
        if original_year in year_updates:
            dt = dt.replace(year=year_updates[original_year])
        
        return str(dt)
    except:
        # If parsing fails, return original
        return timestamp_str

print("Updating years in timestamp column...")
print(f"  2018 → 2024")
print(f"  2019 → 2025")
print(f"  2022 → 2025")

df['timestamp'] = df['timestamp'].apply(update_year)

# Save updated data
print(f"Saving updated data to {output_path}...")
df.to_csv(output_path, index=False)

print("\nDone! Summary:")
print(f"  Original file: {input_path}")
print(f"  Backup file: {backup_path}")
print(f"  Updated file: {output_path}")
print("\nPlease review the updated file. If satisfied, you can replace the original.")
