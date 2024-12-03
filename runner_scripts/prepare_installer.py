import argparse
import os
import sys

from cura import CuraVersion


def set_installer_filename(args):
    os_name = {"Linux": "linux", "Windows": "win64", "macOS": "macos"}.get(args.os)
    enterprise = "-Enterprise" if args.enterprise == "true" else ""
    internal = "-Internal" if args.internal == "true" else ""
    
    installer_filename_args = ["UltiMaker-Cura", CuraVersion.CuraVersionFull]
    if args.enterprise:
        installer_filename_args.append("Enterprise")
    if args.internal:
        installer_filename_args.append("Internal")
    installer_filename_args.append(os_name)
    installer_filename_args.append(args.architecture)
    installer_filename = "-".join(installer_filename_args)

    variables_output = sys.stdout
    if args.variables_output is not None:
        variables_output = open(args.variables_output, "a")
    variables_output.write(f"INSTALLER_FILENAME={installer_filename}\n")
    variables_output.write(f"CURA_VERSION_FULL={CuraVersion.CuraVersionFull}\n")
    variables_output.write(f"CURA_APP_NAME={CuraVersion.CuraAppDisplayName}\n")

    summary_output = sys.stdout
    if args.summary_output is not None:
        summary_output = open(args.summary_output, "a")
    summary_output.write(f"# {installer_filename}\n")
    summary_output.write("## Conan packages:\n")
    for dep_name, dep_info in CuraVersion.ConanInstalls.items():
        summary_output.write(f"`{dep_name} {dep_info['version']} {dep_info['revision']}`\n")

    summary_output.write("## Python modules:\n")
    for dep_name, dep_info in CuraVersion.PythonInstalls.items():
        summary_output.write(f"`{dep_name} {dep_info['version']}`\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Set the installer filename')
    parser.add_argument('--os',               type = str, help = 'OS')
    parser.add_argument('--architecture',     type = str, help = 'Architecture')
    parser.add_argument('--enterprise',       action='store_true', help = 'Enterprise')
    parser.add_argument('--internal',         action='store_true', help = 'Internal')
    parser.add_argument('--summary-output',   type = str, help = 'Output file for the summary. If not specified, stdout will be used.')
    parser.add_argument('--variables-output', type = str, help = 'Output file for the variables. If not specified, stdout will be used.')
    args = parser.parse_args()
    set_installer_filename(args)
