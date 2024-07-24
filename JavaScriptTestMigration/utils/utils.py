import os
import subprocess
import json
import fnmatch
import csv
import requests
import concurrent.futures
import shutil
import argparse

from ..constants import ABSOLUTE_PATH
from ..constants import GLOBAL_TIMEOUT
from ..constants import REPOS_WITH_RUNNING_TESTS_PATH
from ..constants import FILTERED_REPOS

def get_test_files(directory):
    print("Directory: ", directory)
    test_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            
            if fnmatch.fnmatch(file, '*.test.*') or fnmatch.fnmatch(file, '*.spec.*'):
                test_files.append(os.path.join(root, file))
    return test_files

def clone_repo(repo):
    url = f'https://github.com/{repo}.git'
    repo_name = repo.split('/')[-1]

    if os.path.exists(os.path.join(ABSOLUTE_PATH, repo_name)):
        print(f'{repo_name} already exists. Skipping clone.')
        return repo_name
    try:
        result = subprocess.run(['git', 'clone', url], cwd=ABSOLUTE_PATH, check=True, capture_output=True, text=True, timeout=GLOBAL_TIMEOUT)
        print(f'Successfully cloned {repo} into {repo_name}')
    except subprocess.CalledProcessError as e:
        print(f'Error cloning {repo}: {e.stderr}')
        return None
    return repo_name

def install_dependencies(repo_path, idx):
    full_repo_path = os.path.join(ABSOLUTE_PATH, repo_path)
    if os.path.exists(os.path.join(full_repo_path, 'yarn.lock')):
        # Use yarn to install dependencies
        try:
            subprocess.run(['yarn', 'install'], cwd=full_repo_path, capture_output=False, check=True)
            print(f'Successfully installed yarn dependencies in {repo_path}')
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f'Error installing yarn dependencies: {e.stderr}')
            print(f'\nError occured at index {idx}')
            return False
    elif os.path.exists(os.path.join(full_repo_path, 'package-lock.json')):
        # Use npm to install dependencies
        try:
            subprocess.run(['npm', 'install'], cwd=full_repo_path, check=True, capture_output=False, timeout=GLOBAL_TIMEOUT)
            print(f'Successfully installed npm dependencies in {repo_path}')
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f'Error installing npm dependencies: {e.stderr}')
            print(f'\nError occured at index {idx}')
            return False
    else:
        print(f'No yarn.lock or package-lock.json found in {repo_path}. Defaulting to npm')
        # Use npm to install dependencies
        try:
            subprocess.run(['npm', 'install'], cwd=full_repo_path, check=True, capture_output=False, timeout=GLOBAL_TIMEOUT)
            print(f'Successfully installed npm dependencies in {repo_path}')
            return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f'Error installing npm dependencies: {e.stderr}')
            print(f'\nError occured at index {idx}')
            return False

def run_npm_test(repo_path, idx):
    full_repo_path = os.path.join(ABSOLUTE_PATH, repo_path)
    try:
        with open(os.path.join(full_repo_path, 'package.json'), 'r') as f:
            package_json = json.load(f)
            test_command = package_json.get('scripts', {}).get('test')
            print(f"Test command: {test_command}")
            if test_command:
                test_package = test_command.split(" ")[0]
                print(f"Test package: {test_package}")

                if test_package:
                    subprocess.run([test_package, 'test'], cwd=full_repo_path, capture_output=False, check=True, timeout=GLOBAL_TIMEOUT) 
                    print(f'Successfully ran test in {repo_path}')
                    return True 
                else:
                    print(f'No test script found in package.json of {repo_path}')
                    return False
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f'Error running npm test: {e}')
        print(f'\nError occured at index {idx}')
        return False

def verify_tests_can_run(repo, idx, should_write_to_file = False):
    repo_name = clone_repo(repo)
    if repo_name:
        repo_path = os.path.join(ABSOLUTE_PATH, repo_name)
        if install_dependencies(repo_path, idx) and run_npm_test(repo_path, idx):
            try:
                if should_write_to_file:
                    with open(REPOS_WITH_RUNNING_TESTS_PATH, mode='a', encoding='utf-8') as file:
                        file.write(repo + ',\n')
                    print(f"{repo_name} written to file")
            except Exception as e:
                print(f"An error occurred: {e}")

def remove_directory(directory_path):
    try:
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
            print(f'Successfully removed directory: {directory_path}')
            return True
        else:
            print(f'Directory does not exist: {directory_path}')
            return False
    except Exception as e:
        print(f'Error removing directory: {e}')
        return False

def test_single_repo(repo_name):
    if repo_name:
        repo_path = os.path.join(ABSOLUTE_PATH, repo_name)
        if install_dependencies(repo_path, 0) and run_npm_test(repo_path, 0):
            print(f"Ran tests for {repo_name}")

def read_names_from_csv(file_path):
    repo_names = []
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            if 'name' not in csv_reader.fieldnames:
                print(f"'name' column not found in {file_path}")
                return

            names = [row['name'] for row in csv_reader]
            for name in names:
                repo_names.append(name)
        return repo_names
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

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
                        with open(FILTERED_REPOS, mode='a', encoding='utf-8') as file:
                            file.write(repo + ',\n')
                            print("Writing")
                        print(f"{package_name} written to file")
                    except Exception as e:
                        print(f"An error occurred: {e}")
                    return True
            return False
        except:
            print(f'Error with response for {repo}')
    else:
        return False

def run_parallel_package_checks(repos, package_names, branch='master'):
    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
        futures = {executor.submit(check_package_in_repo, repo, package_names, branch): repo for repo in repos}
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"Repo {repo} generated an exception: {exc}")

def run_parallel_verifications(repos):
    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
        futures = {executor.submit(verify_tests_can_run, repo, idx): repo for idx,repo in enumerate(repos)}
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            repo_name = repo.split('/')[-1]
            try:
                future.result()
                # remove_directory(repo_name)
            except Exception as exc:
                print(f"Repo {repo} generated an exception: {exc}")
                # remove_directory(repo_name)


