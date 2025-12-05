"""
Test script for session security features.
Verifies session regeneration, timeout checking, and fingerprint validation.
"""

from app import create_app
from app.session_security import (
    regenerate_session,
    init_session_security,
    check_session_timeout,
    validate_session_fingerprint,
    get_session_info
)
from flask import session
from config import Config
from datetime import datetime, timedelta


def test_session_regeneration():
    """Test session ID regeneration."""
    print("\n" + "=" * 80)
    print("TEST: Session Regeneration")
    print("=" * 80)

    app = create_app(Config)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            # Set some initial session data
            sess['user_id'] = 123
            sess['test_data'] = 'original_value'
            original_sid = id(sess)

        print(f"Original session data: {dict(session)}")

        # Regenerate session
        with app.test_request_context():
            with client.session_transaction() as sess:
                for key, value in sess.items():
                    session[key] = value

            success = regenerate_session()
            print(f"Regeneration successful: {success}")

        # Check session data persisted
        with client.session_transaction() as sess:
            print(f"After regeneration: {dict(sess)}")
            assert sess.get('user_id') == 123, "User ID should persist"
            assert sess.get('test_data') == 'original_value', "Test data should persist"

    print("[PASS] Session regeneration preserves data")
    return True


def test_session_initialization():
    """Test session security initialization."""
    print("\n" + "=" * 80)
    print("TEST: Session Security Initialization")
    print("=" * 80)

    app = create_app(Config)

    with app.test_client() as client:
        with app.test_request_context():
            init_session_security()

            # Check that security fields were added
            assert '_created_at' in session, "Should have creation timestamp"
            assert '_last_activity' in session, "Should have last activity timestamp"
            assert '_session_id' in session, "Should have session ID"
            assert '_user_agent' in session, "Should have user agent"
            assert '_ip_address' in session, "Should have IP address"

            print(f"Session security metadata:")
            print(f"  - Created at: {session.get('_created_at')}")
            print(f"  - Last activity: {session.get('_last_activity')}")
            print(f"  - Session ID: {session.get('_session_id')[:16]}...")
            print(f"  - User agent: {session.get('_user_agent', 'N/A')}")
            print(f"  - IP address: {session.get('_ip_address')}")

    print("[PASS] Session initialization sets metadata")
    return True


def test_session_timeout_checking():
    """Test session timeout detection."""
    print("\n" + "=" * 80)
    print("TEST: Session Timeout Checking")
    print("=" * 80)

    app = create_app(Config)

    with app.test_client() as client:
        with app.test_request_context():
            # Initialize session
            init_session_security()

            # Test 1: Fresh session should not be expired
            is_expired, reason = check_session_timeout(
                absolute_timeout=86400,  # 24 hours
                inactivity_timeout=3600  # 1 hour
            )
            print(f"Test 1 - Fresh session: expired={is_expired}, reason={reason}")
            assert not is_expired, "Fresh session should not be expired"

            # Test 2: Simulate old session (absolute timeout)
            old_time = (datetime.utcnow() - timedelta(hours=25)).isoformat()
            session['_created_at'] = old_time
            is_expired, reason = check_session_timeout(
                absolute_timeout=86400,  # 24 hours
                inactivity_timeout=3600
            )
            print(f"Test 2 - Old session (25h): expired={is_expired}, reason={reason}")
            assert is_expired, "Old session should be expired"
            assert "expired after" in reason.lower(), "Should mention expiration"

            # Test 3: Simulate inactive session
            session['_created_at'] = datetime.utcnow().isoformat()  # Recent creation
            inactive_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
            session['_last_activity'] = inactive_time
            is_expired, reason = check_session_timeout(
                absolute_timeout=86400,
                inactivity_timeout=3600  # 1 hour
            )
            print(f"Test 3 - Inactive session (2h): expired={is_expired}, reason={reason}")
            assert is_expired, "Inactive session should be expired"
            assert "inactive" in reason.lower(), "Should mention inactivity"

    print("[PASS] Session timeout checking works correctly")
    return True


def test_fingerprint_validation():
    """Test session fingerprint validation."""
    print("\n" + "=" * 80)
    print("TEST: Session Fingerprint Validation")
    print("=" * 80)

    app = create_app(Config)

    with app.test_client() as client:
        # Test 1: Matching user agent
        with app.test_request_context(headers={'User-Agent': 'Mozilla/5.0 Test Browser'}):
            session['_user_agent'] = 'Mozilla/5.0 Test Browser'
            is_valid, reason = validate_session_fingerprint()
            print(f"Test 1 - Matching UA: valid={is_valid}, reason={reason}")
            assert is_valid, "Matching user agent should be valid"

        # Test 2: Changed user agent (possible hijacking)
        with app.test_request_context(headers={'User-Agent': 'Different Browser'}):
            session['_user_agent'] = 'Mozilla/5.0 Test Browser'
            is_valid, reason = validate_session_fingerprint()
            print(f"Test 2 - Changed UA: valid={is_valid}, reason={reason}")
            assert not is_valid, "Changed user agent should be invalid"
            assert "mismatch" in reason.lower(), "Should mention mismatch"

    print("[PASS] Fingerprint validation detects mismatches")
    return True


def test_session_info():
    """Test getting session information."""
    print("\n" + "=" * 80)
    print("TEST: Session Information Retrieval")
    print("=" * 80)

    app = create_app(Config)

    with app.test_client() as client:
        with app.test_request_context():
            # Initialize session
            init_session_security()

            # Get session info
            info = get_session_info()

            print("Session Info:")
            for key, value in info.items():
                print(f"  - {key}: {value}")

            assert info is not None, "Should return session info"
            assert 'session_id' in info, "Should have session ID"
            assert 'created_at' in info, "Should have creation time"
            assert 'session_age_seconds' in info, "Should have session age"
            assert 'inactive_seconds' in info, "Should have inactivity time"

    print("[PASS] Session info retrieval works")
    return True


if __name__ == '__main__':
    print("\n" * 2)
    print("+" + "=" * 78 + "+")
    print("|" + " " * 20 + "TACTIZEN SESSION SECURITY TESTS" + " " * 27 + "|")
    print("+" + "=" * 78 + "+")

    tests = [
        test_session_regeneration,
        test_session_initialization,
        test_session_timeout_checking,
        test_fingerprint_validation,
        test_session_info
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_func.__name__}: {e}")
            failed += 1

    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print(f"Tests Passed: {passed}/{len(tests)}")
    print(f"Tests Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n[PASS] ALL SESSION SECURITY TESTS PASSED!")
    else:
        print(f"\n[FAIL] {failed} test(s) failed")

    print("=" * 80)
    print()
