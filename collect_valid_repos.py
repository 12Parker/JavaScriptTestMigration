import os
import subprocess
import json
import fnmatch
import csv
import requests
import concurrent.futures
# List of GitHub repositories in the format 'username/repo'

def read_names_from_csv(file_path):
    repoNames = []
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            if 'name' not in csv_reader.fieldnames:
                print(f"'name' column not found in {file_path}")
                return

            names = [row['name'] for row in csv_reader]
            for name in names:
                repoNames.append(name)
        return repoNames
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

valid_repos = set()
def check_package_in_repo(repo, package_names, branch='master'):
    url = f'https://raw.githubusercontent.com/{repo}/{branch}/package.json'
    response = requests.get(url)
    
    if response.status_code == 200:
        try:
            package_json = response.json()
            dependencies = package_json.get('dependencies', {})
            dev_dependencies = package_json.get('devDependencies', {})
            
            for package_name in package_names:
                if package_name in dependencies or package_name in dev_dependencies:
                    print(f"{package_name} found in dependencies.")
                    try:
                        with open('testTwo.txt', mode='a', encoding='utf-8') as file:
                            file.write(repo + ',\n')
                        print(f"{package_name} written to file")
                    except Exception as e:
                        print(f"An error occurred: {e}")
                    valid_repos.add(package_name)
                    return True
            return False
        except:
            print(f'Error with response for {repo}')
    else:
        # print(f"Failed to fetch package.json from {url}. Status code: {response.status_code}")
        return False

def run_parallel_checks(repos, package_names, branch='master'):
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check_package_in_repo, repo, package_names, branch): repo for repo in repos}
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"Repo {repo} generated an exception: {exc}")

def main():
    repos = read_names_from_csv('/home/jovyan/code/JavaScriptTesting/JavascriptRepos.csv')
    package_names = ['enzyme', '@testing-library/react', 'jest', 'mocha', 'chai', 'karma', 'karma-enzyme', 'karma-chai', 'karma-jasmine', 'chai-enzyme', 'jasmine-core']

    run_parallel_checks(repos, package_names)
    print("All checks completed.")
    print(f"Valid repos: {valid_repos}")
if __name__ == '__main__':
    main()