import argparse
import os
import subprocess
import re
import yaml
import json

from pathlib import Path

def upload_changed_recipes(args):
    configs = {}

    for file in args.Files:
        file_path = Path(file)
        config_path = file_path.parent.parent.joinpath("config.yml")
        package_name = file_path.parent.parent.name
        configs[package_name] = config_path

    packages = []
    is_release = "main" in args.branch
    channel = "" if is_release else re.match(r"(CURA|NP|PP)-\d*", args.branch)[0].lower().replace("-", "_")
    user = "" if is_release else "ultimaker"

    for name, config_file in configs.items():
        if not config_file.exists():
            continue

        actual_user = user
        actual_channel = channel

        versions = {}
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
            versions = config["versions"]
            if "user" in config:
                actual_user = config["user"]
            if "channel" in config:
                actual_channel = config["channel"]

        for version, data in versions.items():
            conanfile = config_file.parent.joinpath(data["folder"], "conanfile.py")

            conan_export = ["conan", "export", conanfile, "--name", name, "--version", version, "-f", "json"]

            if actual_user != "":
                conan_export += ["--user", actual_user]
            if actual_channel != "":
                conan_export += ["--channel", actual_channel]

            export_output = subprocess.run(conan_export, capture_output=True, check = True).stdout
            package_reference = json.loads(export_output)["reference"]
            subprocess.run(["conan", "upload", package_reference, "-r", args.remote, "-c"], check = True)
            packages.append(package_reference.split("#")[0])

    summary_env = os.environ["GITHUB_STEP_SUMMARY"]
    with open(summary_env, "w") as f:
        f.writelines(f"# Created and Uploaded to remote {args.remote}\n")
        for package in packages:
            f.writelines(f"{package}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Upload all the changed recipes in the recipe folder')
    parser.add_argument('--branch', type = str, help = 'Development branch')
    parser.add_argument('--remote', type = str, help = 'Name of the remote conan repository')
    parser.add_argument("Files", metavar="FILES", type=str, nargs="+", help="Files or directories to format")

    args = parser.parse_args()
    upload_changed_recipes(args)
