import os
import subprocess
import json
import fnmatch
import csv
import requests
import concurrent.futures
from repoNames import repos
# List of GitHub repositories in the format 'username/repo'

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

    if os.path.exists(repo_name):
        print(f'{repo_name} already exists. Skipping clone.')
        return repo_name
    try:
        result = subprocess.run(['git', 'clone', url], check=True, capture_output=True, text=True)
        print(f'Successfully cloned {repo} into {repo_name}')
    except subprocess.CalledProcessError as e:
        print(f'Error cloning {repo}: {e.stderr}')
        return None
    return repo_name

def check_dependencies(repo_path,file_path):
    path = os.path.join(repo_path,file_path)
    try:
        # Read the package.json file
        with open(path, 'r', encoding='utf-8') as file:
            package_json = json.load(file)
        
        # Check for dependencies and devDependencies
        dependencies = package_json.get('dependencies', {})
        dev_dependencies = package_json.get('devDependencies', {})
        
        # Check if Enzyme or @testing-library/react are present
        has_enzyme = 'enzyme' in dependencies or 'enzyme' in dev_dependencies
        has_testing_library = '@testing-library/react' in dependencies or '@testing-library/react' in dev_dependencies
        
        if has_enzyme or has_testing_library:
            print(f'Has DOM testing library')
        else:
            print(f'Doesn\'t have DOM testing library')
        return has_enzyme or has_testing_library
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f'Error reading or parsing package.json: {error}')
        return False

def install_dependencies(repo_path):
    if os.path.exists(os.path.join(repo_path, 'yarn.lock')):
        # Use yarn to install dependencies
        try:
            subprocess.run(['yarn', 'install'], cwd=repo_path, check=True)
            print(f'Successfully installed yarn dependencies in {repo_path}')
            return True
        except subprocess.CalledProcessError as e:
            print(f'Error installing yarn dependencies: {e.stderr}')
            return False
    elif os.path.exists(os.path.join(repo_path, 'package-lock.json')):
        # Use npm to install dependencies
        try:
            subprocess.run(['npm', 'install'], cwd=repo_path, check=True)
            print(f'Successfully installed npm dependencies in {repo_path}')
            return True
        except subprocess.CalledProcessError as e:
            print(f'Error installing npm dependencies: {e.stderr}')
            return False
    else:
        print(f'No yarn.lock or package-lock.json found in {repo_path}. Defaulting to npm')
        # Use npm to install dependencies
        try:
            subprocess.run(['npm', 'install'], cwd=repo_path, check=True)
            print(f'Successfully installed npm dependencies in {repo_path}')
            return True
        except subprocess.CalledProcessError as e:
            print(f'Error installing npm dependencies: {e.stderr}')
            return False

def run_npm_test(repo_path):
    try:
        with open(os.path.join(repo_path, 'package.json'), 'r') as f:
            package_json = json.load(f)
            test_command = package_json.get('scripts', {}).get('test')
            print(f"Test command: {test_command}")
            if test_command:
                test_package = test_command.split(" ")[0]
                print(f"Test package: {test_package}")

                if test_package:
                    subprocess.run([test_package, 'test'], cwd=repo_path, check=True) 
                    print(f'Successfully ran test in {repo_path}')
                    return True
                else:
                    print(f'No test script found in package.json of {repo_path}')
                    return False
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f'Error running npm test: {e}')
        return False

def main():
    success = []
    start = 31
    end = 60
    for idx, repo in enumerate(repos[start:end]):
        print(f"progress {idx}/{end - start}")
        repo_name = clone_repo(repo)
        if repo_name:
            env_name = repo_name.replace('/', '_')
            repo_path = os.path.join(os.getcwd(), repo_name)
            get_test_files(repo_name)
            if install_dependencies(repo_path) and run_npm_test(repo_path):
                success.append(repo_name)
    return success
if __name__ == '__main__':
    print(main())
