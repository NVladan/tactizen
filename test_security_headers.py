"""
Script to test security headers implementation.
Run this script to verify that all security headers are properly configured.
"""

from app import create_app
from config import Config


def test_security_headers():
    """Test that security headers are properly applied to responses."""
    app = create_app(Config)

    with app.test_client() as client:
        # Make a request to the index page
        response = client.get('/')

        print("=" * 80)
        print("SECURITY HEADERS TEST")
        print("=" * 80)
        print()

        # Expected security headers
        expected_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin',
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Content-Security-Policy': None  # Will check separately
        }

        print("Testing Security Headers:")
        print("-" * 80)

        all_passed = True
        for header_name, expected_value in expected_headers.items():
            actual_value = response.headers.get(header_name)

            if header_name == 'Content-Security-Policy':
                # Just check if CSP header exists
                if actual_value:
                    print(f"[PASS] {header_name}: PRESENT")
                    print(f"  Value: {actual_value[:100]}...")
                else:
                    print(f"[FAIL] {header_name}: MISSING")
                    all_passed = False
            else:
                if actual_value == expected_value:
                    print(f"[PASS] {header_name}: {actual_value}")
                else:
                    print(f"[FAIL] {header_name}:")
                    print(f"  Expected: {expected_value}")
                    print(f"  Actual:   {actual_value}")
                    all_passed = False

        print()
        print("=" * 80)

        if all_passed:
            print("[PASS] ALL SECURITY HEADERS TESTS PASSED")
        else:
            print("[FAIL] SOME SECURITY HEADERS TESTS FAILED")

        print("=" * 80)
        print()

        # Print all response headers for debugging
        print("All Response Headers:")
        print("-" * 80)
        for header_name, header_value in response.headers:
            print(f"{header_name}: {header_value}")

        print()
        print("=" * 80)

        return all_passed


def test_csp_directives():
    """Test Content Security Policy directives."""
    app = create_app(Config)

    with app.test_client() as client:
        response = client.get('/')
        csp_header = response.headers.get('Content-Security-Policy')

        if not csp_header:
            print("✗ Content-Security-Policy header not found")
            return False

        print()
        print("=" * 80)
        print("CONTENT SECURITY POLICY ANALYSIS")
        print("=" * 80)
        print()

        # Expected CSP directives
        expected_directives = [
            'default-src',
            'script-src',
            'style-src',
            'font-src',
            'img-src',
            'connect-src',
            'frame-src',
            'object-src',
            'base-uri',
            'form-action',
            'frame-ancestors',
            'upgrade-insecure-requests',
            'block-all-mixed-content'
        ]

        print("CSP Directives:")
        print("-" * 80)

        all_present = True
        for directive in expected_directives:
            if directive in csp_header:
                # Extract the value for this directive
                parts = csp_header.split(';')
                for part in parts:
                    if part.strip().startswith(directive):
                        print(f"[PASS] {part.strip()}")
                        break
            else:
                print(f"[FAIL] {directive}: MISSING")
                all_present = False

        print()
        print("=" * 80)

        if all_present:
            print("[PASS] ALL CSP DIRECTIVES PRESENT")
        else:
            print("[FAIL] SOME CSP DIRECTIVES MISSING")

        print("=" * 80)
        print()

        # Check for unsafe directives
        print("Security Analysis:")
        print("-" * 80)

        if "'unsafe-inline'" in csp_header:
            print("[WARNING] 'unsafe-inline' detected in CSP")
            print("  This weakens XSS protection. Consider using nonces or hashes.")

        if "'unsafe-eval'" in csp_header:
            print("[WARNING] 'unsafe-eval' detected in CSP")
            print("  This allows dynamic code execution. Remove if not needed.")

        if "*" in csp_header:
            print("[WARNING] Wildcard (*) detected in CSP")
            print("  This allows any source. Consider being more specific.")

        print()
        print("=" * 80)

        return all_present


if __name__ == '__main__':
    print("\n" * 2)
    print("+" + "=" * 78 + "+")
    print("|" + " " * 22 + "TACTIZEN SECURITY HEADERS TEST" + " " * 26 + "|")
    print("+" + "=" * 78 + "+")
    print()

    headers_passed = test_security_headers()
    csp_passed = test_csp_directives()

    print()
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)

    if headers_passed and csp_passed:
        print("[PASS] ALL TESTS PASSED - Security headers are properly configured!")
    else:
        print("[FAIL] SOME TESTS FAILED - Please review the output above")

    print("=" * 80)
    print()
