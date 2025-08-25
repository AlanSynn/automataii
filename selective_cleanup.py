#!/usr/bin/env python3
"""
Selective unused code cleanup - focusing on clearly safe removals
"""

import sys
import os
sys.path.append('scripts')

from find_and_remove_unused_code import UnusedCodeFinder

def main():
    # Initialize the finder
    finder = UnusedCodeFinder('src/automataii')
    
    # Collect code info
    print("Collecting code information...")
    finder.collect_all_code_info()
    
    # Find unused entities
    print("Finding unused entities...")
    unused_entities = finder.find_unused_entities()
    
    # Filter to only the safest removals
    safe_removals = []
    
    for entity in unused_entities:
        # Only remove private methods that are clearly dead code
        if (entity.is_private and 
            not entity.decorators and 
            not any(pattern in entity.file_path for pattern in ['interface', 'abstract', 'base']) and
            not any(keyword in entity.name.lower() for keyword in ['test', 'mock', 'stub'])):
            safe_removals.append(entity)
        
        # Remove clearly unused public methods in specific files
        elif (entity.file_path.endswith('model_downloader.py') or
              entity.file_path.endswith('selectors.py') or  
              entity.file_path.endswith('mechanism_debug.py')):
            safe_removals.append(entity)
    
    print(f"Found {len(safe_removals)} safe removals out of {len(unused_entities)} total unused")
    
    # Show what we'd remove
    for entity in safe_removals:
        print(f"Would remove: {entity.full_name} in {entity.file_path}:{entity.line_number}")
    
    # Ask for confirmation
    if safe_removals:
        response = input(f"\nRemove {len(safe_removals)} unused items? (yes/no): ")
        if response.lower() == 'yes':
            finder.remove_unused_code(safe_removals, dry_run=False)
            print("Unused code removed!")
        else:
            print("Removal cancelled.")

if __name__ == '__main__':
    main()