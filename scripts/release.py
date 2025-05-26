#!/usr/bin/env python3
"""
Release script for celo-mcp package.

This script helps with version management and creating releases.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def get_current_version():
    """Get the current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found")

    content = pyproject_path.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in pyproject.toml")

    return match.group(1)


def update_version(new_version):
    """Update the version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Update version
    updated_content = re.sub(
        r'version = "[^"]+"', f'version = "{new_version}"', content
    )

    pyproject_path.write_text(updated_content)
    print(f"Updated version to {new_version} in pyproject.toml")


def run_command(cmd, check=True):
    """Run a shell command."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)

    return result


def increment_version(version, part):
    """Increment version number."""
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    major, minor, patch = map(int, parts)

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid part: {part}")

    return f"{major}.{minor}.{patch}"


def create_release(version, dry_run=False):
    """Create a new release."""
    current_version = get_current_version()
    print(f"Current version: {current_version}")
    print(f"New version: {version}")

    if not dry_run:
        # Update version
        update_version(version)

        # Commit changes
        run_command("git add pyproject.toml")
        run_command(f'git commit -m "Bump version to {version}"')

        # Create and push tag
        tag_name = f"v{version}"
        run_command(f'git tag -a {tag_name} -m "Release {version}"')
        run_command(f"git push origin {tag_name}")
        run_command("git push")

        print(f"✅ Release {version} created successfully!")
        print(f"🏷️  Tag: {tag_name}")
        print("🚀 GitHub Actions will now build and publish to PyPI")
    else:
        print("🔍 Dry run - no changes made")


def main():
    parser = argparse.ArgumentParser(description="Release management for celo-mcp")
    parser.add_argument(
        "action",
        choices=["current", "patch", "minor", "major", "custom"],
        help="Action to perform",
    )
    parser.add_argument(
        "--version", help="Custom version (required for 'custom' action)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    if args.action == "current":
        current = get_current_version()
        print(f"Current version: {current}")
        return

    current_version = get_current_version()

    if args.action == "custom":
        if not args.version:
            print("Error: --version is required for custom action")
            sys.exit(1)
        new_version = args.version
    else:
        new_version = increment_version(current_version, args.action)

    create_release(new_version, args.dry_run)


if __name__ == "__main__":
    main()
