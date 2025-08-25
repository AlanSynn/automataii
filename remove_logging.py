#!/usr/bin/env python3
"""
Remove all logging-related code from mechanism_design_tab.py
Safely removes logging calls, imports, and logging-only variables
"""

import ast
import re
import sys
import logging as system_logging
from pathlib import Path
from typing import List, Tuple, Set, Dict
from dataclasses import dataclass

# Setup system logging for this script
system_logging.basicConfig(level=system_logging.INFO, format='%(levelname)s: %(message)s')
logger = system_logging.getLogger(__name__)

@dataclass
class LoggingCall:
    """Information about a logging call"""
    line_number: int
    end_line: int
    full_line: str
    call_type: str  # 'logging.info', 'logger.debug', etc.

class LoggingRemover:
    """Remove logging calls from Python code"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.source_code = ""
        self.source_lines = []
        self.logging_calls: List[LoggingCall] = []
        self.logging_imports: Set[int] = set()  # Line numbers of logging imports
        self.logging_variables: Set[str] = set()  # Variables used only for logging
        
        # Logging method patterns
        self.logging_methods = {
            'debug', 'info', 'warning', 'warn', 'error', 'exception', 
            'critical', 'fatal', 'log'
        }
        
        # Common logging variable names
        self.common_logger_names = {'logger', 'log', '_logger', 'logging'}
    
    def load_file(self) -> bool:
        """Load the source file"""
        try:
            self.source_code = self.file_path.read_text(encoding='utf-8')
            self.source_lines = self.source_code.split('\n')
            logger.info(f"Loaded {self.file_path} ({len(self.source_lines)} lines)")
            return True
        except Exception as e:
            logger.error(f"Failed to load {self.file_path}: {e}")
            return False
    
    def find_logging_calls(self):
        """Find all logging calls using AST"""
        try:
            tree = ast.parse(self.source_code)
            
            class LoggingVisitor(ast.NodeVisitor):
                def __init__(self, remover):
                    self.remover = remover
                
                def visit_Call(self, node):
                    # Check for logging calls
                    call_info = self._analyze_call(node)
                    if call_info:
                        self.remover.logging_calls.append(call_info)
                    self.generic_visit(node)
                
                def visit_Import(self, node):
                    # Find logging imports
                    for alias in node.names:
                        if alias.name == 'logging':
                            self.remover.logging_imports.add(node.lineno)
                
                def visit_ImportFrom(self, node):
                    # Find logging imports
                    if node.module == 'logging':
                        self.remover.logging_imports.add(node.lineno)
                
                def visit_Assign(self, node):
                    # Find logger variable assignments
                    if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                        if self._is_logger_assignment(node.value, var_name):
                            self.remover.logging_variables.add(var_name)
                    self.generic_visit(node)
                
                def _analyze_call(self, node) -> LoggingCall:
                    """Analyze if this is a logging call"""
                    call_type = None
                    
                    if isinstance(node.func, ast.Attribute):
                        # Method calls like logging.info() or logger.debug()
                        attr_name = node.func.attr
                        if attr_name in self.remover.logging_methods:
                            if isinstance(node.func.value, ast.Name):
                                obj_name = node.func.value.id
                                if obj_name in self.remover.common_logger_names or obj_name == 'logging':
                                    call_type = f"{obj_name}.{attr_name}"
                    
                    elif isinstance(node.func, ast.Name):
                        # Direct function calls like info(), debug()
                        func_name = node.func.id
                        if func_name in self.remover.logging_methods:
                            call_type = func_name
                    
                    if call_type:
                        # Get the full line content
                        line_num = node.lineno
                        end_line = getattr(node, 'end_lineno', line_num)
                        
                        if line_num <= len(self.remover.source_lines):
                            full_line = self.remover.source_lines[line_num - 1]
                            
                            return LoggingCall(
                                line_number=line_num,
                                end_line=end_line or line_num,
                                full_line=full_line,
                                call_type=call_type
                            )
                    
                    return None
                
                def _is_logger_assignment(self, node, var_name: str) -> bool:
                    """Check if this assignment creates a logger"""
                    # logging.getLogger(...)
                    if (isinstance(node, ast.Call) and 
                        isinstance(node.func, ast.Attribute) and
                        isinstance(node.func.value, ast.Name) and
                        node.func.value.id == 'logging' and
                        node.func.attr == 'getLogger'):
                        return True
                    
                    # Check if variable name suggests it's a logger
                    if any(log_name in var_name.lower() for log_name in ['log', 'logger']):
                        return True
                    
                    return False
            
            visitor = LoggingVisitor(self)
            visitor.visit(tree)
            
        except SyntaxError as e:
            logger.error(f"Syntax error in file: {e}")
        except Exception as e:
            logger.error(f"Error analyzing file: {e}")
    
    def find_additional_logging_patterns(self):
        """Find additional logging patterns using regex"""
        # Pattern for multiline logging calls or complex logging
        logging_patterns = [
            r'^\s*logging\.\w+\s*\(',
            r'^\s*logger\.\w+\s*\(',
            r'^\s*log\.\w+\s*\(',
            r'^\s*_logger\.\w+\s*\(',
        ]
        
        additional_calls = []
        
        for line_num, line in enumerate(self.source_lines, 1):
            for pattern in logging_patterns:
                if re.search(pattern, line):
                    # Check if this line is not already found by AST
                    already_found = any(call.line_number == line_num 
                                      for call in self.logging_calls)
                    if not already_found:
                        # Try to find the end of the call
                        end_line = self._find_call_end(line_num - 1)
                        call_type = "regex_found"
                        
                        additional_calls.append(LoggingCall(
                            line_number=line_num,
                            end_line=end_line + 1,
                            full_line=line,
                            call_type=call_type
                        ))
                    break
        
        self.logging_calls.extend(additional_calls)
    
    def _find_call_end(self, start_idx: int) -> int:
        """Find the end line of a function call that might span multiple lines"""
        paren_count = 0
        in_call = False
        
        for i in range(start_idx, len(self.source_lines)):
            line = self.source_lines[i]
            
            for char in line:
                if char == '(':
                    paren_count += 1
                    in_call = True
                elif char == ')':
                    paren_count -= 1
                    if in_call and paren_count == 0:
                        return i
        
        return start_idx  # Fallback to same line
    
    def remove_logging_code(self) -> str:
        """Remove all logging code and return the cleaned source"""
        if not self.logging_calls and not self.logging_imports:
            logger.info("No logging code found to remove")
            return self.source_code
        
        # Sort by line number in reverse order to maintain line numbers
        all_removals = []
        
        # Add logging calls
        for call in self.logging_calls:
            all_removals.extend(range(call.line_number - 1, call.end_line))
        
        # Add import lines
        for import_line in self.logging_imports:
            all_removals.append(import_line - 1)
        
        # Remove duplicates and sort in reverse order
        lines_to_remove = sorted(set(all_removals), reverse=True)
        
        # Create new source lines
        new_lines = []
        removed_count = 0
        
        for i, line in enumerate(self.source_lines):
            if i in lines_to_remove:
                removed_count += 1
                # Check if line has other code besides logging
                if self._line_has_other_code(line):
                    # Keep the line but remove just the logging part
                    cleaned_line = self._remove_logging_from_line(line)
                    if cleaned_line.strip():  # Only add if there's still content
                        new_lines.append(cleaned_line)
            else:
                new_lines.append(line)
        
        logger.info(f"Removed {removed_count} lines of logging code")
        return '\n'.join(new_lines)
    
    def _line_has_other_code(self, line: str) -> bool:
        """Check if a line has code other than logging"""
        # Remove common logging patterns
        temp_line = line.strip()
        
        # Skip if it's purely a logging call
        logging_patterns = [
            r'^\s*logging\.\w+\s*\(',
            r'^\s*logger\.\w+\s*\(',
            r'^\s*log\.\w+\s*\(',
            r'^\s*_logger\.\w+\s*\(',
        ]
        
        for pattern in logging_patterns:
            if re.match(pattern, temp_line):
                # Check if there's a semicolon indicating multiple statements
                return ';' in line
        
        return False
    
    def _remove_logging_from_line(self, line: str) -> str:
        """Remove logging part from a line that has other code"""
        # This is a simplified approach - in practice you'd need more sophisticated parsing
        # For now, we'll be conservative and keep the line
        return line
    
    def generate_report(self) -> str:
        """Generate a report of what will be removed"""
        report = []
        report.append("="*60)
        report.append("LOGGING REMOVAL REPORT")
        report.append("="*60)
        report.append("")
        
        report.append(f"File: {self.file_path}")
        report.append(f"Total lines: {len(self.source_lines)}")
        report.append(f"Logging calls found: {len(self.logging_calls)}")
        report.append(f"Logging imports found: {len(self.logging_imports)}")
        report.append("")
        
        if self.logging_calls:
            report.append("LOGGING CALLS TO REMOVE:")
            report.append("-" * 30)
            for call in sorted(self.logging_calls, key=lambda x: x.line_number):
                report.append(f"Line {call.line_number}: {call.call_type}")
                report.append(f"  {call.full_line.strip()}")
                report.append("")
        
        if self.logging_imports:
            report.append("LOGGING IMPORTS TO REMOVE:")
            report.append("-" * 30)
            for line_num in sorted(self.logging_imports):
                if line_num <= len(self.source_lines):
                    line_content = self.source_lines[line_num - 1].strip()
                    report.append(f"Line {line_num}: {line_content}")
            report.append("")
        
        if self.logging_variables:
            report.append("LOGGING VARIABLES FOUND:")
            report.append("-" * 30)
            for var_name in sorted(self.logging_variables):
                report.append(f"  {var_name}")
            report.append("")
        
        return "\n".join(report)
    
    def save_cleaned_file(self, output_path: str = None):
        """Save the cleaned file"""
        if not output_path:
            output_path = str(self.file_path.with_suffix('.cleaned.py'))
        
        cleaned_code = self.remove_logging_code()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)
        
        logger.info(f"Cleaned file saved to: {output_path}")
        return output_path

def main():
    """Main function"""
    file_path = "src/automataii/gui/tabs/mechanism_design_tab.py"
    
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return
    
    remover = LoggingRemover(file_path)
    
    logger.info("Loading file...")
    if not remover.load_file():
        return
    
    logger.info("Finding logging calls...")
    remover.find_logging_calls()
    
    logger.info("Finding additional logging patterns...")
    remover.find_additional_logging_patterns()
    
    logger.info("Generating report...")
    report = remover.generate_report()
    
    # Save report
    with open("logging_removal_report.txt", 'w') as f:
        f.write(report)
    
    print(report)
    
    # Ask for confirmation
    response = input(f"\nRemove {len(remover.logging_calls)} logging calls and "
                    f"{len(remover.logging_imports)} imports? (yes/no): ")
    
    if response.lower() == 'yes':
        logger.info("Removing logging code...")
        cleaned_path = remover.save_cleaned_file()
        
        # Optionally replace the original file
        replace = input(f"\nReplace original file with cleaned version? (yes/no): ")
        if replace.lower() == 'yes':
            import shutil
            shutil.copy2(cleaned_path, file_path)
            logger.info(f"Original file replaced with cleaned version")
            
            # Remove the temporary cleaned file
            Path(cleaned_path).unlink()
        else:
            logger.info(f"Cleaned file saved as: {cleaned_path}")
    else:
        logger.info("Logging removal cancelled")

if __name__ == "__main__":
    main()