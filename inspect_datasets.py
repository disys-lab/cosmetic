#!/usr/bin/env python3
"""
Inspect the three datasets used by ACC, LRT, and KS applications.
Shows structure, keys, shapes, and sample values.
"""
import pickle
import os

def inspect_pkl(path, name):
    """Load a pkl file and print its structure."""
    print("=" * 70)
    print(f"  {name}")
    print(f"  Path: {path}")
    print("=" * 70)
    
    if not os.path.isfile(path):
        print(f"  ERROR: File not found.\n")
        return
    
    with open(path, "rb") as f:
        data = pickle.load(f)
    
    # What type is the top-level object?
    print(f"\n  Type of loaded object: {type(data).__name__}")
    
    if isinstance(data, dict):
        print(f"  Number of keys: {len(data)}")
        print(f"  Keys: {list(data.keys())}")
        print()
        
        for key in data.keys():
            val = data[key]
            print(f"  --- Key: '{key}' ---")
            print(f"      Type: {type(val).__name__}")
            
            if hasattr(val, 'shape'):
                print(f"      Shape: {val.shape}")
                if val.size > 0 and val.size <= 20:
                    print(f"      Values: {val}")
                elif hasattr(val, 'flatten'):
                    flat = val.flatten()
                    print(f"      First 5 values: {flat[:5].tolist()}")
                    print(f"      Last 3 values:  {flat[-3:].tolist()}")
            elif isinstance(val, (list, tuple)):
                print(f"      Length: {len(val)}")
                if len(val) <= 10:
                    print(f"      Values: {val}")
                else:
                    print(f"      First 3: {val[:3]}")
                    print(f"      Last 2:  {val[-2:]}")
            else:
                s = str(val)
                if len(s) > 200:
                    s = s[:200] + "..."
                print(f"      Value: {s}")
            print()
    else:
        print(f"  Content (repr): {repr(data)[:500]}")
    
    print()

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base, "data")
    
    # 1. Logistic regression data (used by ACC and LRT)
    inspect_pkl(
        os.path.join(data_dir, "data_for_logreg_small.pkl"),
        "1. data_for_logreg_small.pkl (used by ACC & LRT)"
    )
    
    # 2. Logistic regression coefficients (used by ACC and LRT)
    inspect_pkl(
        os.path.join(data_dir, "logreg_glm_fits.pkl"),
        "2. logreg_glm_fits.pkl (used by ACC & LRT)"
    )
    
    # 3. KS test data (used by KS only)
    inspect_pkl(
        os.path.join(data_dir, "data_for_ks_test.pkl"),
        "3. data_for_ks_test.pkl (used by KS)"
    )
    
    print("Done.")

if __name__ == "__main__":
    main()
