import argparse
import os

from cura.CuraVersion import CuraVersionFull


def set_installer_filename(args):
    os_name = {"Linux": "linux", "Windows": "win64", "macOS": "macos"}.get(args.os)
    enterprise = "-Enterprise" if args.enterprise == "true" else ""
    internal = "-Internal" if args.internal == "true" else ""
    
    installer_filename_args = ["UltiMaker-Cura", CuraVersionFull]
    if args.enterprise:
        installer_filename_args.append("Enterprise")
    if args.internal:
        installer_filename_args.append("Internal")
    installer_filename_args.append(os_name)
    installer_filename_args.append(args.architecture)
    installer_filename = "-".join(installer_filename_args)

    print(installer_filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Set the installer filename')
    parser.add_argument('--os',           type = str, help = 'OS')
    parser.add_argument('--architecture', type = str, help = 'Architecture')
    parser.add_argument('--enterprise',   action='store_true', help = 'Enterprise')
    parser.add_argument('--internal',     action='store_true', help = 'Internal')
    args = parser.parse_args()
    set_installer_filename(args)
