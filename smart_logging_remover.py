#!/usr/bin/env python3
"""
Smart logging remover that handles empty blocks properly
"""

import ast
import re
from pathlib import Path
from typing import Set, List, Tuple

class SmartLoggingRemover:
    """Remove logging code while preserving syntax"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.lines = []
        self.lines_to_remove = set()
        
    def load_file(self):
        """Load the file"""
        content = self.file_path.read_text(encoding='utf-8')
        self.lines = content.split('\n')
        print(f"Loaded {self.file_path} ({len(self.lines)} lines)")
    
    def find_logging_lines(self):
        """Find all logging-related lines"""
        logging_patterns = [
            r'^\s*import\s+logging\s*$',                    # import logging
            r'^\s*from\s+logging\s+import',                 # from logging import ...
            r'^\s*logger\s*=.*logging\.getLogger',          # logger = logging.getLogger(...)
            r'^\s*logging\.',                               # logging.info, logging.debug, etc.
            r'^\s*logger\.',                                # logger.info, logger.debug, etc.
        ]
        
        # Find logging lines and their multiline continuations
        for i, line in enumerate(self.lines):
            for pattern in logging_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Mark this line for removal
                    self.lines_to_remove.add(i)
                    
                    # If it's a multiline call, find the end
                    if '(' in line and ')' not in line:
                        end_line = self._find_multiline_end(i)
                        for j in range(i, end_line + 1):
                            self.lines_to_remove.add(j)
                    break
        
        print(f"Found {len(self.lines_to_remove)} lines to remove")
    
    def _find_multiline_end(self, start_idx: int) -> int:
        """Find the end of a multiline statement"""
        paren_count = 0
        for i in range(start_idx, len(self.lines)):
            line = self.lines[i]
            paren_count += line.count('(') - line.count(')')
            if paren_count <= 0:
                return i
        return start_idx
    
    def fix_empty_blocks(self):
        """Fix empty if/else/except/for/while blocks by adding pass"""
        block_keywords = [
            r'^\s*if\s+.*:\s*$',
            r'^\s*elif\s+.*:\s*$', 
            r'^\s*else:\s*$',
            r'^\s*except.*:\s*$',
            r'^\s*try:\s*$',
            r'^\s*finally:\s*$',
            r'^\s*for\s+.*:\s*$',
            r'^\s*while\s+.*:\s*$',
            r'^\s*def\s+.*:\s*$',
            r'^\s*class\s+.*:\s*$'
        ]
        
        for i, line in enumerate(self.lines):
            # Skip lines that are being removed
            if i in self.lines_to_remove:
                continue
                
            # Check if this line starts a block
            for pattern in block_keywords:
                if re.match(pattern, line):
                    # Check if the next non-removed line is at the same or lower indentation
                    current_indent = len(line) - len(line.lstrip())
                    needs_pass = True
                    
                    # Look for content in the block
                    for j in range(i + 1, len(self.lines)):
                        if j in self.lines_to_remove:
                            continue
                            
                        next_line = self.lines[j]
                        if not next_line.strip():  # Empty line
                            continue
                            
                        next_indent = len(next_line) - len(next_line.lstrip())
                        
                        if next_indent > current_indent:
                            # Found indented content, block is not empty
                            needs_pass = False
                            break
                        elif next_indent <= current_indent:
                            # Found content at same or lower level, block is empty
                            break
                    
                    if needs_pass:
                        # Insert a 'pass' statement after this line
                        pass_line = ' ' * (current_indent + 4) + 'pass'
                        self.lines.insert(i + 1, pass_line)
                        # Update line indices for removal
                        updated_removals = set()
                        for idx in self.lines_to_remove:
                            if idx > i:
                                updated_removals.add(idx + 1)
                            else:
                                updated_removals.add(idx)
                        self.lines_to_remove = updated_removals
                    break
    
    def remove_logging_and_save(self):
        """Remove logging lines and save the result"""
        # Create cleaned content
        cleaned_lines = []
        for i, line in enumerate(self.lines):
            if i not in self.lines_to_remove:
                cleaned_lines.append(line)
        
        # Remove excessive empty lines
        final_lines = []
        prev_empty = False
        for line in cleaned_lines:
            current_empty = not line.strip()
            if current_empty and prev_empty:
                continue
            final_lines.append(line)
            prev_empty = current_empty
        
        # Save cleaned file
        cleaned_content = '\n'.join(final_lines)
        
        # Create backup
        backup_path = self.file_path.with_suffix('.py.bak2')
        if not backup_path.exists():
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.lines))
            print(f"Created backup: {backup_path}")
        
        # Save cleaned version
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
        
        original_lines = len(self.lines)
        final_line_count = len(final_lines)
        removed_lines = len(self.lines_to_remove)
        
        print(f"Original lines: {original_lines}")
        print(f"Lines removed: {removed_lines}")
        print(f"Final lines: {final_line_count}")
        print(f"Net reduction: {original_lines - final_line_count}")

def main():
    """Main function"""
    file_path = "src/automataii/gui/tabs/mechanism_design_tab.py"
    
    remover = SmartLoggingRemover(file_path)
    remover.load_file()
    remover.find_logging_lines()
    remover.fix_empty_blocks()
    remover.remove_logging_and_save()
    
    print("✅ Smart logging removal completed!")

if __name__ == "__main__":
    main()