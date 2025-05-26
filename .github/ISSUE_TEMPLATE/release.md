---
name: Release
about: Plan a new release
title: "Release v[VERSION]"
labels: "release"
assignees: ""
---

## Release Checklist

### Pre-Release

- [ ] All planned features/fixes are merged
- [ ] Tests are passing on main branch
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated (if applicable)
- [ ] Version number is decided: `[VERSION]`

### Release Type

- [ ] Patch (bug fixes, small improvements)
- [ ] Minor (new features, backward compatible)
- [ ] Major (breaking changes)

### Release Process

- [ ] Run `python scripts/release.py [patch|minor|major]` or `make release-[patch|minor|major]`
- [ ] Verify GitHub Actions workflow completes successfully
- [ ] Verify package is published to PyPI
- [ ] Test installation: `uvx install celo-mcp`
- [ ] Update any dependent projects/documentation

### Post-Release

- [ ] Announce release (if applicable)
- [ ] Close this issue
- [ ] Plan next release (if applicable)

## Release Notes

### New Features

-

### Bug Fixes

-

### Breaking Changes

-

### Other Changes

-

## Testing Instructions

```bash
# Test the new release
uvx install celo-mcp
uvx celo-mcp --help

# Test in Claude Desktop
# Add to claude_desktop_config.json and restart Claude
```
