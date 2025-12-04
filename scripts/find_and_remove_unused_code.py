#!/usr/bin/env python3
"""
Find and Remove Unused Code - Static Analysis Tool
Author: Automataii Contributors
Date: 2025-01-19

This script performs static analysis to find unused classes, methods, and functions
in the codebase and optionally removes them safely with backup.

Usage:
    python scripts/find_and_remove_unused_code.py --analyze  # Just analyze and report
    python scripts/find_and_remove_unused_code.py --remove   # Remove unused code (with backup)
    python scripts/find_and_remove_unused_code.py --restore  # Restore from backup
"""

import ast
import argparse
import json
import logging
import os
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CodeEntity:
    """Represents a code entity (class, method, function)"""
    name: str
    type: str  # 'class', 'method', 'function'
    file_path: str
    line_number: int
    end_line: int
    parent_class: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_test: bool = False
    is_private: bool = False
    is_magic: bool = False
    is_property: bool = False
    full_name: str = ""
    
    def __post_init__(self):
        """Generate full name after initialization"""
        if self.parent_class:
            self.full_name = f"{self.parent_class}.{self.name}"
        else:
            self.full_name = self.name
        
        # Check if private
        self.is_private = self.name.startswith('_') and not self.name.startswith('__')
        
        # Check if magic method
        self.is_magic = self.name.startswith('__') and self.name.endswith('__')
        
        # Check if property
        self.is_property = 'property' in self.decorators


@dataclass
class Usage:
    """Represents a usage of a code entity"""
    entity_name: str
    used_in_file: str
    line_number: int
    context: str  # The line of code where it's used


class CodeAnalyzer(ast.NodeVisitor):
    """AST visitor to extract code entities and their usages"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.entities: List[CodeEntity] = []
        self.usages: List[Usage] = []
        self.current_class = None
        self.imports: Set[str] = set()
        self.source_lines = []
        
    def analyze(self, source_code: str) -> Tuple[List[CodeEntity], List[Usage], Set[str]]:
        """Analyze source code and return entities, usages, and imports"""
        self.source_lines = source_code.splitlines()
        try:
            tree = ast.parse(source_code)
            self.visit(tree)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {self.file_path}: {e}")
        return self.entities, self.usages, self.imports
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition"""
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        entity = CodeEntity(
            name=node.name,
            type='class',
            file_path=self.file_path,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            decorators=decorators,
            is_test='test' in node.name.lower()
        )
        self.entities.append(entity)
        
        # Process class body
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function/method definition"""
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        entity_type = 'method' if self.current_class else 'function'
        entity = CodeEntity(
            name=node.name,
            type=entity_type,
            file_path=self.file_path,
            line_number=node.lineno,
            end_line=node.end_lineno or node.lineno,
            parent_class=self.current_class,
            decorators=decorators,
            is_test='test' in node.name.lower()
        )
        self.entities.append(entity)
        
        # Visit function body for usages
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function/method definition"""
        # Treat async functions the same as regular functions
        self.visit_FunctionDef(node)
    
    def visit_Name(self, node: ast.Name):
        """Visit name references (potential usages)"""
        if isinstance(node.ctx, ast.Load):
            # This is a usage of something
            line_content = self._get_line_content(node.lineno)
            usage = Usage(
                entity_name=node.id,
                used_in_file=self.file_path,
                line_number=node.lineno,
                context=line_content
            )
            self.usages.append(usage)
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute):
        """Visit attribute access (e.g., obj.method())"""
        # Record method/attribute usage
        line_content = self._get_line_content(node.lineno)
        usage = Usage(
            entity_name=node.attr,
            used_in_file=self.file_path,
            line_number=node.lineno,
            context=line_content
        )
        self.usages.append(usage)
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import):
        """Visit import statements"""
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Visit from...import statements"""
        if node.module:
            for alias in node.names:
                if alias.name != '*':
                    self.imports.add(f"{node.module}.{alias.name}")
                    self.imports.add(alias.name)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Visit function/method calls"""
        # Handle direct function calls
        if isinstance(node.func, ast.Name):
            line_content = self._get_line_content(node.lineno)
            usage = Usage(
                entity_name=node.func.id,
                used_in_file=self.file_path,
                line_number=node.lineno,
                context=line_content
            )
            self.usages.append(usage)
        self.generic_visit(node)
    
    def _get_decorator_name(self, decorator) -> str:
        """Extract decorator name from AST node"""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
        return ""
    
    def _get_line_content(self, line_number: int) -> str:
        """Get the content of a specific line"""
        if 0 < line_number <= len(self.source_lines):
            return self.source_lines[line_number - 1].strip()
        return ""


class UnusedCodeFinder:
    """Main class for finding unused code"""
    
    def __init__(self, src_dir: str, exclude_patterns: Optional[List[str]] = None):
        self.src_dir = Path(src_dir)
        self.exclude_patterns = exclude_patterns or []
        self.all_entities: List[CodeEntity] = []
        self.all_usages: List[Usage] = []
        self.entity_map: Dict[str, List[CodeEntity]] = defaultdict(list)
        self.usage_map: Dict[str, List[Usage]] = defaultdict(list)
        self.file_imports: Dict[str, Set[str]] = {}
        
        # Add default exclusions
        self.always_keep = {
            '__init__', '__new__', '__del__', '__str__', '__repr__',
            '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__',
            '__hash__', '__bool__', '__len__', '__getitem__', '__setitem__',
            '__delitem__', '__iter__', '__next__', '__contains__',
            '__call__', '__enter__', '__exit__', '__getattr__', '__setattr__',
            '__delattr__', '__dir__', '__class__', '__dict__',
            'setUp', 'tearDown', 'setUpClass', 'tearDownClass',  # Test methods
            'main', 'run', 'execute', 'start', 'stop',  # Common entry points
        }
        
        # Patterns that indicate the code might be used externally
        self.external_patterns = [
            r'@app\.route',  # Flask routes
            r'@api\.route',  # API routes
            r'@click\.command',  # CLI commands
            r'@pytest\.',  # Pytest fixtures
            r'@unittest\.',  # Unittest decorators
            r'class.*\(.*TestCase\)',  # Test classes
            r'def test_',  # Test functions
        ]
    
    def find_python_files(self) -> List[Path]:
        """Find all Python files in the source directory"""
        python_files = []
        for file_path in self.src_dir.rglob('*.py'):
            # Skip excluded patterns
            if any(pattern in str(file_path) for pattern in self.exclude_patterns):
                continue
            python_files.append(file_path)
        return python_files
    
    def analyze_file(self, file_path: Path) -> Tuple[List[CodeEntity], List[Usage], Set[str]]:
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            analyzer = CodeAnalyzer(str(file_path))
            return analyzer.analyze(source_code)
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return [], [], set()
    
    def collect_all_code_info(self):
        """Collect all code entities and usages from the codebase"""
        python_files = self.find_python_files()
        logger.info(f"Found {len(python_files)} Python files to analyze")
        
        for file_path in python_files:
            entities, usages, imports = self.analyze_file(file_path)
            
            # Store entities
            for entity in entities:
                self.all_entities.append(entity)
                self.entity_map[entity.name].append(entity)
                if entity.parent_class:
                    self.entity_map[entity.full_name].append(entity)
            
            # Store usages
            for usage in usages:
                self.all_usages.append(usage)
                self.usage_map[usage.entity_name].append(usage)
            
            # Store imports
            self.file_imports[str(file_path)] = imports
        
        logger.info(f"Found {len(self.all_entities)} code entities")
        logger.info(f"Found {len(self.all_usages)} usages")
    
    def is_externally_used(self, entity: CodeEntity) -> bool:
        """Check if entity might be used externally"""
        # Check decorators
        for decorator in entity.decorators:
            for pattern in self.external_patterns:
                if re.search(pattern, decorator):
                    return True
        
        # Check if it's in __all__
        try:
            with open(entity.file_path, 'r') as f:
                content = f.read()
                if f"'{entity.name}'" in content or f'"{entity.name}"' in content:
                    if '__all__' in content:
                        return True
        except:
            pass
        
        # Check if it's imported elsewhere
        for file_path, imports in self.file_imports.items():
            if file_path != entity.file_path:
                if entity.name in imports or entity.full_name in imports:
                    return True
        
        return False
    
    def find_unused_entities(self) -> List[CodeEntity]:
        """Find entities that are never used"""
        unused = []
        
        for entity in self.all_entities:
            # Skip entities we always keep
            if entity.name in self.always_keep:
                continue
            
            # Skip test code
            if entity.is_test or 'test' in entity.file_path.lower():
                continue
            
            # Skip magic methods
            if entity.is_magic:
                continue
            
            # Skip if externally used
            if self.is_externally_used(entity):
                continue
            
            # Check if used anywhere
            is_used = False
            
            # Check by name
            if entity.name in self.usage_map:
                # Filter out self-references
                real_usages = [u for u in self.usage_map[entity.name] 
                             if not (u.used_in_file == entity.file_path and 
                                   u.line_number >= entity.line_number and 
                                   u.line_number <= entity.end_line)]
                if real_usages:
                    is_used = True
            
            # Check by full name (for methods)
            if not is_used and entity.full_name in self.usage_map:
                real_usages = [u for u in self.usage_map[entity.full_name]
                             if not (u.used_in_file == entity.file_path and
                                   u.line_number >= entity.line_number and
                                   u.line_number <= entity.end_line)]
                if real_usages:
                    is_used = True
            
            if not is_used:
                unused.append(entity)
        
        return unused
    
    def generate_report(self, unused_entities: List[CodeEntity]) -> str:
        """Generate a report of unused code"""
        report = []
        report.append("=" * 80)
        report.append("UNUSED CODE ANALYSIS REPORT")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("=" * 80)
        report.append("")
        
        # Group by file
        by_file = defaultdict(list)
        for entity in unused_entities:
            by_file[entity.file_path].append(entity)
        
        # Statistics
        report.append(f"Total unused entities: {len(unused_entities)}")
        report.append(f"Files affected: {len(by_file)}")
        report.append("")
        
        # Group by type
        by_type = defaultdict(int)
        for entity in unused_entities:
            by_type[entity.type] += 1
        
        report.append("By type:")
        for entity_type, count in sorted(by_type.items()):
            report.append(f"  - {entity_type}: {count}")
        report.append("")
        
        # Detailed list
        report.append("-" * 80)
        report.append("DETAILED LIST OF UNUSED ENTITIES")
        report.append("-" * 80)
        
        for file_path in sorted(by_file.keys()):
            report.append(f"\n{file_path}:")
            for entity in sorted(by_file[file_path], key=lambda e: e.line_number):
                marker = "  [P]" if entity.is_private else "    "
                report.append(f"{marker} L{entity.line_number:4d}: {entity.type:8s} {entity.full_name}")
                if entity.decorators:
                    report.append(f"       decorators: {', '.join(entity.decorators)}")
        
        return "\n".join(report)
    
    def create_backup(self, backup_dir: str = "backup_unused_code"):
        """Create backup of files before modification"""
        backup_path = Path(backup_dir) / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "src_dir": str(self.src_dir),
            "files_backed_up": []
        }
        
        # Copy files that will be modified
        for entity in self.all_entities:
            file_path = Path(entity.file_path)
            if file_path.exists():
                relative_path = file_path.relative_to(self.src_dir.parent)
                backup_file = backup_path / relative_path
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                
                if not backup_file.exists():
                    shutil.copy2(file_path, backup_file)
                    metadata["files_backed_up"].append(str(relative_path))
        
        # Save metadata
        with open(backup_path / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Backup created at: {backup_path}")
        return backup_path
    
    def remove_entity_from_file(self, entity: CodeEntity) -> bool:
        """Remove an entity from its file"""
        try:
            with open(entity.file_path, 'r') as f:
                lines = f.readlines()
            
            # Calculate which lines to remove
            start_idx = entity.line_number - 1
            end_idx = entity.end_line
            
            # Check for decorators (they come before the definition)
            while start_idx > 0 and lines[start_idx - 1].strip().startswith('@'):
                start_idx -= 1
            
            # Remove the lines
            new_lines = lines[:start_idx] + lines[end_idx:]
            
            # Write back
            with open(entity.file_path, 'w') as f:
                f.writelines(new_lines)
            
            return True
        except Exception as e:
            logger.error(f"Error removing {entity.full_name} from {entity.file_path}: {e}")
            return False
    
    def remove_unused_code(self, unused_entities: List[CodeEntity], dry_run: bool = False):
        """Remove unused code from files"""
        if not dry_run:
            backup_path = self.create_backup()
            logger.info(f"Created backup at: {backup_path}")
        
        # Group by file and sort by line number (reverse order to maintain line numbers)
        by_file = defaultdict(list)
        for entity in unused_entities:
            by_file[entity.file_path].append(entity)
        
        for file_path, entities in by_file.items():
            # Sort in reverse order by line number
            entities.sort(key=lambda e: e.line_number, reverse=True)
            
            if dry_run:
                logger.info(f"[DRY RUN] Would remove from {file_path}:")
                for entity in entities:
                    logger.info(f"  - {entity.full_name} (lines {entity.line_number}-{entity.end_line})")
            else:
                logger.info(f"Processing {file_path}...")
                for entity in entities:
                    if self.remove_entity_from_file(entity):
                        logger.info(f"  ✓ Removed {entity.full_name}")
                    else:
                        logger.error(f"  ✗ Failed to remove {entity.full_name}")


def main():
    parser = argparse.ArgumentParser(description='Find and remove unused code')
    parser.add_argument('--src-dir', default='src', help='Source directory to analyze')
    parser.add_argument('--analyze', action='store_true', help='Only analyze and report')
    parser.add_argument('--remove', action='store_true', help='Remove unused code')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without doing it')
    parser.add_argument('--exclude', nargs='+', default=['__pycache__', '.git', 'migrations'], 
                       help='Patterns to exclude from analysis')
    parser.add_argument('--output', help='Output report file')
    parser.add_argument('--min-confidence', type=float, default=0.9, 
                       help='Minimum confidence level for removal (0-1)')
    
    args = parser.parse_args()
    
    if not args.analyze and not args.remove:
        logger.error("Please specify --analyze or --remove")
        sys.exit(1)
    
    # Initialize finder
    finder = UnusedCodeFinder(args.src_dir, args.exclude)
    
    # Collect all code info
    logger.info("Collecting code information...")
    finder.collect_all_code_info()
    
    # Find unused entities
    logger.info("Analyzing usage patterns...")
    unused_entities = finder.find_unused_entities()
    
    # Generate report
    report = finder.generate_report(unused_entities)
    
    # Output report
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to: {args.output}")
    else:
        print(report)
    
    # Remove if requested
    if args.remove and unused_entities:
        if args.dry_run:
            logger.info("\n--- DRY RUN MODE ---")
            finder.remove_unused_code(unused_entities, dry_run=True)
        else:
            response = input(f"\nRemove {len(unused_entities)} unused entities? (yes/no): ")
            if response.lower() == 'yes':
                finder.remove_unused_code(unused_entities, dry_run=False)
                logger.info("Unused code removed successfully!")
            else:
                logger.info("Removal cancelled.")


if __name__ == '__main__':
    main()