"""
Integration test for XSS vulnerability fix in blueprint generation.
"""
import pytest
from automataii.domain.fabrication.blueprint import generate_detailed_part_content


class TestBlueprintXSSIntegration:
    """Test XSS vulnerability fix in blueprint generation."""
    
    def test_xss_vulnerability_fix(self):
        """Test that malicious scripts are properly sanitized in blueprint generation."""
        # Test data with XSS payloads
        malicious_parts = [
            {
                "name": "<script>alert('XSS')</script>",
                "type": "gear",
                "description": "A gear with <img src=x onerror=alert('XSS')>",
                "material": "Steel <script>document.cookie='stolen';</script>",
                "dimensions": {
                    "width": 50,
                    "height": 50
                },
                "position": {"x": 100, "y": 100}
            },
            {
                "name": "NormalPart",
                "type": "linkage",
                "description": "Normal description",
                "material": "Aluminum",
                "dimensions": {
                    "width": 30,
                    "height": 20
                },
                "position": {"x": 200, "y": 200}
            }
        ]
        
        # Generate blueprint content
        svg_content = generate_detailed_part_content(malicious_parts, padding=20.0)
        
        # Verify that script tags are sanitized
        assert "<script>" not in svg_content
        assert "</script>" not in svg_content
        assert "alert(" not in svg_content
        assert "onerror=" not in svg_content
        assert "document.cookie" not in svg_content
        
        # Verify that normal content is preserved
        assert "NormalPart" in svg_content
        assert "Normal description" in svg_content
        assert "Aluminum" in svg_content
        
        # Verify the SVG structure is still valid
        assert '<svg' in svg_content
        assert '</svg>' in svg_content
        
        print("✅ XSS vulnerability fix validated - malicious scripts are sanitized")
        print(f"Generated SVG length: {len(svg_content)} characters")
    
    def test_html_entities_escaping(self):
        """Test that HTML entities are properly escaped."""
        test_parts = [
            {
                "name": "Test & Part",
                "type": "gear",
                "description": "Description with < > & \" ' characters",
                "material": "Steel & Aluminum",
                "dimensions": {"width": 50, "height": 50},
                "position": {"x": 100, "y": 100}
            }
        ]
        
        svg_content = generate_detailed_part_content(test_parts)
        
        # Verify HTML entities are escaped
        assert "&amp;" in svg_content or "Test &amp; Part" in svg_content
        assert "&lt;" in svg_content or "&gt;" in svg_content
        assert "&quot;" in svg_content or "&#39;" in svg_content
        
        print("✅ HTML entities properly escaped")
    
    def test_blueprint_generation_performance(self):
        """Test that blueprint generation still performs well after security fixes."""
        import time
        
        # Generate many parts to test performance
        large_parts_list = []
        for i in range(100):
            large_parts_list.append({
                "name": f"Part_{i}",
                "type": "gear",
                "description": f"Description for part {i}",
                "material": "Steel",
                "dimensions": {"width": 10, "height": 10},
                "position": {"x": i * 10, "y": i * 10}
            })
        
        start_time = time.time()
        svg_content = generate_detailed_part_content(large_parts_list)
        end_time = time.time()
        
        generation_time = end_time - start_time
        
        # Should complete in reasonable time (less than 5 seconds)
        assert generation_time < 5.0, f"Blueprint generation took {generation_time:.2f}s - too slow"
        assert len(svg_content) > 1000, "Generated content seems too small"
        
        print(f"✅ Blueprint generation performance: {generation_time:.2f}s for 100 parts")
        print(f"Generated SVG size: {len(svg_content)} characters")