
import pickle
import os
import pandas as pd

pkl_path = os.path.join("channel extraction", "knowledge_base.pkl")

if os.path.exists(pkl_path):
    try:
        with open(pkl_path, 'rb') as f:
            df = pickle.load(f)
        
        print(f"Loaded {len(df)} records.")
        if not df.empty and 'embedding' in df.columns:
            emb = df.iloc[0]['embedding']
            print(f"Embedding type: {type(emb)}")
            print(f"Embedding dimension: {len(emb)}")
        else:
            print("No embeddings found in dataframe.")
            
    except Exception as e:
        print(f"Error loading pickle: {e}")
else:
    print(f"File not found: {pkl_path}")
