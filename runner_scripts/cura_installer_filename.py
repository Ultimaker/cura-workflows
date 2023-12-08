import argparse
import os


def set_installer_filename(args):
    os_name = {"Linux": "linux", "Windows": "win64", "macOS": "macos"}.get(args.os)
    enterprise = "-Enterprise" if args.enterprise == "true" else ""
    internal = "-Internal" if args.internal == "true" else ""
    
    installer_filename_args = ["UltiMaker-Cura", os.getenv('CURA_VERSION_FULL')]
    if args.enterprise == "true":
        installer_filename_args.append("Enterprise")
    if args.internal == "true":
        installer_filename_args.append("Internal")
    installer_filename_args.append(os_name)
    installer_filename_args.append(args.architecture)
    installer_filename = "-".join(installer_filename_args)
    output_env = os.environ["GITHUB_OUTPUT"]
    content = ""
    if os.path.exists(output_env):
        with open(output_env, "r") as f:
            content = f.read()

    with open(output_env, "w") as f:
        f.write(content)
        f.writelines(f"INSTALLER_FILENAME={installer_filename}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Set the installer filename')
    parser.add_argument('--os', type = str, help = 'OS')
    parser.add_argument('--architecture', type = str, help = 'Architecture')
    parser.add_argument('--enterprise', type = str, help = 'Enterprise')
    parser.add_argument('--internal', type = str, help = 'Internal')
    args = parser.parse_args()
    set_installer_filename(args)
