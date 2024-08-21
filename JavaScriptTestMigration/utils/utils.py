import os
import subprocess
import json
import fnmatch
import csv
import requests
import concurrent.futures
import shutil
import argparse
import re

from ..constants import ABSOLUTE_PATH
from ..constants import GLOBAL_TIMEOUT
from ..constants import ENZYME_REPOS_WITH_RUNNING_TESTS_PATH
from ..constants import RTL_REPOS_WITH_RUNNING_TESTS_PATH
from ..constants import ENZYME_FILTERED_REPOS
from ..constants import RTL_FILTERED_REPOS

def save_test_suite_results(repo_path, test_suite_results_path, res):
    print("Writing to: ", test_suite_results_path)
    print("Writing data: ", res)
    try:
        # Check if `res` is None or not a string
        if res is None:
            print(f"Test suite results for {repo_path} are None. No data to write.")
            return
        
        # Convert res to string if it’s not a string already (handle other data types)
        if not isinstance(res, str):
            res = str(res)
        with open(test_suite_results_path, mode='w', encoding='utf-8') as file:
            file.write(res)
        print(f"Writing test suite results for {repo_path}")
    except Exception as e:
        print(f"An error occurred while saving test suite results for {repo_path}: {e}")

def append_to_csv(filename, name_to_search, data_to_append):
    # Read the existing data into memory
    with open(filename, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        lines = list(reader)
    
    # Find the index of the row containing the name
    header = lines[0]
    name_index = None
    for i, row in enumerate(lines[1:]):
        # Step 1: Split the row by '/'
        name = row[0].split('/')
        print("Name: ", name)
        if name_to_search == name[1]:
            name_index = i + 1
            break
    
    # Append data to the row if the name is found
    if name_index is not None:
        lines[name_index].extend(data_to_append)
    else:
        print(f"Name '{name_to_search}' not found in the CSV file.")
        return
    print("Writing new data: ", lines[name_index])
    # Write the updated data back to the CSV file
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=',', quoting=csv.QUOTE_NONE, quotechar='')
        writer.writerows(lines)
    print("Data appended successfully.")

def get_test_files(directory):
    print("Directory: ", directory)
    test_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            
            if fnmatch.fnmatch(file, '*.test.*') or fnmatch.fnmatch(file, '*.spec.*') or fnmatch.fnmatch(file, '*--spec.*'):
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
    print("Install - Dependencies -> Full_repo_path: ", full_repo_path)
    test_suite_results_path = os.path.join(full_repo_path, 'test_suite_results.txt')
    f = open(test_suite_results_path, 'w')
    
    if os.path.exists(os.path.join(full_repo_path, 'yarn.lock')):
        # Use yarn to install dependencies
        try:
            # Open the file in write mode
            with open(test_suite_results_path, 'w', encoding='utf-8') as file:
                # Start the subprocess
                process = subprocess.Popen(['yarn', 'install'], cwd=full_repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                print("Running yarn command...")

                # Write stdout and stderr to the file continuously
                for line in process.stdout:
                    file.write(str(line))
                
                # Optionally write stderr after stdout is finished
                stderr_output = process.stderr.read()
                if stderr_output:
                    file.write("\nStandard Error:\n")
                    file.write(stderr_output)
            
            print(f"Command output saved to {test_suite_results_path}")
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False
    else:
        try:
            # Open the file in write mode
            with open(test_suite_results_path, 'w', encoding='utf-8') as file:
                # Start the subprocess
                process = subprocess.Popen(['npm', 'install'], cwd=full_repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                print("Running npm command...")
                
                # Write stdout and stderr to the file continuously
                for line in process.stdout:
                    file.write(line)
                
                # Optionally write stderr after stdout is finished
                stderr_output = process.stderr.read()
                if stderr_output:
                    file.write("\nStandard Error:\n")
                    file.write(stderr_output)
            
            print(f"Command output saved to {test_suite_results_path}")
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

def run_test_suite(repo_path, idx):
    full_repo_path = os.path.join(ABSOLUTE_PATH, repo_path)
    test_suite_results_path = os.path.join(full_repo_path, 'test_suite_results.txt')
    try:
        with open(os.path.join(full_repo_path, 'package.json'), 'r') as f:
            package_json = json.load(f)
            test_command = package_json.get('scripts', {}).get('test')
            print(f"Test command: {test_command}")
            if test_command:
                test_package = test_command.split(" ")[0]
                print(f"Test package: {test_package}")

                if test_package:
                    try:
                        res = subprocess.run([test_package, 'test'], cwd=full_repo_path, capture_output=True, check=False, text=True, timeout=GLOBAL_TIMEOUT) 
                        # print(f'Result from testing: {res}')
                        save_test_suite_results(repo_path, test_suite_results_path, res)
                        print("Here_01")
                        
                        passing_tests, failing_tests = verify_test_suite_results(res, "Tests:")
                        print("Here_02")
                        passing_test_suites, failing_test_suites = verify_test_suite_results(res, "Test Suites:")
                        print("Here_03")
                        print(f'Successfully ran test in {repo_path}. {passing_tests} passed and {failing_tests} failed.')
                        print(f'Successfully ran test suite in {repo_path}. {passing_test_suites} passed and {failing_test_suites} failed.')
                        return (passing_tests, failing_tests, passing_test_suites, failing_test_suites)
                    except Exception as e:
                        save_test_suite_results(repo_path, test_suite_results_path, e)
                        print("There was an error while running tests: ", e)
                        return (-1,-1,-1,-1)
                else:
                    print(f'No test script found in package.json of {repo_path}')
                    return (-1,-1,-1,-1)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, AttributeError) as e:
        print(f'Error running npm test: {e}')
        print(f'\nError occured at index {idx}')
        save_test_suite_results(repo_path, test_suite_results_path, e)
        return (-1,-1,-1,-1)

def verify_test_suite_results(output, str_to_match):
    print("Verifying test_suite_results: ", output)
    text = str(output)
    print("after text to str")
    lines = text.strip().split("\\n")

    # Find the line starting with str_to_match
    tests_line = None
    for line in lines:
        if line.strip().startswith(str_to_match):
            tests_line = line
            break

    if tests_line == None:
        return (-1,-1)
    # Regular expressions to extract numbers
    total_tests_pattern = r'(\d+) total'
    passed_tests_pattern = r'(\d+) passed'
    skipped_tests_pattern = r'(\d+) skipped'
    failed_tests_pattern = r'(\d+) failed'

    # Extracting the numbers using regular expressions
    total_tests = int(found_match(total_tests_pattern, tests_line))
    passing_tests = int(found_match(passed_tests_pattern, tests_line))
    skipped_tests = int(found_match(skipped_tests_pattern, tests_line))
    failing_tests = int(found_match(failed_tests_pattern, tests_line))

    # Output the results
    print(f"Number of tests that passed: {passing_tests}")
    print(f"Number of tests that failed: {failing_tests}")
    return (passing_tests, failing_tests)

def found_match(pattern, text):
    match = re.search(pattern, text)
    print("FOUND MATCH: ", match)
    if match:
        return match.group(1)
    return 0

def verify_tests_can_run(repo, idx, file_path_to_update, should_write_to_file = True, is_post_migration = True):
    repo_name = clone_repo(repo)
    if repo_name:
        repo_path = os.path.join(ABSOLUTE_PATH, repo_name)
        if install_dependencies(repo_path, idx):
            try:
                passing_tests, failing_tests, passing_test_suites, failing_test_suites = run_test_suite(repo_path, idx)
                print("Preparing to write to file")
                if is_post_migration:
                    print(f"Writing post_migration for {repo}")
                    data_to_append = [str(passing_tests), str(failing_tests), str(passing_test_suites), str(failing_test_suites)]
                    append_to_csv(file_path_to_update, repo, data_to_append)
                elif should_write_to_file and passing_tests > 0:
                    print(f"Writing for {repo}")
                    with open(file_path_to_update, mode='a', encoding='utf-8') as file:
                        text_to_write = f"{repo},{str(passing_tests)},{str(failing_tests)},{str(passing_test_suites)},{str(failing_test_suites)}\n"
                        print("text_to_write: ", text_to_write)
                        file.write(text_to_write)
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
        if install_dependencies(repo_path, 0):
            passing_tests, failing_tests = run_test_suite(repo_path, 0)
            print(f"Ran tests for {repo_name}. {passing_tests} passed and {failing_tests} failed.")

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
    print("Checking repo: ", repo)
    
    if response.status_code == 200:
        try:
            package_json = response.json()
            dependencies = package_json.get('dependencies', {})
            dev_dependencies = package_json.get('devDependencies', {})
            
            for package_name in package_names:
                if package_name in dependencies or package_name in dev_dependencies:
                    print(f"{package_name} found in dependencies.")
                    try:
                        with open(ENZYME_FILTERED_REPOS, mode='a', encoding='utf-8') as file:
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

def run_parallel_verifications(repos, file_to_update):
    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
        futures = {executor.submit(verify_tests_can_run, repo, idx, file_to_update, True, False): repo for idx,repo in enumerate(repos)}
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            repo_name = repo.split('/')[-1]
            try:
                future.result()
                # remove_directory(repo_name)
            except Exception as exc:
                print(f"Repo {repo} generated an exception: {exc}")
                remove_directory(repo_name)


