import argparse
import os
import yaml

def get_conan_broadcast_data(args):
    with open("conandata.yml", "r") as f:
        conan_data = yaml.safe_load(f)
    version = conan_data["version"] if args.version == '' else args.version
    project_name = args.project_name

    if args.release == "true":
        actual_version = version
        user = "_"
        channel = "_"
        is_release_branch = True
    else:
        build_metadata = ""
        if "+" in version:
            build_metadata += f"+{version.split('+')[1]}"
            version = version.split("+")[0]
        elif args.sha:
            build_metadata += f"+{args.sha[:6]}"

        actual_version = f"{version}{build_metadata}"
        user = args.user.lower()
        is_release_branch = False
        if args.channel:
            channel = args.channel.lower()
        else:
            ref_name = args.base_ref if args.event_name == "pull_request" else args.ref_name
            if "beta" in version and args.event_name != "pull_request" and ref_name == '.'.join(version.split('.')[:2]):
                channel = "stable"
                is_release_branch = True
            else:
                if ref_name in ("main", "master"):
                    channel = 'testing'
                else:
                    channel = "_".join(ref_name.replace("-", "_").split("_")[:2]).lower()

    # %% Set the environment output
    output_env = os.environ["GITHUB_OUTPUT"]
    content = ""
    if os.path.exists(output_env):
        with open(output_env, "r") as f:
            content = f.read()

    with open(output_env, "w") as f:
        f.write(content)
        f.writelines(f"name={project_name}\n")
        f.writelines(f"version={actual_version}\n")
        f.writelines(f"channel={channel}\n")
        f.writelines(f"recipe_id_full={project_name}/{actual_version}@{user}/{channel}\n")
        f.writelines(f"recipe_id_latest={project_name}/latest@{user}/{channel}\n")
        f.writelines(f"semver_full={actual_version}\n")
        f.writelines(f"is_release_branch={str(is_release_branch).lower()}\n")

    summary_env = os.environ["GITHUB_STEP_SUMMARY"]
    with open(summary_env, "w") as f:
        f.writelines(f"# {project_name}\n")
        f.writelines(f"name={project_name}\n")
        f.writelines(f"version={actual_version}\n")
        f.writelines(f"channel={channel}\n")
        f.writelines(f"recipe_id_full={project_name}/{actual_version}@{user}/{channel}\n")
        f.writelines(f"recipe_id_latest={project_name}/latest@{user}/{channel}\n")
        f.writelines(f"semver_full={actual_version}\n")
        f.writelines(f"is_release_branch={str(is_release_branch).lower()}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Get Conan broadcast data')
    parser.add_argument('--user', type = str, help = 'User input')
    parser.add_argument('--project_name', type = str, help = 'Name of the project')
    parser.add_argument('--sha', type = str, help = 'Commit SHA')
    parser.add_argument('--event_name', type = str, help = 'Github event name')
    parser.add_argument('--base_ref', type = str, help = 'Github base reference')
    parser.add_argument('--ref_name', type = str, help = 'Github name reference')
    parser.add_argument('--release', type = str, help = 'Is a release')
    parser.add_argument('--version', type = str, help = 'User override version')

    args = parser.parse_args()
    get_conan_broadcast_data(args)
