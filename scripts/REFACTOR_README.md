# Automataii Refactoring Guide

## Overview

This directory contains tools for safely refactoring the Automataii codebase from its current structure to a clean Hexagonal Architecture.

## Files

- `refactor_tool.py` - Main refactoring orchestration tool
- `REFACTOR_ANALYSIS.md` - Detailed architectural analysis and migration plan

## Quick Start

### 1. Analyze Current Codebase

```bash
python scripts/refactor_tool.py --analyze --verbose
```

This will:
- Parse all Python files
- Build dependency graph
- Identify import patterns
- Generate statistics

### 2. Preview Phase 1 (Dry Run)

```bash
python scripts/refactor_tool.py --phase 1 --dry-run --verbose
```

This will show what changes would be made without actually modifying files.

### 3. Execute Phase 1

```bash
python scripts/refactor_tool.py --phase 1 --verbose
```

This will:
- Create backup in `.refactor_backup/`
- Create target directory structure
- Run validation checks

### 4. Validate Application

```bash
uv run automataii
```

Verify the application still works correctly.

### 5. Execute Subsequent Phases

```bash
python scripts/refactor_tool.py --phase 2 --verbose
python scripts/refactor_tool.py --phase 3 --verbose
# ... and so on
```

### 6. Restore from Backup (if needed)

```bash
python scripts/refactor_tool.py --restore
```

## Migration Phases

### Phase 1: Create Target Structure
- **Status:** Safe (no file moves)
- **Duration:** ~1 minute
- **Risk:** None
- **Operations:**
  - Create new directory tree
  - Create `__init__.py` files
  - No imports rewritten

### Phase 2: Extract Domain Logic
- **Status:** Medium risk
- **Duration:** ~5 minutes
- **Risk:** Import errors
- **Operations:**
  - Move `mechanisms/` → `domain/mechanisms/`
  - Merge `animate/` + `animation/` → `domain/animation/`
  - Move `kinematics/` → `domain/kinematics/`
  - Rewrite all imports

### Phase 3: Consolidate UI
- **Status:** High risk
- **Duration:** ~10 minutes
- **Risk:** Import errors, broken UI
- **Operations:**
  - Merge `gui/` + `ui/` → `presentation/qt/`
  - Flatten deep nesting
  - Rewrite all imports

### Phase 4: Refactor Application Layer
- **Status:** Medium risk
- **Duration:** ~5 minutes
- **Risk:** Import errors
- **Operations:**
  - Move `services/` → `application/`
  - Move `scenarios/` → `application/scenarios/`
  - Rewrite all imports

### Phase 5: Infrastructure Adapters
- **Status:** Low risk
- **Duration:** ~5 minutes
- **Risk:** Minor import errors
- **Operations:**
  - Move `core/serialization/` → `infrastructure/persistence/`
  - Move `core/project/` → `infrastructure/persistence/project/`
  - Rewrite all imports

## Validation Checkpoints

After each phase, the tool automatically runs:

1. **Syntax Validation**
   ```bash
   python -m py_compile src/automataii/**/*.py
   ```

2. **Import Validation**
   ```bash
   python -c "import automataii"
   ```

3. **Application Launch**
   ```bash
   timeout 15 uv run automataii
   ```

## Safety Features

### 1. Automatic Backups
- Created before each execution phase
- Stored in `.refactor_backup/`
- Includes git commit hash

### 2. Git Integration
- Uses `git mv` to preserve history
- Can be rolled back with git

### 3. Dry Run Mode
- Preview all changes
- No files modified
- See exact operations

### 4. Validation Gates
- Automatic validation after each phase
- Fails fast on errors
- Detailed error reporting

## Rollback Strategies

### Option 1: Restore from Backup
```bash
python scripts/refactor_tool.py --restore
```

### Option 2: Git Rollback
```bash
git status
git reset --hard HEAD~1  # or specific commit
```

### Option 3: Manual Rollback
If both fail, the backup is in `.refactor_backup/src/`

## Monitoring Progress

### Metrics Reported

- **Files Moved:** Count of files relocated
- **Imports Rewritten:** Count of import statements modified
- **Errors:** Count of failures
- **Warnings:** Count of non-critical issues

### Log Levels

- `INFO` - Standard progress messages
- `DEBUG` - Detailed operation logs (use `--verbose`)
- `WARNING` - Non-critical issues
- `ERROR` - Critical failures

## Common Issues

### Issue 1: Import Not Found

**Symptom:**
```
ModuleNotFoundError: No module named 'automataii.mechanisms'
```

**Solution:**
```bash
# Check if migration map is correct
grep "mechanisms" scripts/refactor_tool.py

# Manually fix import
sed -i '' 's/automataii.mechanisms/automataii.domain.mechanisms/g' file.py
```

### Issue 2: Circular Dependencies

**Symptom:**
```
ImportError: cannot import name 'X' from partially initialized module 'Y'
```

**Solution:**
- Move import inside function (lazy import)
- Refactor to eliminate circular dependency
- Use Protocol/ABC for type hints

### Issue 3: Application Won't Start

**Symptom:**
```
Application failed to start
```

**Solution:**
```bash
# Check detailed logs
uv run automataii 2>&1 | tee app.log

# Restore backup
python scripts/refactor_tool.py --restore
```

## Best Practices

1. **Always dry-run first**
   ```bash
   python scripts/refactor_tool.py --phase N --dry-run
   ```

2. **Commit after each successful phase**
   ```bash
   git add .
   git commit -m "refactor: complete phase N"
   ```

3. **Test thoroughly**
   - Launch application
   - Test each tab
   - Test mechanism design workflow
   - Test blueprint export

4. **Keep backups**
   - Don't delete `.refactor_backup/` until all phases complete
   - Keep git history clean

## Customization

### Modify Migration Map

Edit `MIGRATION_MAP` in `refactor_tool.py`:

```python
MIGRATION_MAP = {
    "old/path": "new/path",
    # Add custom mappings here
}
```

### Modify Import Rewrite Rules

Edit `IMPORT_REWRITE_MAP` in `refactor_tool.py`:

```python
IMPORT_REWRITE_MAP = {
    "from old.module": "from new.module",
    # Add custom rules here
}
```

### Add Custom Validation

Extend `Validator` class:

```python
class Validator:
    @staticmethod
    def validate_custom() -> bool:
        # Your custom validation logic
        pass
```

## Architecture Decision Records (ADRs)

See `REFACTOR_ANALYSIS.md` for detailed architectural decisions.

## Support

If you encounter issues:

1. Check logs for errors
2. Review `REFACTOR_ANALYSIS.md`
3. Restore from backup if needed
4. Create an issue with logs attached

## Success Criteria

- [ ] All phases completed without errors
- [ ] Application starts successfully
- [ ] All tabs load correctly
- [ ] Mechanism design workflow works
- [ ] Blueprint export works
- [ ] Image processing works
- [ ] No import depth > 3 levels
- [ ] No circular dependencies
- [ ] Clean git history

## Timeline

- **Analysis:** 10 minutes
- **Phase 1:** 5 minutes
- **Phase 2:** 30 minutes (+ testing)
- **Phase 3:** 45 minutes (+ testing)
- **Phase 4:** 20 minutes (+ testing)
- **Phase 5:** 20 minutes (+ testing)
- **Total:** ~2-3 hours

## Next Steps

After completing all phases:

1. **Clean up**
   ```bash
   rm -rf .refactor_backup/
   ```

2. **Update documentation**
   - Update README.md with new structure
   - Update import examples
   - Update architecture diagrams

3. **Create PR**
   ```bash
   git push origin refactoring/architecture
   # Create PR for review
   ```

4. **Run full test suite**
   ```bash
   uv run pytest tests/
   ```

---

**Remember:** Always test thoroughly after each phase. It's better to catch issues early than to have to rollback multiple phases.
