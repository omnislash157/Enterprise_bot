#!/usr/bin/env python3
"""
Minimal Deepgram WebSocket Connection Test
Tests different parameter combinations to isolate HTTP 400 cause
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
import websockets

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

async def test_connection(test_name: str, url: str):
    """Test a specific URL configuration"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"URL: {url}")
    print(f"API Key: {DEEPGRAM_API_KEY[:8]}... (length: {len(DEEPGRAM_API_KEY)})")

    headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

    try:
        ws = await websockets.connect(
            url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10
        )
        print("✅ SUCCESS - Connected to Deepgram!")
        print(f"WebSocket state: {ws.state.name}")
        await ws.close()
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

async def main():
    if not DEEPGRAM_API_KEY:
        print("❌ ERROR: DEEPGRAM_API_KEY not found in .env")
        sys.exit(1)

    print("Deepgram WebSocket Connection Test Suite")
    print(f"Using websockets library version: {websockets.__version__}")

    results = {}

    # Test 1: Minimal parameters (just model)
    results['minimal'] = await test_connection(
        "Minimal (model only)",
        "wss://api.deepgram.com/v1/listen?model=nova-2"
    )
    await asyncio.sleep(1)

    # Test 2: With encoding, no sample rate
    results['encoding_only'] = await test_connection(
        "Encoding only (no sample_rate)",
        "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=webm-opus"
    )
    await asyncio.sleep(1)

    # Test 3: With 16kHz sample rate (frontend setting)
    results['16khz'] = await test_connection(
        "16kHz sample rate (current frontend)",
        "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=webm-opus&sample_rate=16000"
    )
    await asyncio.sleep(1)

    # Test 4: With 48kHz sample rate (current backend)
    results['48khz'] = await test_connection(
        "48kHz sample rate (current backend)",
        "wss://api.deepgram.com/v1/listen?model=nova-2&encoding=webm-opus&sample_rate=48000"
    )
    await asyncio.sleep(1)

    # Test 5: Full production config (as backend builds it)
    results['full_config'] = await test_connection(
        "Full production config",
        "wss://api.deepgram.com/v1/listen?model=nova-2&language=en-US&smart_format=true&interim_results=true&punctuate=true&encoding=webm-opus&sample_rate=48000"
    )

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n{'='*60}")
    print("DIAGNOSIS")
    print(f"{'='*60}")

    # All passed
    if all(results.values()):
        print("✅ All tests passed - WebSocket connection working correctly")
        print("🔍 Issue may be in audio data transmission, not connection")

    # All failed
    elif not any(results.values()):
        print("❌ All tests failed - Check:")
        print("   1. API key validity (try regenerating in Deepgram dashboard)")
        print("   2. Network connectivity (firewall blocking websockets?)")
        print("   3. Deepgram service status")

    # Some passed, some failed
    else:
        print("⚠️  Mixed results - Connection works with some configs")
        if results['minimal'] and not results['48khz']:
            print("🎯 Sample rate parameter causing rejection")
            print("   → Try removing sample_rate from backend config")
        if results['minimal'] and not results['encoding_only']:
            print("🎯 Encoding parameter may be problematic")
            print("   → Try 'opus' instead of 'webm-opus'")
        if results['16khz'] and not results['48khz']:
            print("🎯 48kHz rejected but 16kHz works")
            print("   → Change backend to sample_rate=16000")
        if results['48khz'] and not results['16khz']:
            print("🎯 16kHz rejected but 48kHz works")
            print("   → Change frontend to sampleRate: 48000")

if __name__ == "__main__":
    asyncio.run(main())
