import os
import json
import requests
from urllib.parse import urljoin
import sys

def fetch_composer_json(repo_url, branch, platform="github"):
    """
    Fetches composer.json file from a repository.
    """
    if platform == "github":
        raw_url = repo_url.replace("github.com", "raw.githubusercontent.com") + f"/{branch}/composer.json"
    elif platform == "gitlab" or platform == "drupalcode":
        raw_url = repo_url + f"/-/raw/{branch}/composer.json"
    else:
        print(f"Unsupported platform for {repo_url}")
        sys.exit(1)  # Stop execution

    response = requests.get(raw_url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch composer.json from {repo_url} on branch {branch}")
        sys.exit(1)  # Stop execution

def get_default_branch(repo_url, platform="github"):
    """
    Fetches the default branch of a repository.
    """
    if platform == "github":
        api_url = repo_url.replace("github.com", "api.github.com/repos")
    elif platform == "gitlab":
        api_url = repo_url.replace("gitlab.com", "gitlab.com/api/v4/projects/")
        api_url = api_url.replace("/", "%2F", 1) + "/repository"
    elif platform == "drupalcode":
        api_url = repo_url.replace("git.drupalcode.org", "git.drupalcode.org/api/v4/projects/")
        api_url = api_url.replace("/", "%2F", 1) + "/repository"
    else:
        print(f"Unsupported platform for {repo_url}")
        sys.exit(1)  # Stop execution

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        if platform == "github":
            return data.get("default_branch", "main")
        elif platform == "gitlab" or platform == "drupalcode":
            return data.get("default_branch", "main")
    except requests.RequestException as e:
        print(f"Failed to fetch default branch for {repo_url}: {e}")
        sys.exit(1)  # Stop execution

def parse_dependencies(repo_name, repo_url, branch, all_dependencies, visited, platform="github"):
    """
    Parse the dependencies from a composer.json file and add them to the mermaid.js chart.
    """
    if repo_url in visited:
        return  # Avoid reprocessing the same repository
    visited.add(repo_url)

    composer_data = fetch_composer_json(repo_url, branch, platform)
    if not composer_data:
        sys.exit(1)  # Stop execution if composer.json is missing

    dependencies = composer_data.get("require", {})
    type_field = composer_data.get("type", "unknown")

    # Add the current repo to the dependencies list with its type
    all_dependencies[repo_name] = {
        "type": type_field,
        "dependencies": dependencies.keys()
    }

    # Recursively fetch dependencies
    for dependency in dependencies.keys():
        if "kanopi" in dependency:  # Assume only `kanopi` packages are on GitHub
            dep_repo_url = urljoin("https://github.com/", dependency.replace("/", "/"))
            dep_branch = get_default_branch(dep_repo_url, "github")  # Get the default branch for the dependent repo
            parse_dependencies(dependency, dep_repo_url, dep_branch, all_dependencies, visited, "github")
        elif "gitlab" in dependency:
            dep_repo_url = urljoin("https://gitlab.com/", dependency.replace("/", "/"))
            dep_branch = get_default_branch(dep_repo_url, "gitlab")  # Get the default branch for the dependent repo
            parse_dependencies(dependency, dep_repo_url, dep_branch, all_dependencies, visited, "gitlab")
        elif "git.drupalcode.org" in dependency:
            dep_repo_url = urljoin("https://git.drupalcode.org/", dependency.replace("/", "/"))
            dep_branch = get_default_branch(dep_repo_url, "drupalcode")  # Get the default branch for the dependent repo
            parse_dependencies(dependency, dep_repo_url, dep_branch, all_dependencies, visited, "drupalcode")

def generate_mermaid_chart(all_dependencies):
    """
    Generate a mermaid.js chart from the dependencies, structured to be more vertical than wide.
    """
    node_shapes = {
        "drupal-recipe": "(({}))",
        "drupal-module": "([{}])",
        "drupal-theme": "({})",
        "unknown": "[{}]"
    }

    lines = ["graph TB"]  # Use TB (Top to Bottom) for a vertical layout

    for repo, data in all_dependencies.items():
        shape = node_shapes.get(data["type"], "[{}]").format(repo)
        lines.append(f'    {repo}{shape}')
        for dependency in data["dependencies"]:
            lines.append(f'    {repo} --> {dependency}')

    return "\n".join(lines)

def generate_combined_markdown(repo_name, mermaid_chart, all_dependencies):
    """
    Generate a combined markdown file containing the Mermaid.js chart and the dependency list.
    """
    lines = [f"# {repo_name} Dependencies\n"]

    # Add Mermaid.js chart
    lines.append("## Dependency Graph\n")
    lines.append("```mermaid")
    lines.append(mermaid_chart)
    lines.append("```")

    # Add dependency list
    lines.append("## Dependency List\n")
    for repo, data in all_dependencies.items():
        lines.append(f"### {repo}\n")
        lines.append(f"- Type: {data['type']}\n")
        lines.append("#### Dependencies:\n")
        for dependency in data["dependencies"]:
            if dependency.startswith("drupal/"):
                dependency_name = dependency.split("/")[-1]
                link = f"https://www.drupal.org/project/{dependency_name}"
            elif dependency.startswith("bower-asset/") or dependency.startswith("npm-asset/"):
                dependency_name = dependency.split("/")[-1]
                link = f"https://asset-packagist.org/package/{dependency.replace('bower-asset/', 'bower-asset/').replace('npm-asset/', 'npm-asset/')}"
            else:
                link = f"https://packagist.org/packages/{dependency}"
            lines.append(f"- [{dependency}]({link})\n")

    # Add generated-by text at the bottom
    lines.append("---\n")
    lines.append("Generated using [thejimbirch/dependgen](https://github.com/thejimbirch/dependgen).\n")
    
    return "\n".join(lines).strip() + "\n"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <repository_url> [branch]")
        sys.exit(1)

    repo_url = sys.argv[1]
    branch = sys.argv[2] if len(sys.argv) > 2 else "main"
    repo_name = "/".join(repo_url.split("/")[-2:])
    all_dependencies = {}
    visited = set()

    # Parse dependencies recursively
    if "gitlab.com" in repo_url:
        platform = "gitlab"
    elif "git.drupalcode.org" in repo_url:
        platform = "drupalcode"
    else:
        platform = "github"

    parse_dependencies(repo_name, repo_url, branch, all_dependencies, visited, platform)

    # Generate mermaid.js chart
    mermaid_chart = generate_mermaid_chart(all_dependencies)

    # Generate combined markdown content
    combined_markdown = generate_combined_markdown(repo_name, mermaid_chart, all_dependencies)

    # Save the combined markdown file
    with open("DEPENDENCIES.md", "w") as file:
        file.write(combined_markdown)

    print("DEPENDENCIES.md file created!")
