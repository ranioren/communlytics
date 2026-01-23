import google.generativeai as genai
import pandas as pd
import numpy as np
import pickle
import os
import time
from tqdm import tqdm
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

from sqlalchemy import create_engine, text

# Load from environment variable
DB_URI = os.getenv("DB_URI")

KB_PATH = os.path.join("channel extraction", "knowledge_base.pkl")

def get_embedding(text):
    """Fetches embedding for a single string using Gemini."""
    try:
        # Add rate limit handling if needed, but basic call:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query"
        )
        return np.array(result['embedding'])
    except Exception as e:
        print(f"Error fetching embedding: {e}")
        return None

def get_top_suggestions(query, top_k=3):
    """Finds top K similar entries in the Postgres DB using pgvector."""
    query_emb = get_embedding(query)
    if query_emb is None:
        return []
    
    # Format for PGVector
    # Numpy array to list of floats (crucial for json/string serialization)
    emb_list = [float(x) for x in query_emb]
    emb_str = str(emb_list)
    
    try:
        engine = create_engine(DB_URI)
        with engine.connect() as conn:
            # Use Cosine Distance operator <=>
            # Similarity = 1 - Distance
            sql = text("""
                SELECT question, answer, 1 - (embedding <=> :emb) as similarity
                FROM knowledge_base
                ORDER BY embedding <=> :emb
                LIMIT :k
            """)
            
            result = conn.execute(sql, {"emb": emb_str, "k": top_k}).fetchall()
            
        suggestions = []
        for row in result:
            suggestions.append({
                'question': row.question,
                'answer': row.answer,
                'similarity': float(row.similarity)
            })
        return suggestions
        
    except Exception as e:
        print(f"Vector search failed: {e}")
        # Optional: Fallback to pickle if needed, but we wanted to migrate away.
        return []

def generate_ai_response(question, contexts, existing_draft=""):
    """Generates a response using Gemini based on provided contexts and existing draft."""
    model = genai.GenerativeModel('gemini-flash-latest')
    
    context_str = "\n\n".join([f"Relevant Response {i+1}:\nQ: {c['question']}\nA: {c['answer']}" for i, c in enumerate(contexts)])
    
    prompt = f"""
You are a professional technical writer and community manager for a Technology Blog dealing with Python developer questions.
Your goal is to answer the user's question kindly, professionally, and accurately.

The Original Question:
{question}

---
Existing Draft Content (if any):
{existing_draft}

---
Relevant Knowledge Base Responses:
{context_str}

---
Task:
1. Please draft a response to the original question.
2. Incorporate any useful information from the 'Existing Draft Content' above.
3. Use the 'Relevant Knowledge Base Responses' to provide technical depth and accurate Python-related guidance.
4. Ensure the tone is kind, professional, and suitable for a technology blog.
5. If some information is missing or unclear, politely advise the user on how to clarify their issue.

Final Response:
"""
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating response: {e}"

if __name__ == "__main__":
    # Test
    print("Testing similarity search...")
    results = get_top_suggestions("How to find path in s3?")
    for r in results:
        print(f"\nMatch ({r['similarity']:.2f}): {r['question'][:50]}...")

def generate_community_health_suggestion(status_summary):
    """Generates recommendations for a community manager based on health metrics."""
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
You are an expert Community Manager consultant.
Review the following community status summary:

{status_summary}

Task:
1. Summarize the status (trends, volume, feedback).
2. Provide specific, actionable recommendations for a community manager to drive engagement up or maintain momentum.
3. Keep the tone professional, encouraging, and concise (under 200 words).
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating suggestion: {e}"

def generate_crm_response(user_query, context_str):
    """
    Generates a response to a user's question about a specific CRM contact,
    based strictly on the provided context string.
    """
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
You are a helpful CRM assistant. You have access to the following details about a user:

{context_str}

User Question: {user_query}

Task:
1. Answer the question using ONLY the information provided above.
2. If the information is not in the context, politely say you don't know.
3. Be concise and friendly.
"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def build_knowledge_base(input_csv_path=None, output_pkl_path=None):
    """
    Vectorizes the Q&A dataset and saves it as a pickle file.
    Default input: channel extraction/stof400.csv
    Default output: channel extraction/knowledge_base.pkl
    """
    if input_csv_path is None:
        input_csv_path = os.path.join("channel extraction", "stof400.csv")
    if output_pkl_path is None:
        output_pkl_path = os.path.join("channel extraction", "knowledge_base.pkl")
    
    print(f"Loading data from {input_csv_path}...")
    if not os.path.exists(input_csv_path):
        print("Input file not found.")
        return

    df = pd.read_csv(input_csv_path)
    
    # Combine Question and Answer for a richer embedding context
    df['text_for_embedding'] = "Question: " + df['Question'].astype(str) + "\nAnswer: " + df['Answer'].astype(str)
    
    embeddings = []
    start_idx = 0
    if os.path.exists(output_pkl_path):
        try:
            with open(output_pkl_path, 'rb') as f:
                old_df = pickle.load(f)
                embeddings = list(old_df['embedding'])
                start_idx = len(embeddings)
                print(f"Resuming from index {start_idx}...")
        except Exception as e:
            print(f"Could not load checkpoint: {e}. Starting from scratch.")
    
    print("Generating embeddings via Gemini (batching)...")
    
    # Simple batching to stay within rate limits
    for i in tqdm(range(start_idx, len(df))):
        text = df.iloc[i]['text_for_embedding']
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=text,
                    task_type="retrieval_document"
                )
                embeddings.append(result['embedding'])
                
                # Rate limit safety (15 RPM -> 4s gap)
                time.sleep(4.5) 
                
                # Checkpoint: Save every 10 rows
                if (i + 1) % 10 == 0:
                    df_partial = df.iloc[:len(embeddings)].copy()
                    df_partial['embedding'] = embeddings
                    with open(output_pkl_path, 'wb') as f:
                        pickle.dump(df_partial, f)
                
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Resource has been exhausted" in error_str:
                    print(f"\nRate limit hit at {i}. Waiting 60s before retry...")
                    time.sleep(60) 
                    if attempt == max_retries - 1:
                        print(f"Failed after {max_retries} attempts at index {i}")
                        # Save partial
                        df_partial = df.iloc[:len(embeddings)].copy()
                        df_partial['embedding'] = embeddings
                        with open(output_pkl_path, 'wb') as f:
                            pickle.dump(df_partial, f)
                        raise e
                else:
                    print(f"Error at index {i}: {e}")
                    raise e

    df['embedding'] = embeddings
    
    print(f"Saving knowledge base to {output_pkl_path}...")
    with open(output_pkl_path, 'wb') as f:
        pickle.dump(df, f)
    
    print("Done!")
