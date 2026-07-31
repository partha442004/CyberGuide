"""Helper to list all routes in the FastAPI app."""
import sys
import os

# Add the src directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cybershield.main import app

# Get routes from OpenAPI schema
schema = app.openapi()
paths = schema.get("paths", {})

print(f"\nTotal API paths: {len(paths)}\n")
for path in sorted(paths.keys()):
    methods = list(paths[path].keys())
    print(f"  {methods} {path}")
