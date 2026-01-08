import pandas as pd
import google.generativeai as genai
import os
import pickle
from dotenv import load_dotenv
from tqdm import tqdm
import time

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

def vectorize():
    input_path = os.path.join("channel extraction", "stof400.csv")
    output_path = os.path.join("channel extraction", "knowledge_base.pkl")
    
    print(f"Loading data from {input_path}...")
    df = pd.read_csv(input_path)
    
    # Combine Question and Answer for a richer embedding context
    # We will search against both, but the embedding should represent the topic
    df['text_for_embedding'] = "Question: " + df['Question'].astype(str) + "\nAnswer: " + df['Answer'].astype(str)
    
    embeddings = []
    start_idx = 0
    if os.path.exists(output_path):
        try:
            with open(output_path, 'rb') as f:
                old_df = pickle.load(f)
                embeddings = list(old_df['embedding'])
                start_idx = len(embeddings)
                print(f"Resuming from index {start_idx}...")
        except Exception as e:
            print(f"Could not load checkpoint: {e}. Starting from scratch.")
    
    print("Generating embeddings via Gemini (batching)...")
    
    # Simple batching to stay within rate limits (15 RPM for Free Tier)
    for i in tqdm(range(start_idx, len(df))):
        text = df.iloc[i]['text_for_embedding']
        
        # Initial retry parameters
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
                # Fixed sleep to stay under 15 RPM (60/15 = 4s, using 5s for safety)
                time.sleep(4.5) 
                
                # Checkpoint: Save every 10 rows
                if (i + 1) % 10 == 0:
                    df_partial = df.iloc[:len(embeddings)].copy()
                    df_partial['embedding'] = embeddings
                    with open(output_path, 'wb') as f:
                        pickle.dump(df_partial, f)
                
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Resource has been exhausted" in error_str:
                    # Look for retry delay in error message or default to 60s
                    print(f"\nRate limit hit at {i}. Waiting 60s before retry...")
                    time.sleep(60) 
                    if attempt == max_retries - 1:
                        print(f"Failed after {max_retries} attempts at index {i}")
                        # Save partial progress
                        df_partial = df.iloc[:len(embeddings)].copy()
                        df_partial['embedding'] = embeddings
                        with open(output_path, 'wb') as f:
                            pickle.dump(df_partial, f)
                        raise e
                else:
                    print(f"Error at index {i}: {e}")
                    raise e

    df['embedding'] = embeddings
    
    # Save the dataframe with embeddings
    print(f"Saving knowledge base to {output_path}...")
    with open(output_path, 'wb') as f:
        pickle.dump(df, f)
    
    print("Done!")

if __name__ == "__main__":
    vectorize()
