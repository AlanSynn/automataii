import os
import sys

print("--- sys.path ---")
for p in sys.path:
    print(p)
print("--- end sys.path ---")
print(f"PYTHONPATH environment variable: {os.environ.get('PYTHONPATH')}")
