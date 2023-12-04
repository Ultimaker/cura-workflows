import argparse
import os

from cura.CuraVersion import ConanInstalls, PythonInstalls


def set_gh_output_used_dependencies(args):
    summary_env = os.environ["GITHUB_STEP_SUMMARY"]
    content = ""
    if os.path.exists(summary_env):
        with open(summary_env, "r") as f:
            content = f.read()

    with open(summary_env, "w") as f:
        f.write(content)
        f.writelines("# ${{ steps.filename.outputs.INSTALLER_FILENAME }}\n")
        f.writelines("## Conan packages:\n")
        for dep_name, dep_info in ConanInstalls.items():
            f.writelines(f"`{dep_name} {dep_info['version']} {dep_info['revision']}`\n")

        f.writelines("## Python modules:\n")
        for dep_name, dep_info in PythonInstalls.items():
            f.writelines(f"`{dep_name} {dep_info['version']}`\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Set the installer filename')
    parser.add_argument('--installer_filename', type = str, help = 'INSTALLER_FILENAME')
    args = parser.parse_args()
    set_gh_output_used_dependencies(args)
