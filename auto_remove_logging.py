#!/usr/bin/env python3
"""
Automatically remove all logging-related code from mechanism_design_tab.py
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

class AutoLoggingRemover:
    """Automatically remove logging calls from Python code"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.source_lines = []
        self.lines_to_remove = set()
        
    def load_file(self) -> bool:
        """Load the source file"""
        try:
            content = self.file_path.read_text(encoding='utf-8')
            self.source_lines = content.split('\n')
            logger.info(f"Loaded {self.file_path} ({len(self.source_lines)} lines)")
            return True
        except Exception as e:
            logger.error(f"Failed to load {self.file_path}: {e}")
            return False
    
    def find_logging_lines(self):
        """Find lines containing logging calls using regex patterns"""
        logging_patterns = [
            r'^\s*import\s+logging\s*$',                    # import logging
            r'^\s*from\s+logging\s+import',                 # from logging import ...
            r'^\s*logger\s*=.*logging\.getLogger',          # logger = logging.getLogger(...)
            r'^\s*logging\.\w+\s*\(',                       # logging.info(, logging.debug(, etc.
            r'^\s*logger\.\w+\s*\(',                        # logger.info(, logger.debug(, etc.
            r'.*logging\.(debug|info|warning|error|exception|critical|fatal|log)\s*\(',  # Any logging call
            r'.*logger\.(debug|info|warning|error|exception|critical|fatal|log)\s*\(',   # Any logger call
        ]
        
        removed_count = 0
        
        for line_idx, line in enumerate(self.source_lines):
            for pattern in logging_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check if this is a multiline logging call
                    end_line_idx = self._find_multiline_call_end(line_idx, line)
                    
                    # Mark all lines of this logging call for removal
                    for i in range(line_idx, end_line_idx + 1):
                        if i not in self.lines_to_remove:
                            self.lines_to_remove.add(i)
                            removed_count += 1
                    break
        
        logger.info(f"Found {removed_count} lines with logging code to remove")
    
    def _find_multiline_call_end(self, start_idx: int, first_line: str) -> int:
        """Find the end of a potentially multiline function call"""
        if not ('(' in first_line and ')' not in first_line):
            # Single line call
            return start_idx
        
        # Count parentheses to find the end
        paren_count = first_line.count('(') - first_line.count(')')
        current_idx = start_idx
        
        while paren_count > 0 and current_idx + 1 < len(self.source_lines):
            current_idx += 1
            line = self.source_lines[current_idx]
            paren_count += line.count('(') - line.count(')')
        
        return current_idx
    
    def remove_empty_lines(self):
        """Remove consecutive empty lines that result from logging removal"""
        # This will be applied after removing logging lines
        pass
    
    def create_cleaned_file(self) -> str:
        """Create the cleaned version of the file"""
        cleaned_lines = []
        
        for i, line in enumerate(self.source_lines):
            if i not in self.lines_to_remove:
                cleaned_lines.append(line)
        
        # Remove excessive empty lines
        final_lines = []
        prev_empty = False
        
        for line in cleaned_lines:
            current_empty = not line.strip()
            
            if current_empty and prev_empty:
                continue  # Skip consecutive empty lines
            
            final_lines.append(line)
            prev_empty = current_empty
        
        return '\n'.join(final_lines)
    
    def save_cleaned_file(self):
        """Save the cleaned file, replacing the original"""
        cleaned_content = self.create_cleaned_file()
        
        # Create backup
        backup_path = self.file_path.with_suffix('.bak')
        self.file_path.rename(backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        # Save cleaned version
        self.file_path.write_text(cleaned_content, encoding='utf-8')
        
        new_line_count = len(cleaned_content.split('\n'))
        removed_lines = len(self.source_lines) - new_line_count
        
        logger.info(f"Saved cleaned file: {self.file_path}")
        logger.info(f"Lines removed: {removed_lines}")
        logger.info(f"New line count: {new_line_count}")
    
    def generate_summary(self) -> str:
        """Generate a summary of changes"""
        summary = []
        summary.append("="*60)
        summary.append("LOGGING REMOVAL SUMMARY")
        summary.append("="*60)
        summary.append(f"File: {self.file_path}")
        summary.append(f"Original lines: {len(self.source_lines)}")
        summary.append(f"Lines with logging: {len(self.lines_to_remove)}")
        summary.append(f"Lines after cleaning: {len(self.source_lines) - len(self.lines_to_remove)}")
        summary.append("")
        
        # Show first few removed lines as examples
        removed_lines = sorted(self.lines_to_remove)
        summary.append("Examples of removed lines:")
        for i, line_idx in enumerate(removed_lines[:10]):
            if line_idx < len(self.source_lines):
                line_content = self.source_lines[line_idx].strip()
                if line_content:  # Only show non-empty lines
                    summary.append(f"  Line {line_idx + 1}: {line_content}")
        
        if len(removed_lines) > 10:
            summary.append(f"  ... and {len(removed_lines) - 10} more lines")
        
        return '\n'.join(summary)

def main():
    """Main function"""
    file_path = "src/automataii/gui/tabs/mechanism_design_tab.py"
    
    if not Path(file_path).exists():
        logger.error(f"File not found: {file_path}")
        return
    
    remover = AutoLoggingRemover(file_path)
    
    logger.info("Loading file...")
    if not remover.load_file():
        return
    
    logger.info("Finding logging lines...")
    remover.find_logging_lines()
    
    if not remover.lines_to_remove:
        logger.info("No logging lines found to remove")
        return
    
    logger.info("Generating summary...")
    summary = remover.generate_summary()
    print(summary)
    
    # Save summary to file
    with open("logging_removal_summary.txt", 'w') as f:
        f.write(summary)
    
    logger.info("Removing logging code and saving cleaned file...")
    remover.save_cleaned_file()
    
    logger.info("✅ Logging removal completed successfully!")

if __name__ == "__main__":
    main()