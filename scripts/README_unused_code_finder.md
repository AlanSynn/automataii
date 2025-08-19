# Unused Code Finder - Documentation

## Overview
This script performs static analysis to find and optionally remove unused classes, methods, and functions from your Python codebase.

## Features
- **Static Analysis**: Uses AST (Abstract Syntax Tree) parsing for accurate code analysis
- **Safe Removal**: Creates automatic backups before removing any code
- **Smart Detection**: Recognizes common patterns like test code, magic methods, and framework callbacks
- **Detailed Reports**: Generates comprehensive reports of unused code
- **Dry Run Mode**: Preview changes before applying them

## Usage

### Basic Commands

```bash
# Analyze and generate report (no changes made)
uv run python scripts/find_and_remove_unused_code.py --analyze

# Analyze and save report to file
uv run python scripts/find_and_remove_unused_code.py --analyze --output unused_code_report.txt

# Remove unused code (with confirmation prompt)
uv run python scripts/find_and_remove_unused_code.py --remove

# Dry run - see what would be removed without actually removing
uv run python scripts/find_and_remove_unused_code.py --remove --dry-run

# Analyze specific directory
uv run python scripts/find_and_remove_unused_code.py --src-dir src/automataii --analyze

# Exclude additional patterns
uv run python scripts/find_and_remove_unused_code.py --analyze --exclude __pycache__ .git test_*
```

## What It Detects

### Unused Code Detection
The script identifies:
- Classes that are never instantiated
- Methods that are never called
- Functions that are never invoked
- Private methods (`_method`) that are unused within their class
- Properties that are never accessed

### Automatic Exclusions
The script automatically excludes:
- Magic methods (`__init__`, `__str__`, etc.)
- Test methods (`setUp`, `tearDown`, test functions)
- Common entry points (`main`, `run`, `execute`)
- Framework callbacks (Qt signals/slots, Flask routes, etc.)
- Decorated functions that might be used externally
- Code referenced in `__all__` exports

## Safety Features

### Backup System
- Creates timestamped backups before any removal
- Backups stored in `backup_unused_code/YYYYMMDD_HHMMSS/`
- Includes metadata about what was backed up
- Can restore from backup if needed

### Conservative Approach
- Requires explicit confirmation before removal
- Skips code that might be used externally
- Preserves decorators and their targets
- Maintains test infrastructure

## Limitations

### Known Limitations
1. **Dynamic Usage**: Cannot detect dynamic attribute access (`getattr`, `setattr`)
2. **String-based Imports**: May miss `importlib` or string-based imports
3. **Framework Callbacks**: Some framework patterns might not be recognized
4. **Cross-file Dependencies**: Complex inheritance patterns might be missed
5. **Metaclasses**: Dynamic class/method creation not fully supported

### False Positives
The script may incorrectly identify as unused:
- Qt/PyQt methods called by the framework
- Event handlers registered dynamically
- Methods called via string names
- Plugin systems and extensions
- Serialization methods

### False Negatives
The script may miss:
- Dead code within functions
- Unused imports (use `flake8` or `autoflake` for this)
- Unused variables within methods
- Redundant conditionals

## Best Practices

### Before Running
1. **Commit your changes**: Ensure git status is clean
2. **Run tests**: Make sure all tests pass
3. **Review the report**: Always analyze first before removing

### Review Process
1. Run analysis: `--analyze --output report.txt`
2. Review the report carefully
3. Run dry-run: `--remove --dry-run`
4. Confirm changes look correct
5. Run actual removal: `--remove`
6. Run tests again to ensure nothing broke

### Post-Removal
1. Run your test suite
2. Check key functionality manually
3. Review git diff before committing
4. Keep backup for a few days

## Integration with CI/CD

You can integrate this into your CI pipeline:

```yaml
# Example GitHub Actions workflow
- name: Check for unused code
  run: |
    python scripts/find_and_remove_unused_code.py --analyze --output unused.txt
    if [ -s unused.txt ]; then
      echo "::warning::Found unused code. See artifacts for details."
    fi
```

## Report Format

The report includes:
- Summary statistics
- Breakdown by type (class/method/function)
- File-by-file listing
- Line numbers for each unused entity
- Decorator information
- Private method indicators `[P]`

## Recovery

If something goes wrong:

1. **From Backup**:
   ```bash
   # Backups are in backup_unused_code/
   # Copy files back from the latest backup directory
   ```

2. **From Git**:
   ```bash
   git checkout -- .  # Revert all changes
   ```

3. **Selective Revert**:
   ```bash
   git checkout -- path/to/specific/file.py
   ```

## Advanced Options

### Confidence Level
```bash
# Only remove with high confidence (default 0.9)
--min-confidence 0.95
```

### Custom Patterns
Edit the script to add custom patterns:
- `always_keep`: Method names to never remove
- `external_patterns`: Decorator patterns indicating external usage
- `exclude_patterns`: File patterns to skip

## Recommendations

1. **Start Small**: Analyze a single module first
2. **Manual Review**: Always review critical modules manually
3. **Incremental Removal**: Remove in small batches
4. **Test Coverage**: Ensure good test coverage before removal
5. **Documentation**: Update docs after significant removals

## Troubleshooting

### "Syntax error in file..."
- The file has syntax errors; fix those first

### "Too many unused entities"
- Normal for large codebases
- Review in sections
- Some may be false positives

### "Removal failed"
- Check file permissions
- Ensure no other process is using the file
- Review the backup and restore if needed

## Contributing

To improve the script:
1. Add new framework patterns to `external_patterns`
2. Enhance AST visitor for better detection
3. Add support for more Python features
4. Improve cross-file dependency analysis

## License

This script is part of the Automataii project and follows the same license.