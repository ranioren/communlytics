
import os
import pandas as pd
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import io

# Load Env
load_dotenv()

# Set env for data loading
# Ensure we can import from local directory
import sys
sys.path.append(os.getcwd())

from data_utils import load_data, generate_wordcloud, save_wordcloud_to_db

DATA_PATH = os.path.join("channel extraction", "merged_data.csv")

def main():
    print("Starting Analytics Job...")
    
    # 1. Load Data
    print("Loading data...")
    try:
        df = load_data(DATA_PATH)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    if df.empty:
        print("No data found.")
        return

    # 2. Generate Wordcloud
    print("Generating Word Cloud (this uses AI model, may take time)...")
    # Using global data
    text_content = " ".join(df['sentences'].astype(str))
    
    # Generate (returns numpy array)
    wc_array = generate_wordcloud(text_content)
    
    if wc_array is None:
        print("Failed to generate wordcloud.")
        return

    # 3. Save to Cache
    print("Saving to DB Cache...")
    # Convert numpy array/image to bytes
    try:
        # Array to Image
        plt.figure(figsize=(10, 5))
        plt.imshow(wc_array, interpolation='bilinear')
        plt.axis("off")
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
        buf.seek(0)
        image_bytes = buf.getvalue()
        plt.close()
        
        success = save_wordcloud_to_db(image_bytes)
        if success:
            print("Successfully saved global_wordcloud to app_cache.")
        else:
            print("Failed to save to DB.")
            
    except Exception as e:
        print(f"Error processing image for save: {e}")

if __name__ == "__main__":
    main()
