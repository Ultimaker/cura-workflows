import argparse
import os
import yaml
import sys
import re

def get_conan_broadcast_data(args):
    if args.version is not None and args.version != "":
        version = args.version
    else:
        if os.path.exists("conandata.yml"):
            with open("conandata.yml", "r") as f:
                conan_data = yaml.safe_load(f)
                version = conan_data["version"]
        else:
            raise ValueError("Version should be specified either via argument or conandata.yml")

    version_base = ""
    version_sha = ""
    if "+" in version:
        version_base = version.split('+')[0]
        version_sha = version.split("+")[1]
    elif args.sha:
        version_base = version
        version_sha = args.sha[:6]

    version_full = f"{version_base}+{version_sha}"

    user = "internal" if args.internal else "ultimaker"

    ref_name = args.head_ref if args.event_name == "pull_request" else args.ref_name
    is_release_branch = re.fullmatch(r"\d+.\d+", ref_name)
    if args.release or is_release_branch:
        user = ""
        channel = ""
    elif ref_name in ("main", "master"):
        channel = 'testing'
    else:
        channel = "_".join(ref_name.replace("-", "_").split("_")[:2]).lower()

    user_channel = ""
    if user != "":
        user_channel = f"@{user}"
        if channel != "":
            user_channel += f"/{channel}"

    data = {
        "package_name": args.package_name,
        "package_version_full": f"{args.package_name}/{version_full}{user_channel}",
        "package_version_latest": f"{args.package_name}/{version_base}{user_channel}",
        "version_full": version_full,
        "version_base": version_base,
        "channel": channel,
        "user": user,
    }

    version_output = sys.stdout
    if args.version_output is not None:
        version_output = open(args.version_output, "a")
    for key, value in data.items():
        version_output.write(f"{key}={value}\n")

    summary_output = sys.stdout
    if args.summary_output is not None:
        summary_output = open(args.summary_output, "a")
    for key, value in data.items():
        if value =="" or (key.endswith("_full") and args.release):
            # we dont't use full version for release package, so don't display them
            continue

        if key == "package_name":
            summary_output.write(f"# {value}\n")
        else:
            summary_output.write(f"**{key}**\n")
            summary_output.write(f"```\n{value}\n```\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Get Conan broadcast data')
    parser.add_argument('--package_name',   type = str, help = 'Name of the package', required=True)
    parser.add_argument('--release',        action='store_true', help = 'Is a release')
    parser.add_argument('--sha',            type = str, help = 'Commit SHA')
    parser.add_argument('--event_name',     type = str, help = 'Github event name')
    parser.add_argument('--ref_name',       type = str, help = 'Github name reference')
    parser.add_argument('--head_ref',       type = str, help = 'Github source branch name')
    parser.add_argument('--version',        type = str, help = 'User override version')
    parser.add_argument('--internal',       action='store_true', help = 'This is an internal version')
    parser.add_argument('--version-output', type = str, help = 'Path of output file to write versions, otherwise print to stdout')
    parser.add_argument('--summary-output', type = str, help = 'Path of output file to write summary, otherwise print to stdout')

    args = parser.parse_args()
    get_conan_broadcast_data(args)
