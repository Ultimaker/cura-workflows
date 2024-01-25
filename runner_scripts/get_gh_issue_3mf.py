import argparse
import asyncio
import json
import zipfile
import re
import shutil
import os
from pathlib import Path

import aiohttp
from aiogithubapi import GitHubAPI

token = os.getenv("GITHUB_TOKEN")


async def get_issues(github, repo_name, page=1):
    url = f"/repos/{repo_name}/issues?page={page}"
    response = await github.generic(url)
    if response.status != 200:
        raise Exception(f"Failed to get issues: {response.status}")
    else:
        print(f"Got issues page {page}")
    return response.is_last_page, response.pages.get("next"), response.data


async def process_issue(issue, out_path: Path):
    issue_number = issue['number']
    if out_path.joinpath(f"GH-{issue_number}-0.3mf").exists():
        print(f"Skipping issue #{issue_number}")
        return

    print(f"Processing issue #{issue_number}")
    pattern = r"(https?://[^\s]+.zip)"

    zip_urls = re.findall(pattern, issue['body'])
    if not zip_urls:
        return

    for zip_url in zip_urls:
        filename = out_path.joinpath(f"gh-{issue_number}.zip")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(zip_url) as resp:
                    with open(filename, "wb") as f:
                        f.write(await resp.read())
            except aiohttp.client_exceptions.ServerDisconnectedError:
                print(f"Server disconnected: {zip_url} while processing issue #{issue_number}")
                return

        try:
            with zipfile.ZipFile(filename, "r") as zip_ref:
                zip_ref.extractall(out_path.joinpath("extracted"))
        except zipfile.BadZipFile:
            print(f"Bad zip file: {zip_url} while processing issue #{issue_number}")
            return
        except NotImplementedError:
            print(f"Unsupported compression method: {zip_url} while processing issue #{issue_number}")
            return

        idx = 0
        for file in out_path.joinpath("extracted").rglob("**/*.3mf"):
            if "__MACOSX" in file.parts:
                continue
            new_filename = out_path.joinpath(f"GH-{issue_number}-{idx}.3mf")
            file.rename(new_filename)
            idx += 1
        shutil.rmtree(out_path.joinpath("extracted"), ignore_errors=True)
        os.remove(filename)


async def main():
    parser = argparse.ArgumentParser(description="Process GitHub issues.")
    parser.add_argument("--repository", type=str, default="Ultimaker/Cura", help="The repository to fetch issues from")
    parser.add_argument("--label", type=str, default="Slicing Error :collision:", help="The label to filter issues by")
    parser.add_argument("--exclude", type=str, default="Sentry :european_castle:",
                        help="The label to exclude issues by")
    parser.add_argument("--out", type=Path, default="./out", help="The directory to save the 3mf files to")

    args = parser.parse_args()

    all_issues = []
    all_issues_numbers = set()
    issue_cache = args.out.joinpath("all_issues.json")
    if issue_cache.exists():
        print("Loading old issues from cache")
        all_issues = json.load(open(issue_cache, "r"))
        all_issues_numbers = set([issue['number'] for issue in all_issues])

    print("Fetching new issues")
    github = GitHubAPI(token=token)

    last_page = False
    page = 1
    new_issues = []
    while not last_page:
        last_page, page, issues = await get_issues(github, args.repository, page)
        _issues = [issue for issue in issues if issue['number'] not in all_issues_numbers]
        if len(_issues) < len(issues):
            last_page = True
        new_issues += _issues

    all_issues += new_issues
    json.dump(all_issues, open(issue_cache, "w"), indent=4)

    for issue in new_issues:
        if any([label["name"] == args.label and label["name"] != args.exclude for label in issue['labels']]):
            await process_issue(issue, args.out)


if __name__ == "__main__":
    asyncio.run(main())
