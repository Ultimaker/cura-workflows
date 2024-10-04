import argparse
import os
import re
import yaml

from pathlib import Path

def upload_changed_recipes(args):
    files = args.Files
    configs = dict(zip([ str(f).split("/")[1] for f in files ], [ Path(*str(f).split("/")[:2]).joinpath("config.yml") for f in files ]))

    packages = []
    channel = "stable" if "main" in args.branch else re.match(r"(CURA-\d*|NP-\d*|PP-\d*)", args.branch)[0].lower().replace("-", "_")

    for name, config in configs.items():
        if not config.exists():
            continue

        versions = {}
        with open(config, "r") as f:
            versions = yaml.safe_load(f)["versions"]

        for version, data in versions.items():
            conanfile = config.parent.joinpath(data["folder"], "conanfile.py")
            package = f"{name}/{version}@{args.user}/{channel}"
            create_cmd = f"conan create {conanfile} {package}"
            os.system(create_cmd)
            upload_cmd = f"conan upload {package} -r {args.remote} -c"
            os.system(upload_cmd)
            packages.append(package)

    summary_env = os.environ["GITHUB_STEP_SUMMARY"]
    with open(summary_env, "w") as f:
        f.writelines(f"# Created and Uploaded to remote {args.remote}\n")
        for package in packages:
            f.writelines(f"{package}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Upload all the changed recipes in the recipe folder')
    parser.add_argument('--user', type = str, help = 'User')
    parser.add_argument('--branch', type = str, help = 'Branch')
    parser.add_argument('--remote', type = str, help = 'Remote')
    parser.add_argument("Files", metavar="F", type=str, nargs="+", help="Files or directories to format")

    args = parser.parse_args()
    upload_changed_recipes(args)
