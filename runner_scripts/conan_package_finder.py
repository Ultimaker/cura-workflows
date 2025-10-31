#!/usr/bin/env python3
"""
Conan Package Finder and Processor
"""

import json
import sys
import argparse
import subprocess
import re
from os import environ
from typing import Dict, List, Tuple, Optional, Any

try:
    from conan.tools.version import Version
except ImportError:
    # Fallback for older Conan versions
    try:
        from conans.model.version import Version
    except ImportError:
        print("Error: Conan is not installed or version comparison tools are not available", file=sys.stderr)
        sys.exit(1)


def search_conan_packages(pattern: str) -> str:
    """
    Execute conan list command to search for packages.
    
    Args:
        pattern: Conan package pattern (e.g., "*/*@ultimaker/cura_12824")
        
    Returns:
        Raw output from conan list command
    """
    try:
        result = subprocess.run(
            ['conan', 'list', pattern, '-r=*', '--format=json'],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            check=True   # Raise CalledProcessError on non-zero exit
        )
        
        # Return both stdout and stderr as conan sometimes mixes output
        return result.stdout + result.stderr
        
    except subprocess.TimeoutExpired:
        print("Error: Conan list command timed out", file=sys.stderr)
        return ""
    except subprocess.CalledProcessError as e:
        print(f"Error: Conan list command failed with return code {e.returncode}", file=sys.stderr)
        print(f"Output: {e.stdout}", file=sys.stderr)
        print(f"Error: {e.stderr}", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print("Error: 'conan' command not found. Make sure Conan is installed and in PATH", file=sys.stderr)
        return ""


def parse_conan_list_output(raw_output: str) -> List[str]:
    """
    Parse conan list JSON output and extract package references.
    
    Args:
        raw_output: Raw output from 'conan list' command
        
    Returns:
        List of package references, filtered to exclude packages with '+'
    """
    if not raw_output.strip():
        return []
        
    # Find JSON content in the output
    json_start = raw_output.find('{')
    if json_start == -1:
        return []
        
    json_end = raw_output.rfind('}')
    if json_end == -1:
        return []
    
    json_str = raw_output[json_start:json_end + 1]
    
    try:
        json_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Failed to parse conan list JSON output: {e}", file=sys.stderr)
        return []
    
    # Extract all packages from all remotes
    all_packages = []
    for remote_name, remote_data in json_data.items():
        if remote_data:
            packages = list(remote_data.keys())
            all_packages.extend(packages)
    
    # Filter out packages with '+' in the name
    filtered_packages = [pkg for pkg in all_packages if '+' not in pkg]
    
    return filtered_packages


def parse_package_reference(package_ref: str) -> Optional[Tuple[str, str]]:
    """
    Parse a Conan package reference to extract package name and version.
    
    Args:
        package_ref: Package reference in format "packagename/version@channel/reference"
        
    Returns:
        Tuple of (package_name, version) or None if parsing fails
    """
    try:
        # Split by '/' to get package name and rest
        parts = package_ref.split('/')
        if len(parts) < 2:
            return None
            
        package_name = parts[0]
        
        # Split by '@' to separate version from channel/reference
        version_part = parts[1].split('@')[0]
        
        return package_name, version_part
    except Exception:
        return None


def deduplicate_packages(packages: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Deduplicate packages by selecting the highest version for each repository.
    
    Args:
        packages: List of package references
        
    Returns:
        Tuple of (deduplicated_packages, version_selections)
        where version_selections maps package_name to list of all versions found
    """
    package_map: Dict[str, List[Tuple[str, str]]] = {}  # package_name -> [(full_ref, version), ...]
    version_selections: Dict[str, List[str]] = {}
    
    # Group packages by name
    for pkg_ref in packages:
        parsed = parse_package_reference(pkg_ref)
        if not parsed:
            continue
            
        package_name, version = parsed
        
        if package_name not in package_map:
            package_map[package_name] = []
            version_selections[package_name] = []
            
        package_map[package_name].append((pkg_ref, version))
        version_selections[package_name].append(version)
    
    # Select highest version for each package
    deduplicated = []
    
    for package_name, refs_and_versions in package_map.items():
        if len(refs_and_versions) == 1:
            # Only one version, keep it
            deduplicated.append(refs_and_versions[0][0])
        else:
            # Multiple versions, select the highest
            highest_ref = None
            highest_version = None
            
            for pkg_ref, version in refs_and_versions:
                try:
                    current_version = Version(version)
                    
                    if highest_version is None or current_version > highest_version:
                        highest_version = current_version
                        highest_ref = pkg_ref
                        
                except Exception as e:
                    print(f"Warning: Could not parse version '{version}' for package '{package_name}': {e}", file=sys.stderr)
                    # If version parsing fails, fall back to string comparison
                    if highest_version is None or version > str(highest_version):
                        highest_version = version
                        highest_ref = pkg_ref
            
            if highest_ref:
                deduplicated.append(highest_ref)
                print(f"Selected highest version for {package_name}: {highest_version} from {len(refs_and_versions)} options", file=sys.stderr)
    
    return deduplicated, version_selections


def categorize_packages(packages: List[str]) -> Tuple[str, List[str]]:
    """
    Separate cura packages from override packages.
    
    Args:
        packages: List of package references
        
    Returns:
        Tuple of (cura_package, override_packages)
    """
    cura_package = ""
    override_packages = []
    
    for pkg in packages:
        if pkg.startswith('cura/'):
            cura_package = pkg
        else:
            override_packages.append(pkg)
    
    return cura_package, override_packages


def main():
    parser = argparse.ArgumentParser(description="Search and process Conan packages")
    parser.add_argument("--search-pattern", help="Conan package search pattern (e.g., '*/*@ultimaker/cura_12824')")
    parser.add_argument("--jira-ticket", help="Jira ticket number for summary generation")
    parser.add_argument("--raw-output", help="Raw output from conan list command (alternative to --search-pattern)")
    parser.add_argument("--packages", help="JSON array of package references (alternative to above)")
    parser.add_argument("--output-format", choices=["json", "github-actions", "github-summary"], default="json",
                       help="Output format")
    
    args = parser.parse_args()
    
    if args.search_pattern:
        # Execute conan search and process results
        print(f"Searching for packages with pattern: {args.search_pattern}", file=sys.stderr)
        raw_output = search_conan_packages(args.search_pattern)
        discovered_packages = parse_conan_list_output(raw_output)
    elif args.raw_output:
        # Process raw conan list output
        discovered_packages = parse_conan_list_output(args.raw_output)
    elif args.packages:
        # Process pre-filtered package list
        try:
            discovered_packages = json.loads(args.packages)
            if not isinstance(discovered_packages, list):
                raise ValueError("Packages must be a JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing packages JSON: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: Must provide one of --search-pattern, --raw-output, or --packages", file=sys.stderr)
        sys.exit(1)
    
    # Deduplicate packages
    deduplicated, version_info = deduplicate_packages(discovered_packages)
    
    # Categorize packages
    cura_package, override_packages = categorize_packages(deduplicated)
    
    if args.output_format == "json":
        result = {
            "discovered_packages": discovered_packages,
            "deduplicated_packages": deduplicated,
            "cura_package": cura_package,
            "override_packages": override_packages,
            "version_selections": version_info,
            "original_count": len(discovered_packages),
            "deduplicated_count": len(deduplicated)
        }
        print(json.dumps(result, indent=2))
        
    elif args.output_format == "github-actions":
        # Output in GitHub Actions format for direct consumption
        print(f"discovered_packages={' '.join(deduplicated)}")
        print(f"cura_package={cura_package}")
        print(f"package_overrides={' '.join(override_packages)}")
        print(f"original_count={len(discovered_packages)}")
        print(f"deduplicated_count={len(deduplicated)}")
        
    elif args.output_format == "github-summary":
        # Generate complete GitHub summary and write directly to GITHUB_STEP_SUMMARY
        jira_ticket = args.jira_ticket or "Unknown"
        pattern = args.search_pattern or "N/A"
        
        summary_lines = [
            f"## Conan Packages Found for Jira Ticket: {jira_ticket}\n",
            "\n",
            f"The workflow searched for Conan packages matching the pattern `{pattern}` across all configured remotes.\n",
            "\n",
            "## Discovered Packages:\n",
            "\n"
        ]
        
        if len(deduplicated) == 0:
            summary_lines.append("*No packages found matching the specified tag.*\n")
        else:
            # Add deduplicated packages list
            for pkg in deduplicated:
                summary_lines.append(f"- {pkg}\n")
            
            # Add version selection info if deduplication occurred
            if len(discovered_packages) > len(deduplicated):
                summary_lines.extend([
                    "\n",
                    "### Package Version Selection:\n",
                    "\n",
                    f"Found {len(discovered_packages)} total packages, selected {len(deduplicated)} packages after choosing the highest semantic version for each repository.\n",
                    "\n",
                    "#### All Discovered Packages (before deduplication):\n",
                    "\n"
                ])
                for pkg in discovered_packages:
                    summary_lines.append(f"- {pkg}\n")
        
        summary_lines.extend(["\n", "---\n"])
        
        # Write directly to GitHub Step Summary if available
        if "GITHUB_STEP_SUMMARY" in environ:
            with open(environ["GITHUB_STEP_SUMMARY"], "a") as f:
                f.writelines(summary_lines)
        
        # Output workflow data as JSON for JavaScript consumption
        outputs = {
            "discovered_packages": " ".join(deduplicated),
            "cura_package": cura_package,
            "package_overrides": " ".join(override_packages)
        }
        
        print(json.dumps(outputs))


if __name__ == "__main__":
    main()