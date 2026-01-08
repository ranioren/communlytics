import google.generativeai as genai
import pandas as pd
import numpy as np
import pickle
import os
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

KB_PATH = os.path.join("channel extraction", "knowledge_base.pkl")

def get_embedding(text):
    """Fetches embedding for a single string using Gemini."""
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query"
        )
        return np.array(result['embedding'])
    except Exception as e:
        print(f"Error fetching embedding: {e}")
        return None

def load_kb():
    """Loads the vectorized knowledge base."""
    if not os.path.exists(KB_PATH):
        return None
    with open(KB_PATH, 'rb') as f:
        return pickle.load(f)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def get_top_suggestions(query, top_k=3):
    """Finds top K similar entries in the KB."""
    kb_df = load_kb()
    if kb_df is None:
        return []
    
    query_emb = get_embedding(query)
    if query_emb is None:
        return []
    
    # Calculate similarities
    # kb_df['embedding'] contains lists or arrays
    similarities = []
    for emb in kb_df['embedding']:
        similarities.append(cosine_similarity(query_emb, np.array(emb)))
    
    kb_df['similarity'] = similarities
    
    # Sort and return top K
    top_results = kb_df.sort_values(by='similarity', ascending=False).head(top_k)
    
    suggestions = []
    for _, row in top_results.iterrows():
        suggestions.append({
            'question': row['Question'],
            'answer': row['Answer'],
            'similarity': row['similarity']
        })
    return suggestions

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
