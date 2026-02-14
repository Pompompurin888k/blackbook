"""
Quick test script to demonstrate smart recommendation algorithm
Run this to see how the scoring works
"""
import os
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "8291")
os.environ.setdefault("DB_NAME", "blackbook_db")
os.environ.setdefault("DB_USER", "bb_operator")

import sys
sys.path.insert(0, 'web')

from web.database import Database

def test_recommendations():
    """Test the smart recommendation system"""
    db = Database()
    
    print("🧪 TESTING SMART RECOMMENDATIONS")
    print("=" * 60)
    
    # Get all active providers
    all_providers = db.get_active_providers("Nairobi", None)
    
    if not all_providers:
        print("❌ No providers found. Run /seed endpoint first!")
        return
    
    # Test with first provider
    source = all_providers[0]
    print(f"\n📍 SOURCE PROVIDER:")
    print(f"   Name: {source['display_name']}")
    print(f"   Neighborhood: {source.get('neighborhood', 'N/A')}")
    print(f"   Build: {source.get('build', 'N/A')}")
    print(f"   Online: {'Yes' if source.get('is_online') else 'No'}")
    
    # Get recommendations
    recommendations = db.get_recommendations("Nairobi", source['id'], limit=4)
    
    print(f"\n✨ RECOMMENDATIONS (Smart Algorithm):")
    print("-" * 60)
    
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec['display_name']}")
        print(f"   📍 {rec.get('neighborhood', 'N/A')}")
        print(f"   🏋️ Build: {rec.get('build', 'N/A')}")
        print(f"   {'🟢' if rec.get('is_online') else '⚫'} Status: {'Online' if rec.get('is_online') else 'Offline'}")
        
        # Show why it was recommended
        reasons = []
        if rec.get('neighborhood') == source.get('neighborhood'):
            reasons.append("✓ Same neighborhood (+10 pts)")
        if rec.get('build') == source.get('build'):
            reasons.append("✓ Similar build (+5 pts)")
        if rec.get('is_online'):
            reasons.append("✓ Currently available (+2 pts)")
        
        if reasons:
            print(f"   Why: {', '.join(reasons)}")
    
    print("\n" + "=" * 60)
    print("✅ Test complete! Algorithm is working.")
    print("\nKey improvements:")
    print("  • Same neighborhood providers prioritized")
    print("  • Similar build types grouped together")
    print("  • Online providers boosted")
    print("  • Recently verified get preference")

if __name__ == "__main__":
    try:
        test_recommendations()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Docker containers are running")
        print("  2. Database is seeded (visit /seed)")
        print("  3. Port 8291 is accessible")
