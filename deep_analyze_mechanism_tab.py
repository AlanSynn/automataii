#!/usr/bin/env python3
"""
Deep Static Analysis for mechanism_design_tab.py
Finds orphan method chains and more accurate duplicate detection
"""

import ast
import re
import sys
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MethodInfo:
    """Enhanced method information"""
    name: str
    line_number: int
    end_line: int
    is_private: bool
    is_static: bool
    is_property: bool
    is_slot: bool
    is_override: bool
    has_decorators: bool
    decorators: List[str]
    calls_made: Set[str]
    docstring: str
    complexity_score: int
    code_lines: List[str]  # Actual code lines for better similarity
    body_length: int

class DeepMethodAnalyzer:
    """Enhanced analyzer for finding orphan method chains"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.source_code = ""
        self.source_lines = []
        self.ast_tree = None
        self.methods: Dict[str, MethodInfo] = {}
        self.method_calls: Dict[str, Set[str]] = defaultdict(set)
        self.called_by: Dict[str, Set[str]] = defaultdict(set)  # Reverse mapping
        
        # External call patterns (more comprehensive)
        self.external_patterns = [
            r'^on_.*',           # Event handlers  
            r'^_on_.*',          # Private event handlers
            r'.*_changed$',      # Signal handlers
            r'.*_clicked$',      # Click handlers
            r'.*_selected$',     # Selection handlers
            r'.*_updated$',      # Update handlers
            r'^handle_.*',       # Handle methods
            r'^set_.*',          # Setter methods
            r'^get_.*',          # Getter methods
            r'^show.*',          # Show methods
            r'^hide.*',          # Hide methods
            r'^update.*',        # Update methods
            r'^clear.*',         # Clear methods
            r'^load.*',          # Load methods
            r'^save.*',          # Save methods
            r'Event$',           # Event methods
            r'^prepare.*',       # Prepare methods
            r'^toggle.*',        # Toggle methods
        ]
        
        # Known Qt framework methods
        self.qt_framework_methods = {
            'closeEvent', 'paintEvent', 'mousePressEvent', 'mouseReleaseEvent',
            'mouseMoveEvent', 'keyPressEvent', 'keyReleaseEvent', 'resizeEvent',
            'showEvent', 'hideEvent', 'wheelEvent', 'contextMenuEvent',
            'dragEnterEvent', 'dragMoveEvent', 'dropEvent', 'focusInEvent',
            'focusOutEvent', 'enterEvent', 'leaveEvent', 'timerEvent'
        }
        
        # Methods that are likely entry points
        self.entry_point_methods = {
            '__init__', 'main', 'run', 'start', 'stop', 'execute', 
            'setup', 'initialize', 'cleanup', 'destroy'
        }
    
    def load_and_parse(self):
        """Load and parse the Python file"""
        try:
            self.source_code = self.file_path.read_text(encoding='utf-8')
            self.source_lines = self.source_code.split('\n')
            self.ast_tree = ast.parse(self.source_code, filename=str(self.file_path))
            logger.info(f"Successfully parsed {self.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to parse {self.file_path}: {e}")
            return False
    
    def analyze_methods(self):
        """Extract all methods with enhanced information"""
        if not self.ast_tree:
            return
        
        class EnhancedMethodVisitor(ast.NodeVisitor):
            def __init__(self, analyzer):
                self.analyzer = analyzer
                self.current_class = None
            
            def visit_ClassDef(self, node):
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class
            
            def visit_FunctionDef(self, node):
                if self.current_class:  # Only analyze class methods
                    method_info = self._extract_enhanced_method_info(node)
                    self.analyzer.methods[method_info.name] = method_info
                    
                    # Extract method calls
                    calls = self._extract_method_calls(node)
                    self.analyzer.method_calls[method_info.name] = calls
                    
                    # Build reverse mapping
                    for called_method in calls:
                        self.analyzer.called_by[called_method].add(method_info.name)
                
                self.generic_visit(node)
            
            def _extract_enhanced_method_info(self, node) -> MethodInfo:
                """Extract enhanced method information"""
                name = node.name
                line_number = node.lineno
                end_line = node.end_lineno or line_number
                
                # Extract actual code lines
                code_lines = []
                if line_number <= len(self.analyzer.source_lines):
                    start_idx = max(0, line_number - 1)
                    end_idx = min(len(self.analyzer.source_lines), end_line)
                    code_lines = self.analyzer.source_lines[start_idx:end_idx]
                
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
                
                # Calculate complexity
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
                    calls_made=set(),  # Will be filled later
                    docstring=docstring,
                    complexity_score=complexity,
                    code_lines=code_lines,
                    body_length=len(code_lines)
                )
            
            def _extract_method_calls(self, node) -> Set[str]:
                """Extract all method calls made within this method"""
                calls = set()
                
                class CallVisitor(ast.NodeVisitor):
                    def visit_Call(self, node):
                        if isinstance(node.func, ast.Attribute):
                            # Method calls like self.method_name
                            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                                calls.add(node.func.attr)
                        elif isinstance(node.func, ast.Name):
                            # Direct function calls (might be methods)
                            calls.add(node.func.id)
                        self.generic_visit(node)
                
                call_visitor = CallVisitor()
                call_visitor.visit(node)
                return calls
            
            def _calculate_complexity(self, node) -> int:
                """Calculate cyclomatic complexity"""
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
                    
                    def visit_ExceptHandler(self, node):
                        self.complexity += 1
                        self.generic_visit(node)
                
                visitor = ComplexityVisitor()
                visitor.visit(node)
                return visitor.complexity
            
            def _is_override_method(self, name: str) -> bool:
                """Check if this method overrides a parent class method"""
                qt_overrides = {
                    '__init__', 'closeEvent', 'paintEvent', 'mousePressEvent',
                    'mouseReleaseEvent', 'mouseMoveEvent', 'keyPressEvent',
                    'keyReleaseEvent', 'resizeEvent', 'showEvent', 'hideEvent',
                    'wheelEvent', 'contextMenuEvent', 'focusInEvent', 'focusOutEvent'
                }
                return name in qt_overrides
        
        visitor = EnhancedMethodVisitor(self)
        visitor.visit(self.ast_tree)
        
        # Update method calls in MethodInfo objects
        for method_name, calls in self.method_calls.items():
            if method_name in self.methods:
                self.methods[method_name].calls_made = calls
    
    def find_entry_points(self) -> Set[str]:
        """Find methods that are likely entry points (called externally)"""
        entry_points = set()
        
        for method_name, method_info in self.methods.items():
            # Check if method matches external patterns
            is_external = False
            for pattern in self.external_patterns:
                if re.match(pattern, method_name):
                    is_external = True
                    break
            
            if is_external:
                entry_points.add(method_name)
                continue
            
            # Qt framework methods
            if method_name in self.qt_framework_methods:
                entry_points.add(method_name)
                continue
            
            # Entry point methods
            if method_name in self.entry_point_methods:
                entry_points.add(method_name)
                continue
            
            # Public methods (might be called externally)
            if not method_info.is_private and not method_name.startswith('__'):
                entry_points.add(method_name)
                continue
            
            # Qt slots (connected via signals)
            if method_info.is_slot:
                entry_points.add(method_name)
                continue
            
            # Property methods
            if method_info.is_property:
                entry_points.add(method_name)
                continue
            
            # Override methods
            if method_info.is_override:
                entry_points.add(method_name)
                continue
        
        return entry_points
    
    def find_reachable_methods(self, entry_points: Set[str]) -> Set[str]:
        """Find all methods reachable from entry points using BFS"""
        reachable = set()
        queue = deque(entry_points)
        reachable.update(entry_points)
        
        while queue:
            current = queue.popleft()
            
            # Add all methods called by current method
            for called_method in self.method_calls.get(current, set()):
                if called_method in self.methods and called_method not in reachable:
                    reachable.add(called_method)
                    queue.append(called_method)
        
        return reachable
    
    def find_orphan_methods(self) -> List[str]:
        """Find methods that are not reachable from any entry point"""
        entry_points = self.find_entry_points()
        reachable = self.find_reachable_methods(entry_points)
        
        orphans = []
        for method_name in self.methods:
            if method_name not in reachable:
                orphans.append(method_name)
        
        return orphans
    
    def find_orphan_chains(self) -> List[List[str]]:
        """Find chains of methods that are orphaned together"""
        orphans = set(self.find_orphan_methods())
        chains = []
        visited = set()
        
        def find_chain(method_name: str) -> List[str]:
            """DFS to find connected orphan methods"""
            if method_name in visited or method_name not in orphans:
                return []
            
            visited.add(method_name)
            chain = [method_name]
            
            # Add methods called by this method
            for called in self.method_calls.get(method_name, set()):
                if called in orphans and called not in visited:
                    chain.extend(find_chain(called))
            
            # Add methods that call this method
            for caller in self.called_by.get(method_name, set()):
                if caller in orphans and caller not in visited:
                    chain.extend(find_chain(caller))
            
            return chain
        
        for method_name in orphans:
            if method_name not in visited:
                chain = find_chain(method_name)
                if chain:
                    chains.append(sorted(chain))
        
        return chains
    
    def calculate_method_similarity(self, method1: str, method2: str) -> float:
        """Calculate similarity between two methods using multiple metrics"""
        if method1 not in self.methods or method2 not in self.methods:
            return 0.0
        
        info1 = self.methods[method1]
        info2 = self.methods[method2]
        
        # Skip if one method is too short (likely empty or simple)
        if info1.body_length < 3 or info2.body_length < 3:
            return 0.0
        
        similarities = []
        
        # 1. Method calls similarity
        calls1 = info1.calls_made
        calls2 = info2.calls_made
        
        if calls1 or calls2:
            intersection = len(calls1.intersection(calls2))
            union = len(calls1.union(calls2))
            calls_similarity = intersection / union if union > 0 else 0.0
            similarities.append(calls_similarity)
        
        # 2. Code structure similarity (simplified Levenshtein on code lines)
        code_similarity = self._calculate_code_similarity(info1.code_lines, info2.code_lines)
        similarities.append(code_similarity)
        
        # 3. Name similarity
        name_similarity = self._calculate_name_similarity(method1, method2)
        similarities.append(name_similarity)
        
        # Weighted average
        if similarities:
            weights = [0.4, 0.5, 0.1]  # Code structure is most important
            return sum(s * w for s, w in zip(similarities, weights))
        
        return 0.0
    
    def _calculate_code_similarity(self, lines1: List[str], lines2: List[str]) -> float:
        """Calculate similarity between code lines"""
        if not lines1 or not lines2:
            return 0.0
        
        # Simple approach: count common non-empty, non-comment lines
        clean_lines1 = {line.strip() for line in lines1 
                       if line.strip() and not line.strip().startswith('#')}
        clean_lines2 = {line.strip() for line in lines2 
                       if line.strip() and not line.strip().startswith('#')}
        
        if not clean_lines1 or not clean_lines2:
            return 0.0
        
        intersection = len(clean_lines1.intersection(clean_lines2))
        union = len(clean_lines1.union(clean_lines2))
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between method names"""
        # Simple approach: common prefixes/suffixes
        if name1 == name2:
            return 1.0
        
        # Remove underscores and split
        parts1 = name1.replace('_', '').lower()
        parts2 = name2.replace('_', '').lower()
        
        # Simple character-based similarity
        min_len = min(len(parts1), len(parts2))
        max_len = max(len(parts1), len(parts2))
        
        if max_len == 0:
            return 0.0
        
        common = sum(c1 == c2 for c1, c2 in zip(parts1, parts2))
        return common / max_len
    
    def find_similar_methods(self, threshold: float = 0.7) -> List[Tuple[str, str, float]]:
        """Find methods that are similar above the threshold"""
        similar_pairs = []
        method_names = list(self.methods.keys())
        
        for i, method1 in enumerate(method_names):
            for method2 in method_names[i+1:]:
                similarity = self.calculate_method_similarity(method1, method2)
                if similarity >= threshold:
                    similar_pairs.append((method1, method2, similarity))
        
        return sorted(similar_pairs, key=lambda x: x[2], reverse=True)
    
    def generate_deep_report(self) -> str:
        """Generate comprehensive deep analysis report"""
        report = []
        report.append("="*80)
        report.append("DEEP MECHANISM DESIGN TAB ANALYSIS REPORT")
        report.append("="*80)
        report.append("")
        
        # Basic statistics
        total_methods = len(self.methods)
        private_methods = sum(1 for m in self.methods.values() if m.is_private)
        
        report.append(f"Total methods: {total_methods}")
        report.append(f"Private methods: {private_methods}")
        report.append(f"Public methods: {total_methods - private_methods}")
        report.append("")
        
        # Entry point analysis
        entry_points = self.find_entry_points()
        reachable = self.find_reachable_methods(entry_points)
        orphans = self.find_orphan_methods()
        
        report.append(f"Entry points (externally callable): {len(entry_points)}")
        report.append(f"Reachable methods: {len(reachable)}")
        report.append(f"Orphan methods: {len(orphans)}")
        report.append("")
        
        # Orphan chains analysis
        orphan_chains = self.find_orphan_chains()
        if orphan_chains:
            report.append("ORPHAN METHOD CHAINS:")
            report.append("-" * 40)
            for i, chain in enumerate(orphan_chains, 1):
                report.append(f"Chain {i} ({len(chain)} methods):")
                for method_name in chain:
                    method_info = self.methods[method_name]
                    report.append(f"  - {method_name} (line {method_info.line_number}, "
                                f"complexity: {method_info.complexity_score})")
                report.append("")
        
        # Individual orphan methods
        single_orphans = [m for m in orphans 
                         if not any(m in chain for chain in orphan_chains)]
        if single_orphans:
            report.append("INDIVIDUAL ORPHAN METHODS:")
            report.append("-" * 40)
            for method_name in sorted(single_orphans):
                method_info = self.methods[method_name]
                report.append(f"  {method_name} (line {method_info.line_number})")
                if method_info.docstring:
                    report.append(f"    Doc: {method_info.docstring[:60]}...")
                calls_made = method_info.calls_made
                if calls_made:
                    report.append(f"    Calls: {', '.join(sorted(calls_made))}")
                report.append("")
        
        # Similar methods
        similar_methods = self.find_similar_methods(0.7)
        if similar_methods:
            report.append("POTENTIALLY DUPLICATE METHODS (>70% similar):")
            report.append("-" * 40)
            for method1, method2, similarity in similar_methods[:20]:  # Top 20
                info1 = self.methods[method1]
                info2 = self.methods[method2]
                report.append(f"{method1} <-> {method2} (similarity: {similarity:.2f})")
                report.append(f"  Lines: {info1.line_number} <-> {info2.line_number}")
                report.append(f"  Length: {info1.body_length} <-> {info2.body_length}")
                report.append("")
        
        # High complexity methods
        complex_methods = [(name, info) for name, info in self.methods.items() 
                          if info.complexity_score > 15]
        if complex_methods:
            report.append("HIGH COMPLEXITY METHODS (>15):")
            report.append("-" * 40)
            for name, info in sorted(complex_methods, 
                                   key=lambda x: x[1].complexity_score, reverse=True)[:10]:
                report.append(f"  {name} (line {info.line_number}, "
                            f"complexity: {info.complexity_score})")
            report.append("")
        
        return "\n".join(report)

def main():
    """Main analysis function"""
    file_path = "src/automataii/gui/tabs/mechanism_design_tab.py"
    
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return
    
    analyzer = DeepMethodAnalyzer(file_path)
    
    logger.info("Loading and parsing file...")
    if not analyzer.load_and_parse():
        return
    
    logger.info("Analyzing methods with enhanced detection...")
    analyzer.analyze_methods()
    
    logger.info("Generating deep analysis report...")
    report = analyzer.generate_deep_report()
    
    # Save report
    report_file = "mechanism_tab_deep_analysis.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(report)
    logger.info(f"Deep analysis report saved to: {report_file}")

if __name__ == "__main__":
    main()