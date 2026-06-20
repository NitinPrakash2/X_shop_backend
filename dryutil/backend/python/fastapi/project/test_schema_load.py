import os
import sys
import importlib.util

schema_path = os.path.join(os.path.dirname(__file__), "src", "shared", "utility", "l", "xshop", "app", "schemas", "auth.py")
print(f"Schema path: {schema_path}")
print(f"Exists: {os.path.exists(schema_path)}")

if os.path.exists(schema_path):
    spec = importlib.util.spec_from_file_location("xshop_schema_auth", schema_path)
    if spec and spec.loader:
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print(f"Schema module loaded successfully")
            print(f"Has RegisterRequest: {hasattr(mod, 'RegisterRequest')}")
        except Exception as e:
            print(f"Failed to load: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Spec is None")
