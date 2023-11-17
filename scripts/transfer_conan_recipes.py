from bs4 import BeautifulSoup
import requests
import os
import subprocess
import argparse
import re

from conan.tools.scm import Version


def list_all_editable_packages():
    conan_search_command = "conan search --raw"
    process = subprocess.run(conan_search_command.split(), capture_output = True)
    packages = process.stdout.decode('utf-8').splitlines()
    return packages


def clear_local_cache():
    conan_remove_command = "conan remove \"*\" -f"
    os.system(conan_remove_command)


def get_remotes():
    conan_remotes_command = "conan remote list"
    process = subprocess.run(conan_remotes_command.split(), capture_output = True)
    remotes = [remote.split(":")[0] for remote in process.stdout.decode('utf-8').splitlines()]
    return remotes


def disable_all_remotes():
    remotes = get_remotes()
    for remote in remotes:
        conan_disable_command = f"conan remote disable {remote}"
        os.system(conan_disable_command)


def enable_remote(remote: str):
    conan_enable_command = f"conan remote enable {remote}"
    os.system(conan_enable_command)


def get_recipes_from_remote(query: str, remote: str):
    disable_all_remotes()
    enable_remote(remote)

    conan_search_command = f"conan search {query} --raw -r {remote}"
    process = subprocess.run(conan_search_command.split(), capture_output = True)
    packages = process.stdout.decode('utf-8').splitlines()
    return packages


def upload_package_filter(package):
    p = package.split("/")
    if p[0] in ["arcus", "cura", "cura_binary_data", "curaengine", "curaengine_grpc_definitions", "curaengine_plugin_gradual_flow", "curaengine_plugin_infill_generate", "curaengine_plugin_postprocess", "curaengine_simplify_plugin",
                "dulcificum", "fdm_materials", "nest2d", "pyarcus", "pynest2d", "pyprojecttoolchain", "pysavitar", "savitar", "scripta", "sipbuildtool", "spatial", "standardprojectsettings", "translationextractor", "umbase",
                "umspatial", "umspatialbackend", "uranium"]:
        return True
    return False


def download_packages(packages: list, remote: str):
    for package in packages:
        print(f"Downloading {package}")
        conan_download_command = f"conan download {package} -r {remote}"
        os.system(conan_download_command)


def upload_packages(packages: list, remote: str):
    for package in packages:
        print(f"Uploading {package}")
        conan_upload_command = f"conan upload {package} -r {remote}"
        os.system(conan_upload_command)


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description = "Transfer Conan Recipes")
    parser.add_argument("--source-remote", type = str, required = True, help = "source remote")
    parser.add_argument("--target-remote", type = str, required = True, help = "target remote")

    args = parser.parse_args()

    clear_local_cache()
    packages = []
    for package in get_recipes_from_remote("*", args.source_remote):
        if upload_package_filter(package):
            packages.append(package)

    download_packages(packages, args.source_remote)
    upload_packages(packages, args.target_remote)


if __name__ == "__main__":
    main()
