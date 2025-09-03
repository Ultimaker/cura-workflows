import argparse
import json


def make_runners_list(args):
    runners_list = []

    if args.platform_linux:
        runners_list.append({"runner": "ubuntu-latest", "conan_extra_args": ""})
    if args.platform_windows:
        runners_list.append({"runner": "windows-latest", "conan_extra_args": ""})
    if args.platform_mac:
        runners_list.append({"runner": "macos-13", "conan_extra_args": ""})
    if args.platform_wasm:
        runners_list.append({"runner": "ubuntu-latest", "conan_extra_args": "-pr:h cura_wasm.jinja"})

    runners_data = {"include": runners_list}
    print(json.dumps(runners_data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Build the runners and conan options list to be processed')
    parser.add_argument('--platform-linux',   action='store_true', help = 'Build on classic Linux runner')
    parser.add_argument('--platform-windows', action='store_true', help = 'Build on Windows runner')
    parser.add_argument('--platform-mac',     action='store_true', help = 'Build on MacOS runner(s)')
    parser.add_argument('--platform-wasm',    action='store_true', help = 'Build for WASM platform (Linux runner with options)')
    args = parser.parse_args()
    make_runners_list(args)
