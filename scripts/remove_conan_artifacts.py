from bs4 import BeautifulSoup
import requests
import os
import subprocess
import argparse

def remove_conan_binaries(query: str, remote: str):
    # Search for packages given the query
    conan_search_command = f"conan search {query} --raw -r {remote}"
    process = subprocess.run(conan_search_command.split(), capture_output=True)
    packages = process.stdout.decode('utf-8').splitlines()
    for package in packages:
        conan_search_command = f"conan search {package} --table packages.html -r {remote}"
        os.system(conan_search_command)
        try:
            # Read the generated HTML file
            with open("packages.html", "r") as f:
                contents = f.read()
            # Create a BeautifulSoup object and specify the parser
            soup = BeautifulSoup(contents, 'html.parser')
            # Find the table that contains the package ids
            table = soup.find_all('table')[-1]
            # Iterate over rows in the table skip the header row
            rows = table.find_all('tr')[1:]
            package_ids = [row.find_all('td')[1].text for row in rows if len(row.find_all('td')) > 1]
        finally:
            os.remove("packages.html")
        # Remove each binary package (but not the recipe)
        for package_id in package_ids:
            print(f"Removing binaries {package_id} for {package}")
            remove_command = f"conan remove -p {package_id} -f -r {remote} {package}"
            # print(remove_command)
            os.system(remove_command)

# Parse arguments
parser = argparse.ArgumentParser(description="Remove Conan Binaries")
parser.add_argument("--query", type=str, required=True, help="Query for packages to remove")
parser.add_argument("--remote", type=str, required=True, help="Remote to remove from")

args = parser.parse_args()
remove_conan_binaries(args.query, args.remote)