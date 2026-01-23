
import pickle
import os
import sys

# Mock Streamlit
import types
st = types.ModuleType("streamlit")
st.cache_data = lambda func: func
sys.modules["streamlit"] = st

KB_PATH = os.path.join("channel extraction", "knowledge_base.pkl")

if os.path.exists(KB_PATH):
    try:
        with open(KB_PATH, 'rb') as f:
            df = pickle.load(f)
            if not df.empty and 'embedding' in df.columns:
                emb = df.iloc[0]['embedding']
                print(f"DIMENSION:{len(emb)}")
            else:
                print("ERROR: Empty DataFrame or no embedding column")
    except Exception as e:
        print(f"ERROR: {e}")
else:
    print("ERROR: File not found")
