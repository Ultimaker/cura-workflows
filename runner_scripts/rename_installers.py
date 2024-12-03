import os
import argparse

def rename_installers(args):
    first_file = True

    for file in os.listdir("."):
        # Find the commit tag, and place the tags instead
        index_plus = file.index("+")
        file_start = file[:index_plus]
        file_end = file[index_plus:]
        file_end = file_end[file_end.index("-")+1:]

        new_file_name = f"{file_start}-{args.tag}-{file_end}"
        os.rename(file, new_file_name)

        if first_file:
            first_file = False

            short_version = file_start.split("-")[2]
            short_version = ".".join(short_version.split(".")[:2])

            print(f"cura_version={file_start}")
            print(f"short_version={file_start}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Rename the installers')
    parser.add_argument('--tag', type = str, help = 'Tag to be added in the name, e.g. "nightly" or "weekly-Internal"', required=True)
    args = parser.parse_args()
    rename_installers(args)
