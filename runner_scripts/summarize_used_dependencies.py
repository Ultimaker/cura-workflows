import argparse
import os

from cura.CuraVersion import ConanInstalls, PythonInstalls


def display_used_dependencies(args):
    print(f"# {args.installer_filename}")
    print("## Conan packages:")
    for dep_name, dep_info in ConanInstalls.items():
        print(f"`{dep_name} {dep_info['version']} {dep_info['revision']}`")

    print("## Python modules:")
    for dep_name, dep_info in PythonInstalls.items():
        print(f"`{dep_name} {dep_info['version']}`")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Set the installer filename')
    parser.add_argument('--installer_filename', type = str, help = 'The raw name of the generated installer file')
    args = parser.parse_args()
    display_used_dependencies(args)
