#!/usr/bin/env python3
"""Update README badges with current versions from pyproject.toml.

This script reads versions of FastAPI, WhisperX, CUDA, and Python from pyproject.toml,
then updates the badge section in README.md between marker comments.

Usage:
    python scripts/update-badges.py [--dry-run]

Options:
    --dry-run    Show changes without modifying files
"""

import argparse
import re
import sys
from pathlib import Path


def get_python_version() -> str:
    """Get Python version from sys.version_info.

    Returns:
        Python version string (e.g., "3.11")
    """
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def get_fastapi_version() -> str:
    """Get FastAPI version from pyproject.toml.

    Returns:
        FastAPI version string (e.g., "0.128.0")
    """
    return get_version_from_pyproject("fastapi")


def get_whisperx_version() -> str:
    """Get WhisperX version from pyproject.toml.

    Returns:
        WhisperX version string (e.g., "3.7.4")
    """
    return get_version_from_pyproject("whisperx")


def get_cuda_version() -> str:
    """Get CUDA version from pyproject.toml.

    Returns:
        CUDA version string (e.g., "12.8") or "n/a" if not found
    """
    return get_cuda_version_from_pyproject()


def get_version_from_pyproject(package: str) -> str:
    """Extract package version from pyproject.toml.

    Args:
        package: Package name to search for

    Returns:
        Version string or "unknown" if not found
    """
    repo_root = Path(__file__).parent.parent
    pyproject_path = repo_root / "pyproject.toml"

    if not pyproject_path.exists():
        return "unknown"

    try:
        content = pyproject_path.read_text()

        # Try to find the package in dependencies
        # Pattern matches: package==version or package<=version or package>=version
        pattern = rf"{package}\s*[=<>]+\s*([\d.]+)"
        match = re.search(pattern, content, re.IGNORECASE)

        if match:
            version = match.group(1)
            # Clean up version (remove any trailing conditions)
            version = version.split(",")[0].strip()
            return version

        return "unknown"
    except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError) as e:
        print(f"Warning: Could not read pyproject.toml: {e}", file=sys.stderr)
        return "unknown"


def get_cuda_version_from_pyproject() -> str:
    """Extract CUDA version from pyproject.toml PyTorch index configuration.

    Returns:
        CUDA version string (e.g., "12.8") or "n/a" if not found
    """
    repo_root = Path(__file__).parent.parent
    pyproject_path = repo_root / "pyproject.toml"

    if not pyproject_path.exists():
        return "n/a"

    try:
        content = pyproject_path.read_text()

        # Look for PyTorch CUDA index URL
        # Pattern: url = "https://download.pytorch.org/whl/cu128"
        pattern = r'url\s*=\s*"https://download\.pytorch\.org/whl/cu(\d+)"'
        match = re.search(pattern, content)

        if match:
            cuda_short = match.group(1)
            # Convert cu128 to 12.8
            if len(cuda_short) >= 2:
                major = cuda_short[:-1]
                minor = cuda_short[-1]
                return f"{major}.{minor}"

        return "n/a"
    except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError) as e:
        print(
            f"Warning: Could not read CUDA version from pyproject.toml: {e}",
            file=sys.stderr,
        )
        return "n/a"


def generate_badge(label: str, message: str, color: str) -> str:
    """Generate shields.io badge markdown.

    Args:
        label: Badge label (e.g., "FastAPI")
        message: Badge message/value (e.g., "0.128.0")
        color: Badge color (e.g., "blue", "green", "orange")

    Returns:
        Markdown badge string
    """
    # Encode special characters for URL
    label_encoded = label.replace(" ", "%20")
    message_encoded = message.replace(" ", "%20")

    return f"![{label}](https://img.shields.io/badge/{label_encoded}-{message_encoded}-{color}.svg)"


def generate_badges() -> str:
    """Generate all badges as markdown.

    Returns:
        Multi-line string with all badges
    """
    python_ver = get_python_version()
    fastapi_ver = get_fastapi_version()
    whisperx_ver = get_whisperx_version()
    cuda_ver = get_cuda_version()

    badges = [
        generate_badge("Python", python_ver, "blue"),
        generate_badge("CUDA", cuda_ver, "blue"),
        generate_badge("FastAPI", fastapi_ver, "green"),
        generate_badge("whisperx", whisperx_ver, "green"),
    ]

    return "\n".join(badges)


def update_readme_badges(dry_run: bool = False) -> bool:
    """Update README.md with current badge values.

    Args:
        dry_run: If True, show changes without modifying file

    Returns:
        True if changes were made (or would be made in dry-run), False otherwise
    """
    repo_root = Path(__file__).parent.parent
    readme_path = repo_root / "README.md"

    if not readme_path.exists():
        print(f"Error: README.md not found at {readme_path}", file=sys.stderr)
        return False

    try:
        content = readme_path.read_text()
    except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError) as e:
        print(f"Error: Could not read README.md: {e}", file=sys.stderr)
        return False

    # Check if markers exist
    start_marker = "<!-- BADGES:START -->"
    end_marker = "<!-- BADGES:END -->"

    if start_marker not in content or end_marker not in content:
        print(
            f"Error: Badge markers not found in README.md. "
            f"Please add {start_marker} and {end_marker}",
            file=sys.stderr,
        )
        return False

    # Generate new badges
    new_badges = generate_badges()

    # Replace content between markers
    pattern = rf"({re.escape(start_marker)})(.*?)({re.escape(end_marker)})"
    replacement = rf"\1\n{new_badges}\n\3"

    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # Check if content changed
    if new_content == content:
        print("No changes needed - badges are already up to date.")
        return False

    if dry_run:
        print("DRY RUN - Would make the following changes:")
        print("=" * 60)
        # Show the badge section
        match = re.search(pattern, new_content, flags=re.DOTALL)
        if match:
            print(match.group(0))
        print("=" * 60)
        return True

    # Write updated content
    try:
        readme_path.write_text(new_content)
        print(f"Successfully updated badges in {readme_path}")
        return True
    except (PermissionError, OSError, UnicodeEncodeError) as e:
        print(f"Error: Could not write to README.md: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Execute the script's main functionality.

    Returns:
        Exit code: 0 on success, 1 on error
    """
    parser = argparse.ArgumentParser(
        description="Update README badges with current versions from pyproject.toml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[0].strip(),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without modifying files",
    )

    args = parser.parse_args()

    try:
        update_readme_badges(dry_run=args.dry_run)
        # Exit with 0 whether updated or not (both are valid states)
        return 0
    except Exception as e:
        # Last resort error handler - log full traceback for debugging
        import traceback

        print(f"Unexpected error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
