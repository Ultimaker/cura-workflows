import argparse
import json


def make_runners_list(args):
    runners_list = []

    if args.platform_linux:
        runners_list.append({"platform": "linux", "runner": "ubuntu-latest", "conan_extra_args": ""})
    if args.platform_windows:
        runners_list.append({"platform": "windows", "runner": "windows-latest", "conan_extra_args": ""})
    if args.platform_mac:
        runners_list.append({"platform": "macos", "runner": "macos-13", "conan_extra_args": ""})
    if args.platform_windows_arm64:
        runners_list.append({
            "platform": "windows-arm64",
            "runner": "windows-11-arm",
            "conan_extra_args": (
                "-s:h arch=armv8 -pr:b default -s:b arch=x86_64 "
                "-s:b compiler.cppstd=17 -s:b \"curator/*:compiler.cppstd=20\" "
                "-c:b tools.build:skip_test=True"
            ),
        })
    if args.platform_wasm:
        runners_list.append({"platform": "wasm", "runner": "ubuntu-latest", "conan_extra_args": "-pr:h cura_wasm.jinja"})

    runners_data = {"include": runners_list}
    print(json.dumps(runners_data))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Build the runners and conan options list to be processed')
    parser.add_argument('--platform-linux',   action='store_true', help = 'Build on classic Linux runner')
    parser.add_argument('--platform-windows', action='store_true', help = 'Build on Windows runner')
    parser.add_argument('--platform-mac',     action='store_true', help = 'Build on MacOS runner(s)')
    parser.add_argument('--platform-wasm',    action='store_true', help = 'Build for WASM platform (Linux runner with options)')
    parser.add_argument('--platform-windows-arm64', action='store_true', help='Build on Windows ARM64 runner')
    args = parser.parse_args()
    make_runners_list(args)
