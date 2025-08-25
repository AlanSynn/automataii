#!/usr/bin/env python3
"""
Static Analysis Tool for mechanism_design_tab.py
Safely identifies unused methods through comprehensive analysis
"""

import ast
import re
import sys
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MethodInfo:
    """Information about a method"""
    name: str
    line_number: int
    end_line: int
    is_private: bool
    is_static: bool
    is_property: bool
    is_slot: bool  # PyQt slot
    is_override: bool  # Overrides parent method
    has_decorators: bool
    decorators: List[str]
    calls_made: Set[str]  # Methods this method calls
    docstring: str
    complexity_score: int  # Rough complexity estimate

class MechanismTabAnalyzer:
    """Static analyzer for mechanism_design_tab.py"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.source_code = ""
        self.ast_tree = None
        self.methods: Dict[str, MethodInfo] = {}
        self.method_calls: Dict[str, Set[str]] = defaultdict(set)
        self.qt_signals: Set[str] = set()
        self.qt_slots: Set[str] = set()
        self.external_references: Set[str] = set()
        
        # Known PyQt methods that might be called by framework
        self.qt_framework_methods = {
            'closeEvent', 'paintEvent', 'mousePressEvent', 'mouseReleaseEvent',
            'mouseMoveEvent', 'keyPressEvent', 'keyReleaseEvent', 'resizeEvent',
            'showEvent', 'hideEvent', 'wheelEvent', 'contextMenuEvent',
            'dragEnterEvent', 'dragMoveEvent', 'dropEvent', 'focusInEvent',
            'focusOutEvent', 'enterEvent', 'leaveEvent', 'timerEvent'
        }
        
        # Known method patterns that are typically called externally
        self.external_call_patterns = [
            r'^on_.*',  # Event handlers
            r'^_on_.*',  # Private event handlers
            r'.*_changed$',  # Signal handlers
            r'.*_clicked$',  # Click handlers
            r'.*_selected$',  # Selection handlers
            r'.*_updated$',  # Update handlers
        ]
    
    def load_and_parse(self):
        """Load and parse the Python file"""
        try:
            self.source_code = self.file_path.read_text(encoding='utf-8')
            self.ast_tree = ast.parse(self.source_code, filename=str(self.file_path))
            logger.info(f"Successfully parsed {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to parse {self.file_path}: {e}")
            return False
        return True
    
    def analyze_methods(self):
        """Extract all methods and their information"""
        if not self.ast_tree:
            return
        
        class MethodVisitor(ast.NodeVisitor):
            def __init__(self, analyzer):
                self.analyzer = analyzer
                self.current_class = None
                self.source_lines = analyzer.source_code.split('\n')
            
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
            
            def visit_FunctionDef(self, node):
                if self.current_class:  # Only analyze class methods
                    method_info = self._extract_method_info(node)
                    self.analyzer.methods[method_info.name] = method_info
                    
                    # Extract method calls
                    calls = self._extract_method_calls(node)
                    self.analyzer.method_calls[method_info.name] = calls
                
                self.generic_visit(node)
            
            def _extract_method_info(self, node) -> MethodInfo:
                """Extract detailed information about a method"""
                name = node.name
                line_number = node.lineno
                end_line = node.end_lineno or line_number
                
                # Check decorators
                decorators = []
                is_slot = False
                is_property = False
                is_static = False
                
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name):
                        dec_name = decorator.id
                        decorators.append(dec_name)
                        if dec_name in ('pyqtSlot', 'slot'):
                            is_slot = True
                        elif dec_name == 'property':
                            is_property = True
                        elif dec_name == 'staticmethod':
                            is_static = True
                    elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                        dec_name = decorator.func.id
                        decorators.append(dec_name)
                        if dec_name in ('pyqtSlot', 'slot'):
                            is_slot = True
                
                # Get docstring
                docstring = ""
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and 
                    isinstance(node.body[0].value.value, str)):
                    docstring = node.body[0].value.value
                
                # Calculate complexity (rough estimate)
                complexity = self._calculate_complexity(node)
                
                return MethodInfo(
                    name=name,
                    line_number=line_number,
                    end_line=end_line,
                    is_private=name.startswith('_'),
                    is_static=is_static,
                    is_property=is_property,
                    is_slot=is_slot,
                    is_override=self._is_override_method(name),
                    has_decorators=len(decorators) > 0,
                    decorators=decorators,
                    calls_made=set(),  # Will be filled by _extract_method_calls
                    docstring=docstring,
                    complexity_score=complexity
                )
            
            def _extract_method_calls(self, node) -> Set[str]:
                """Extract all method calls made within this method"""
                calls = set()
                
                class CallVisitor(ast.NodeVisitor):
                    def visit_Call(self, node):
                        if isinstance(node.func, ast.Attribute):
                            # Method calls like self.method_name or obj.method
                            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                                calls.add(node.func.attr)
                        elif isinstance(node.func, ast.Name):
                            # Direct function calls
                            calls.add(node.func.id)
                        self.generic_visit(node)
                
                call_visitor = CallVisitor()
                call_visitor.visit(node)
                return calls
            
            def _calculate_complexity(self, node) -> int:
                """Calculate rough complexity score"""
                complexity = 1
                
                class ComplexityVisitor(ast.NodeVisitor):
                    def __init__(self):
                        self.complexity = 1
                    
                    def visit_If(self, node):
                        self.complexity += 1
                        self.generic_visit(node)
                    
                    def visit_For(self, node):
                        self.complexity += 1
                        self.generic_visit(node)
                    
                    def visit_While(self, node):
                        self.complexity += 1
                        self.generic_visit(node)
                    
                    def visit_Try(self, node):
                        self.complexity += 1
                        self.generic_visit(node)
                    
                    def visit_With(self, node):
                        self.complexity += 1
                        self.generic_visit(node)
                
                visitor = ComplexityVisitor()
                visitor.visit(node)
                return visitor.complexity
            
            def _is_override_method(self, name: str) -> bool:
                """Check if this method overrides a parent class method"""
                # Known Qt widget override methods
                qt_overrides = {
                    '__init__', 'closeEvent', 'paintEvent', 'mousePressEvent',
                    'mouseReleaseEvent', 'mouseMoveEvent', 'keyPressEvent',
                    'keyReleaseEvent', 'resizeEvent', 'showEvent', 'hideEvent'
                }
                return name in qt_overrides
        
        visitor = MethodVisitor(self)
        visitor.visit(self.ast_tree)
        
        # Update method calls in MethodInfo objects
        for method_name, calls in self.method_calls.items():
            if method_name in self.methods:
                self.methods[method_name].calls_made = calls
    
    def find_external_references(self):
        """Find references to methods from outside this file"""
        # This would require analyzing other files that import this class
        # For now, we'll use pattern matching to identify likely external methods
        
        for method_name, method_info in self.methods.items():
            # Check if method matches external call patterns
            for pattern in self.external_call_patterns:
                if re.match(pattern, method_name):
                    self.external_references.add(method_name)
                    break
            
            # Qt framework methods are likely called externally
            if method_name in self.qt_framework_methods:
                self.external_references.add(method_name)
            
            # Public methods (non-private) might be called externally
            if not method_info.is_private and not method_name.startswith('__'):
                self.external_references.add(method_name)
    
    def analyze_method_usage(self) -> Dict[str, Set[str]]:
        """Analyze which methods are called by which other methods"""
        called_by = defaultdict(set)
        
        for caller_name, calls in self.method_calls.items():
            for called_method in calls:
                if called_method in self.methods:
                    called_by[called_method].add(caller_name)
        
        return dict(called_by)
    
    def find_unused_methods(self) -> List[str]:
        """Find methods that are potentially unused"""
        called_by = self.analyze_method_usage()
        unused = []
        
        for method_name, method_info in self.methods.items():
            # Skip if method is called by other methods
            if method_name in called_by and called_by[method_name]:
                continue
            
            # Skip if method is likely called externally
            if method_name in self.external_references:
                continue
            
            # Skip special methods
            if method_name.startswith('__') and method_name.endswith('__'):
                continue
            
            # Skip Qt slots (might be connected via signals)
            if method_info.is_slot:
                continue
            
            # Skip property methods
            if method_info.is_property:
                continue
            
            # Skip override methods
            if method_info.is_override:
                continue
            
            unused.append(method_name)
        
        return unused
    
    def find_duplicate_methods(self) -> List[Tuple[str, str, float]]:
        """Find potentially duplicate methods based on similarity"""
        duplicates = []
        method_list = list(self.methods.items())
        
        for i, (name1, info1) in enumerate(method_list):
            for name2, info2 in method_list[i+1:]:
                similarity = self._calculate_method_similarity(info1, info2)
                if similarity > 0.8:  # High similarity threshold
                    duplicates.append((name1, name2, similarity))
        
        return duplicates
    
    def _calculate_method_similarity(self, info1: MethodInfo, info2: MethodInfo) -> float:
        """Calculate similarity between two methods"""
        # Simple similarity based on method calls and names
        if not info1.calls_made and not info2.calls_made:
            return 0.0
        
        calls1 = info1.calls_made
        calls2 = info2.calls_made
        
        if not calls1 or not calls2:
            return 0.0
        
        intersection = len(calls1.intersection(calls2))
        union = len(calls1.union(calls2))
        
        return intersection / union if union > 0 else 0.0
    
    def generate_report(self) -> str:
        """Generate comprehensive analysis report"""
        report = []
        report.append("="*80)
        report.append("MECHANISM DESIGN TAB ANALYSIS REPORT")
        report.append("="*80)
        report.append("")
        
        # Basic statistics
        total_methods = len(self.methods)
        private_methods = sum(1 for m in self.methods.values() if m.is_private)
        public_methods = total_methods - private_methods
        
        report.append(f"Total methods: {total_methods}")
        report.append(f"Public methods: {public_methods}")
        report.append(f"Private methods: {private_methods}")
        report.append("")
        
        # Method usage analysis
        called_by = self.analyze_method_usage()
        unused_methods = self.find_unused_methods()
        
        report.append(f"Methods with no internal callers: {len(unused_methods)}")
        report.append(f"Potentially external references: {len(self.external_references)}")
        report.append("")
        
        # List unused methods
        if unused_methods:
            report.append("POTENTIALLY UNUSED METHODS:")
            report.append("-" * 40)
            for method_name in sorted(unused_methods):
                method_info = self.methods[method_name]
                report.append(f"  {method_name} (line {method_info.line_number})")
                if method_info.docstring:
                    report.append(f"    Doc: {method_info.docstring[:60]}...")
                report.append(f"    Private: {method_info.is_private}, Complexity: {method_info.complexity_score}")
                report.append("")
        
        # Find duplicate methods
        duplicates = self.find_duplicate_methods()
        if duplicates:
            report.append("POTENTIALLY DUPLICATE METHODS:")
            report.append("-" * 40)
            for name1, name2, similarity in duplicates:
                report.append(f"  {name1} <-> {name2} (similarity: {similarity:.2f})")
                report.append("")
        
        # Complex methods
        complex_methods = [(name, info) for name, info in self.methods.items() 
                          if info.complexity_score > 10]
        if complex_methods:
            report.append("HIGH COMPLEXITY METHODS (>10):")
            report.append("-" * 40)
            for name, info in sorted(complex_methods, key=lambda x: x[1].complexity_score, reverse=True):
                report.append(f"  {name} (line {info.line_number}, complexity: {info.complexity_score})")
            report.append("")
        
        # Method call graph (top callers)
        report.append("TOP METHOD CALLERS:")
        report.append("-" * 40)
        method_call_counts = defaultdict(int)
        for calls in self.method_calls.values():
            for called_method in calls:
                method_call_counts[called_method] += 1
        
        top_called = sorted(method_call_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for method_name, count in top_called:
            if method_name in self.methods:
                report.append(f"  {method_name}: called {count} times")
        
        return "\n".join(report)

def main():
    """Main analysis function"""
    file_path = "src/automataii/gui/tabs/mechanism_design_tab.py"
    
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return
    
    analyzer = MechanismTabAnalyzer(file_path)
    
    logger.info("Loading and parsing file...")
    if not analyzer.load_and_parse():
        return
    
    logger.info("Analyzing methods...")
    analyzer.analyze_methods()
    
    logger.info("Finding external references...")
    analyzer.find_external_references()
    
    logger.info("Generating report...")
    report = analyzer.generate_report()
    
    # Save report
    report_file = "mechanism_tab_analysis_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(report)
    logger.info(f"Report saved to: {report_file}")

if __name__ == "__main__":
    main()