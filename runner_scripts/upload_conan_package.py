import argparse
import os
import subprocess
import json


def upload_conan_package(args):
    packages_json = subprocess.run(["conan", "list", "-c", "-f", "json", args.package], capture_output=True, check=True).stdout
    packages = json.loads(packages_json)

    for package, details in packages["Local Cache"].items():
        package_recipes = []

        if "revisions" in details:
          package_recipes = [f"{package}#{revision}" for revision in details["revisions"]]
        else:
          package_recipes = [package]

        for package in package_recipes:
            remote = "cura-private-conan2" if "@internal" in package else "cura-conan2"

            print(f"Upload package {package} to {remote}")
            process_args = ["conan", "upload", package, "-r", remote, "-c"]

            if args.dry_run:
              process_args.append("--dry-run")
            if args.force:
              process_args.append("--force")

            subprocess.run(process_args, check=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Upload the given local package(s) to the proper Cura conan repository')
    parser.add_argument('package', type = str, help = 'Package name, fully specific or containing wildards')
    parser.add_argument('--dry-run', action='store_true', help = 'Do not upload the package but just show what would happen')
    parser.add_argument('--force', action='store_true', help = 'Force upload the package even if it already exists (e.g. to update the timestamp)')

    args = parser.parse_args()
    upload_conan_package(args)
