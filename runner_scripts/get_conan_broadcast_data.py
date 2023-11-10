import argparse
import os
from conan.tools.scm import Version
from conan.errors import ConanException
from git import Repo


def get_conan_broadcast_data(args):
    repo = Repo('.')
    user = args.user.lower()
    project_name = args.project_name
    event_name = args.event_name
    issue_number = args.ref.split('/')[2]
    is_tag = args.ref_type == "tag"
    is_release_branch = False
    ref_name = args.base_ref if event_name == "pull_request" else args.ref_name
    buildmetadata = "" if args.additional_buildmetadata == "" else f"{args.additional_buildmetadata}_"

    channel = "testing"
    if is_tag:
        branch_version = Version(ref_name)
        is_release_branch = True
        channel = "_"
        user = "_"
        actual_version = f"{branch_version}"
    else:
        try:
            branch_version = Version(repo.active_branch.name)
        except ConanException:
            branch_version = Version('0.0.0')
        if ref_name == f"{branch_version.major}.{branch_version.minor}":
            channel = 'stable'
            is_release_branch = True
        elif ref_name in ("main", "master"):
            channel = 'testing'
        else:
            channel = "_".join(repo.active_branch.name.replace("-", "_").split("_")[:2]).lower()

        if "pull_request" in event_name:
            channel = f"pr_{issue_number}"

        # %% Get the actual version
        latest_branch_version = Version("0.0.0")
        latest_branch_tag = None
        for tag in repo.active_branch.repo.tags:
            if str(tag).startswith("firmware") or str(tag).startswith("master"):
                continue  # Quick-fix for the versioning scheme name of the embedded team in fdm_materials(_private) repo
            try:
                version = Version(tag)
            except ConanException:
                continue
            if version > latest_branch_version and version < Version("6.0.0"):
                # FIXME: stupid old Cura tags 13.04 etc. keep popping up, als  the fdm_material tag for firmware are messing with this
                latest_branch_version = version
                latest_branch_tag = repo.tag(tag)

        if latest_branch_tag:
            # %% Get the actual version
            sha_commit = repo.commit().hexsha[:6]
            latest_branch_version_prerelease = latest_branch_version.pre
            if latest_branch_version.pre and not "." in str(latest_branch_version.pre):
                # The prerealese did not contain a version number, default it to 1
                latest_branch_version_prerelease = f"{latest_branch_version.pre}.1"
            if event_name == "pull_request":
                actual_version = f"{latest_branch_version.major}.{latest_branch_version.minor}.{latest_branch_version.patch}-{str(latest_branch_version_prerelease).lower()}+{buildmetadata}pr_{issue_number}_{sha_commit}"
                channel_metadata = f"{channel}_{sha_commit}"
            else:
                if channel in ("stable", "_", ""):
                    channel_metadata = f"{sha_commit}"
                else:
                    channel_metadata = f"{channel}_{sha_commit}"
            if is_release_branch:
                if (latest_branch_version.pre == "" or latest_branch_version.pre is None) and branch_version > latest_branch_version:
                    actual_version = f"{branch_version.major}.{branch_version.minor}.0-beta.1+{buildmetadata}{channel_metadata}"
                elif latest_branch_version.pre == "":
                    # An actual full release has been created, we are working on patch
                    bump_up_patch = int(str(latest_branch_version.patch)) + 1
                    actual_version = f"{latest_branch_version.major}.{latest_branch_version.minor}.{bump_up_patch}-beta.1+{buildmetadata}{channel_metadata}"
                elif latest_branch_version.pre is None:
                    actual_version = f"{latest_branch_version.major}.{latest_branch_version.minor}.{int(latest_branch_version.patch.value) + 1}-beta.1+{buildmetadata}{channel_metadata}"
                else:
                    # An beta release has been created we are working toward a next beta or full release
                    bump_up_release_tag = int(str(latest_branch_version.pre).split('.')[1]) + 1
                    actual_version = f"{latest_branch_version.major}.{latest_branch_version.minor}.{latest_branch_version.patch}-{str(latest_branch_version.pre).split('.')[0]}.{bump_up_release_tag}+{buildmetadata}{channel_metadata}"
            else:
                max_branches_version = Version("0.0.0")
                for branch in repo.references:
                    try:
                        if "remotes/origin" in branch.abspath:
                            b_version = Version(branch.name.split("/")[-1])
                            if b_version < Version("6.0.0") and b_version > max_branches_version:
                                max_branches_version = b_version
                    except:
                        pass
                if max_branches_version > latest_branch_version:
                    actual_version = f"{max_branches_version.major}.{int(str(max_branches_version.minor)) + 1}.0-alpha+{buildmetadata}{channel}_{sha_commit}"
                else:
                    actual_version = f"{latest_branch_version.major}.{int(str(latest_branch_version.minor)) + 1}.0-alpha+{buildmetadata}{channel_metadata}"

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
    parser.add_argument('--event_name', type = str, help = 'Github event name')
    parser.add_argument('--ref', type = str, help = 'Github reference')
    parser.add_argument('--ref_type', type = str, help = 'Github reference type')
    parser.add_argument('--base_ref', type = str, help = 'Github base reference')
    parser.add_argument('--ref_name', type = str, help = 'Github name reference')
    parser.add_argument('--additional_buildmetadata', type = str, help = 'Additional build metadata')

    args = parser.parse_args()
    get_conan_broadcast_data(args)
