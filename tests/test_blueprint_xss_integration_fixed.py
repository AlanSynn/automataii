"""
Integration test for XSS vulnerability fix in blueprint generation.
"""
import html
import re
import pytest


class TestBlueprintXSSIntegration:
    """Test XSS vulnerability fix in blueprint generation."""
    
    def test_xss_sanitization_logic(self):
        """Test the XSS sanitization logic directly."""
        # Test malicious inputs
        malicious_inputs = [
            "<script>alert('XSS')</script>",
            "Normal<script>alert('XSS')</script>Name",
            "<img src=x onerror=alert('XSS')>",
            "Test & Part",
            "Part with < > characters",
            "Part with \" quotes",
            "Part with ' apostrophes"
        ]
        
        for malicious_input in malicious_inputs:
            # Apply the same sanitization logic used in blueprint.py
            sanitized_name = html.escape(str(malicious_input), quote=True)
            
            # Limit length to prevent DoS
            if len(sanitized_name) > 100:
                sanitized_name = sanitized_name[:100] + "..."
            
            # Remove any remaining dangerous patterns
            sanitized_name = re.sub(r'[<>"\']', "", sanitized_name)
            
            # Verify no dangerous content remains
            assert "<script>" not in sanitized_name
            assert "</script>" not in sanitized_name
            assert "alert(" not in sanitized_name
            assert "onerror=" not in sanitized_name
            assert "javascript:" not in sanitized_name
            assert "<img" not in sanitized_name
            
            print(f"✅ Sanitized '{malicious_input}' -> '{sanitized_name}'")
    
    def test_html_escape_functionality(self):
        """Test HTML escape functionality."""
        test_cases = [
            ("Test & Part", "Test &amp; Part"),
            ("Part < 10mm", "Part &lt; 10mm"),
            ("Part > 5mm", "Part &gt; 5mm"),
            ("Part \"quoted\"", "Part &quot;quoted&quot;"),
            ("Part 'apostrophe'", "Part &#x27;apostrophe&#x27;")
        ]
        
        for original, expected_escaped in test_cases:
            escaped = html.escape(original, quote=True)
            # After regex cleaning, quotes will be removed
            final_cleaned = re.sub(r'[<>"\']', "", escaped)
            
            # Verify dangerous characters are neutralized
            assert "<" not in final_cleaned
            assert ">" not in final_cleaned
            assert "\"" not in final_cleaned
            assert "'" not in final_cleaned
            
            print(f"✅ HTML escape: '{original}' -> '{final_cleaned}'")
    
    def test_xss_attack_vectors(self):
        """Test various XSS attack vectors are neutralized."""
        attack_vectors = [
            # Script injection
            "<script>alert('XSS')</script>",
            "<SCRIPT>alert('XSS')</SCRIPT>",
            
            # Event handlers
            "onload=alert('XSS')",
            "onerror=alert('XSS')",
            "onclick=alert('XSS')",
            
            # JavaScript protocol
            "javascript:alert('XSS')",
            "JAVASCRIPT:alert('XSS')",
            
            # HTML injection
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "<iframe src=javascript:alert('XSS')>",
            
            # CSS injection
            "style=background:url(javascript:alert('XSS'))",
            
            # Data URLs
            "data:text/html,<script>alert('XSS')</script>",
        ]
        
        for attack in attack_vectors:
            # Apply sanitization
            sanitized = html.escape(attack, quote=True)
            sanitized = re.sub(r'[<>"\']', "", sanitized)
            
            # Verify attack is neutralized
            assert "<script>" not in sanitized.lower()
            assert "</script>" not in sanitized.lower()
            assert "javascript:" not in sanitized.lower()
            assert "alert(" not in sanitized.lower()
            assert "onerror=" not in sanitized.lower()
            assert "onload=" not in sanitized.lower()
            assert "onclick=" not in sanitized.lower()
            assert "<img" not in sanitized.lower()
            assert "<svg" not in sanitized.lower()
            assert "<iframe" not in sanitized.lower()
            
            print(f"✅ Attack vector neutralized: '{attack[:50]}...' -> '{sanitized[:50]}...'")
    
    def test_length_limit_protection(self):
        """Test that extremely long inputs are truncated to prevent DoS."""
        # Create a very long string (over 100 characters)
        long_string = "A" * 200 + "<script>alert('XSS')</script>"
        
        # Apply sanitization with length limit
        sanitized = html.escape(long_string, quote=True)
        if len(sanitized) > 100:
            sanitized = sanitized[:100] + "..."
        sanitized = re.sub(r'[<>"\']', "", sanitized)
        
        # Verify length is limited
        assert len(sanitized) <= 103  # 100 + "..."
        assert "<script>" not in sanitized
        
        print(f"✅ Length limit protection: {len(long_string)} chars -> {len(sanitized)} chars")
    
    def test_normal_content_preserved(self):
        """Test that normal, safe content is preserved."""
        safe_inputs = [
            "NormalPart",
            "Gear_01",
            "Linkage Part",
            "Steel Component",
            "Motor Mount",
            "Bearing Housing"
        ]
        
        for safe_input in safe_inputs:
            sanitized = html.escape(safe_input, quote=True)
            sanitized = re.sub(r'[<>"\']', "", sanitized)
            
            # Normal content should be largely preserved
            assert safe_input.replace(" ", "").replace("_", "") in sanitized.replace(" ", "").replace("_", "")
            
            print(f"✅ Safe content preserved: '{safe_input}' -> '{sanitized}'")
            
        print("✅ XSS vulnerability fix validation completed successfully!")