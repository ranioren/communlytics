
import os
import pandas as pd
import sys

# Ensure we can import data_utils
sys.path.append(os.getcwd())
from data_utils import process_stackoverflow_export

# Configuration
QUESTIONS_PATH = r"C:\Users\Ran Oren\stof\Questions.csv"
ANSWERS_PATH = r"C:\Users\Ran Oren\stof\Answers.csv"
OUTPUT_PATH = r"channel extraction\stof10k.csv"
TARGET_ROWS = 10000

def main():
    print(f"Processing StackOverflow export...")
    print(f"Questions: {QUESTIONS_PATH}")
    print(f"Answers: {ANSWERS_PATH}")

    # Call the processing function
    # Note: process_stackoverflow_export reads the files fully. 
    # If this runs out of memory, we will need to rewrite the function to using chunking.
    try:
        df = process_stackoverflow_export(QUESTIONS_PATH, ANSWERS_PATH)
    except Exception as e:
        print(f"Critical Error in processing: {e}")
        return

    if df.empty:
        print("Error: Empty DataFrame returned.")
        return

    print(f"Total rows merged: {len(df)}")

    # Sort by Question Score (Score_x) descending to get best questions
    if 'Score_x' in df.columns:
        print("Sorting by Question Score...")
        df = df.sort_values(by='Score_x', ascending=False)

    # Limit to 10k
    df_10k = df.head(TARGET_ROWS)

    print(f"Generated {len(df_10k)} rows (limited to {TARGET_ROWS}).")
    
    # Save
    df_10k.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
