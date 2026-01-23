
import sys
import os
import types
import pandas as pd

# Mock Streamlit to handle decorators
st = types.ModuleType("streamlit")

def cache_mock(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator

st.cache_data = cache_mock
st.cache_resource = cache_mock
st.error = lambda msg: print(f"ERROR: {msg}")
sys.modules["streamlit"] = st

# Add path
sys.path.append(os.getcwd())

from data_utils import load_data, enrich_user_data

def verify():
    print("Verifying DB Integration...")
    
    # Test load_data
    # We pass a dummy path, it should IGNORE it if DB works, or fallback to it if DB fails.
    # To prove it uses DB, we can pass a non-existent path? 
    # data_utils.load_data(path) checks path existence at end as fallback.
    # If DB works, it returns before checking path.
    # So passing "dummy.csv" is a good test.
    
    print("Testing load_data (from DB)...")
    try:
        df = load_data("non_existent_file.csv")
        print(f"FAILED? No, wait. If DB works, it returns DF. If DB fails, it falls back to path check and errors.")
        print(f"Result Shape: {df.shape}")
        if not df.empty:
            print("SUCCESS: Loaded messages from DB!")
            print(f"Sample: {df.iloc[0]['sentences'][:50]}...")
    except Exception as e:
        print(f"load_data failed: {e}")

    # Test enrich_user_data
    print("Testing enrich_user_data (from DB)...")
    try:
        # Pass empty inputs to prove it hits DB logic first
        users_df = enrich_user_data(pd.DataFrame(), pd.DataFrame())
        print(f"Result Shape: {users_df.shape}")
        if not users_df.empty:
            print("SUCCESS: Loaded users from DB!")
            # Check a known user
            try:
                print(f"Sample User: {users_df.index[0]}")
            except: pass
    except Exception as e:
         print(f"enrich_user_data failed: {e}")

if __name__ == "__main__":
    verify()
