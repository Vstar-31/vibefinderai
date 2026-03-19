"""
Quick test to verify imports work after reorganization
"""
import sys
import os

# Add backend folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")

try:
    # Test core imports
    from core import vibe_engine
    print("✓ from core import vibe_engine")
    
    from core.vibe_engine import LANGUAGE_TAG_MAP
    print("✓ from core.vibe_engine import LANGUAGE_TAG_MAP")
    
    from core import analytics
    print("✓ from core import analytics")
    
    # Test analyzer imports
    from analyzers import semantic_search
    print("✓ from analyzers import semantic_search")
    
    from analyzers import report_analysis_hub
    print("✓ from analyzers import report_analysis_hub")
    
    # Test data imports
    from data import enrichment
    print("✓ from data import enrichment")
    
    # Test routes imports
    from routes import analytics_routes
    print("✓ from routes import analytics_routes")
    
    print("\n✅ All imports successful!")
    
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)

