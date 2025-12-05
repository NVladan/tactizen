"""
Test script for error handling functionality.
Verifies custom error pages, error handlers, and security logging integration.
"""

from app import create_app
from config import Config


def test_error_templates_exist():
    """Test that all required error templates exist."""
    print("\n" + "=" * 80)
    print("TEST: Error Templates Existence")
    print("=" * 80)

    import os

    templates_dir = os.path.join('app', 'templates', 'errors')
    required_templates = ['401.html', '403.html', '404.html', '429.html', '500.html']

    all_exist = True
    for template in required_templates:
        template_path = os.path.join(templates_dir, template)
        exists = os.path.exists(template_path)
        status = "EXISTS" if exists else "MISSING"
        print(f"  - {template}: {status}")
        if not exists:
            all_exist = False

    if all_exist:
        print("[PASS] All error templates exist")
        return True
    else:
        print("[FAIL] Some error templates are missing")
        return False


def test_error_handlers_registered():
    """Test that error handlers are properly registered."""
    print("\n" + "=" * 80)
    print("TEST: Error Handlers Registration")
    print("=" * 80)

    app = create_app(Config)

    # Check that error handlers module was imported and registered
    import sys
    if 'app.error_handlers' in sys.modules:
        print("  - Error handlers module loaded: YES")
    else:
        print("  - Error handlers module loaded: NO")
        print("[FAIL] Error handlers module not loaded")
        return False

    # Test that the app has error handlers
    error_codes = [400, 401, 403, 404, 429, 500, 503]
    handlers_registered = []

    for code in error_codes:
        if code in app.error_handler_spec[None]:
            handlers_registered.append(code)
            print(f"  - Handler for {code}: REGISTERED")
        else:
            print(f"  - Handler for {code}: NOT REGISTERED")

    if len(handlers_registered) >= 5:  # At least 5 handlers should be registered
        print(f"[PASS] {len(handlers_registered)} error handlers registered")
        return True
    else:
        print(f"[FAIL] Only {len(handlers_registered)} error handlers registered")
        return False


def test_404_error_response():
    """Test 404 error handler with HTML response."""
    print("\n" + "=" * 80)
    print("TEST: 404 Error Handler (HTML)")
    print("=" * 80)

    app = create_app(Config)

    with app.test_client() as client:
        response = client.get('/nonexistent-page-12345')

        print(f"  - Status Code: {response.status_code}")
        print(f"  - Content-Type: {response.content_type}")

        # Check status code
        if response.status_code != 404:
            print(f"[FAIL] Expected 404, got {response.status_code}")
            return False

        # Check HTML content
        if b'404' in response.data or b'Not Found' in response.data:
            print("  - Error message in response: YES")
        else:
            print("  - Error message in response: NO")
            print("[FAIL] 404 error message not found in response")
            return False

    print("[PASS] 404 error handler works correctly")
    return True


def test_404_error_json_response():
    """Test 404 error handler with JSON response."""
    print("\n" + "=" * 80)
    print("TEST: 404 Error Handler (JSON)")
    print("=" * 80)

    app = create_app(Config)

    with app.test_client() as client:
        response = client.get(
            '/api/nonexistent-endpoint',
            headers={'Accept': 'application/json'}
        )

        print(f"  - Status Code: {response.status_code}")
        print(f"  - Content-Type: {response.content_type}")

        # Check status code
        if response.status_code != 404:
            print(f"[FAIL] Expected 404, got {response.status_code}")
            return False

        # Check JSON content
        try:
            data = response.get_json()
            print(f"  - JSON Response: {data}")

            if 'error' in data and 'code' in data['error']:
                print("  - JSON error structure: VALID")
                if data['error']['code'] == 404:
                    print("[PASS] JSON 404 error handler works correctly")
                    return True
                else:
                    print(f"[FAIL] Expected error code 404, got {data['error']['code']}")
                    return False
            else:
                print("  - JSON error structure: INVALID")
                print("[FAIL] JSON response missing error structure")
                return False

        except Exception as e:
            print(f"  - Error parsing JSON: {e}")
            print("[FAIL] Response is not valid JSON")
            return False


def test_500_error_no_debug_info():
    """Test that 500 errors don't expose debug info in production mode."""
    print("\n" + "=" * 80)
    print("TEST: 500 Error - No Debug Info Exposure")
    print("=" * 80)

    from config import ProductionConfig
    app = create_app(ProductionConfig)

    # Create a route that intentionally raises an exception
    @app.route('/test-500-error')
    def trigger_500():
        raise Exception("Test exception - this should not be exposed to users")

    with app.test_client() as client:
        response = client.get('/test-500-error')

        print(f"  - Status Code: {response.status_code}")

        # Check status code
        if response.status_code != 500:
            print(f"[FAIL] Expected 500, got {response.status_code}")
            return False

        # Check that exception details are NOT in response
        response_text = response.data.decode('utf-8').lower()

        if 'test exception' in response_text or 'traceback' in response_text:
            print("  - Exception details exposed: YES")
            print("[FAIL] Production mode is exposing error details!")
            return False
        else:
            print("  - Exception details exposed: NO")
            print("  - Generic error message shown: YES")

    print("[PASS] 500 errors don't expose debug info in production")
    return True


def test_error_logging_integration():
    """Test that errors are logged to security logging system."""
    print("\n" + "=" * 80)
    print("TEST: Error Logging Integration")
    print("=" * 80)

    app = create_app(Config)

    # Check if error handlers use security logging
    import inspect
    from app import error_handlers

    source = inspect.getsource(error_handlers.log_error_event)

    if 'log_security_event' in source:
        print("  - Error handlers use log_security_event: YES")
    else:
        print("  - Error handlers use log_security_event: NO")
        print("[FAIL] Error handlers don't integrate with security logging")
        return False

    if 'SecurityEventType' in source:
        print("  - Error handlers map to SecurityEventType: YES")
    else:
        print("  - Error handlers map to SecurityEventType: NO")
        print("[FAIL] Error handlers don't use SecurityEventType")
        return False

    print("[PASS] Error handlers integrate with security logging")
    return True


def test_configuration_settings():
    """Test that production configuration has proper error handling settings."""
    print("\n" + "=" * 80)
    print("TEST: Configuration Settings")
    print("=" * 80)

    from config import ProductionConfig, DevelopmentConfig

    print("\n  Production Config:")
    print(f"    - DEBUG: {ProductionConfig.DEBUG}")
    print(f"    - PROPAGATE_EXCEPTIONS: {ProductionConfig.PROPAGATE_EXCEPTIONS}")
    print(f"    - TRAP_BAD_REQUEST_ERRORS: {ProductionConfig.TRAP_BAD_REQUEST_ERRORS}")

    print("\n  Development Config:")
    print(f"    - DEBUG: {DevelopmentConfig.DEBUG}")
    print(f"    - PROPAGATE_EXCEPTIONS: {DevelopmentConfig.PROPAGATE_EXCEPTIONS}")
    print(f"    - TRAP_BAD_REQUEST_ERRORS: {DevelopmentConfig.TRAP_BAD_REQUEST_ERRORS}")

    # Check production settings
    if ProductionConfig.DEBUG:
        print("\n[FAIL] DEBUG should be False in production")
        return False

    if ProductionConfig.PROPAGATE_EXCEPTIONS:
        print("\n[FAIL] PROPAGATE_EXCEPTIONS should be False in production")
        return False

    print("\n[PASS] Configuration settings are correct")
    return True


if __name__ == '__main__':
    print("\n" * 2)
    print("+" + "=" * 78 + "+")
    print("|" + " " * 22 + "TACTIZEN ERROR HANDLING TESTS" + " " * 27 + "|")
    print("+" + "=" * 78 + "+")

    tests = [
        test_error_templates_exist,
        test_error_handlers_registered,
        test_404_error_response,
        test_404_error_json_response,
        test_500_error_no_debug_info,
        test_error_logging_integration,
        test_configuration_settings,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print(f"Tests Passed: {passed}/{len(tests)}")
    print(f"Tests Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n[PASS] ALL ERROR HANDLING TESTS PASSED!")
    else:
        print(f"\n[FAIL] {failed} test(s) failed")

    print("=" * 80)
    print()
