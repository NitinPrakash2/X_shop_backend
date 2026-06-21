#!/usr/bin/env python3
"""
Quick test to verify backend-frontend connection
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

async def test_connection():
    print("\n" + "="*80)
    print("TESTING BACKEND-FRONTEND CONNECTION")
    print("="*80)
    
    # Test 1: Check if backend is running
    print("\n[1] Testing Backend Connection...")
    try:
        import httpx
        response = await httpx.AsyncClient().get("http://localhost:8000/")
        if response.status_code == 200:
            print("    ✓ Backend is running on http://localhost:8000")
        else:
            print(f"    ✗ Backend returned status: {response.status_code}")
    except Exception as e:
        print(f"    ✗ Backend not accessible: {str(e)}")
        print("    → Start backend: uvicorn src.index:app --reload")
    
    # Test 2: Check CORS headers
    print("\n[2] Testing CORS Configuration...")
    try:
        response = await httpx.AsyncClient().options("http://localhost:8000/client/api/i/ona/xshop?action=get_products")
        headers = response.headers
        if 'access-control-allow-origin' in headers:
            print(f"    ✓ CORS enabled: {headers['access-control-allow-origin']}")
        else:
            print("    ✗ CORS not configured")
    except Exception as e:
        print(f"    ⚠ Could not check CORS: {str(e)}")
    
    # Test 3: Check API endpoints
    print("\n[3] Testing API Endpoints...")
    endpoints = [
        "/docs",
        "/client-public/docs",
        "/client/docs"
    ]
    
    for endpoint in endpoints:
        try:
            response = await httpx.AsyncClient().get(f"http://localhost:8000{endpoint}")
            if response.status_code == 200:
                print(f"    ✓ {endpoint} - OK")
            else:
                print(f"    ✗ {endpoint} - {response.status_code}")
        except Exception as e:
            print(f"    ✗ {endpoint} - Error")
    
    # Test 4: Database connection
    print("\n[4] Testing Database Connection...")
    try:
        from src.db_config import AsyncSessionLocal
        db = AsyncSessionLocal()
        await db.execute("SELECT 1")
        await db.close()
        print("    ✓ Database connected")
    except Exception as e:
        print(f"    ✗ Database connection failed: {str(e)}")
    
    # Test 5: Check product sync
    print("\n[5] Testing Product Sync Capability...")
    try:
        from src.shared.utility.l.xshop.app.integrations.product_api.client import fetch_product_list
        result = await fetch_product_list(query="", page=1, per_page=5)
        if result["success"]:
            print(f"    ✓ External API accessible - {len(result['data'])} products")
        else:
            print(f"    ✗ External API error: {result.get('error')}")
    except Exception as e:
        print(f"    ✗ External API test failed: {str(e)}")
    
    print("\n" + "="*80)
    print("CONNECTION TEST SUMMARY")
    print("="*80)
    print("\nBackend URLs:")
    print("  - Main API: http://localhost:8000")
    print("  - Swagger Docs: http://localhost:8000/docs")
    print("  - Public API: http://localhost:8000/client-public/docs")
    print("  - Private API: http://localhost:8000/client/docs")
    print("\nFrontend URLs:")
    print("  - Dev Server: http://localhost:5173")
    print("  - Dashboard: http://localhost:5173/xshop")
    print("  - Products: http://localhost:5173/xshop/products")
    print("\nNext Steps:")
    print("  1. Start backend: uvicorn src.index:app --reload")
    print("  2. Start frontend: npm run dev")
    print("  3. Open http://localhost:5173/xshop")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_connection())
