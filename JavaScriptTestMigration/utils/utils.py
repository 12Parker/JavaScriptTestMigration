import ast
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
import logging

from threading import Lock
from itertools import product
from collections import Counter
from ..constants import *

logging.basicConfig(level=logging.INFO, format='%(threadName)s: %(message)s')
file_lock = Lock()

def extract_repo_name_and_brace_UI_test_framework(filename):
    results = []
    
    with open(filename, 'r') as file:
        for line in file:
            # Extract the dictionary-like string at the beginning of the line
            match = re.search(r'\{.*?\}', line)
            if match:
                dict_str = match.group()
                # Safely evaluate the string as a Python literal
                data_dict = ast.literal_eval(dict_str)
                repo_name = data_dict.get('repo_name', '')
                UI_test_framework = data_dict.get('UI_test_framework', [])
            else:
                repo_name = ''
                UI_test_framework = []
            
            # Append the extracted data to the results list
            results.append({'repo_name': repo_name, 'UI_test_framework': UI_test_framework})
    
    return results
    
def save_test_suite_results(repo_path, test_suite_results_path, res):
    print("Writing to: ", test_suite_results_path)
    # print("Writing data: ", res)
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

def clone_repo(repo_path, repo):
    print(f'{repo} - clone')
    url = f'https://github.com/{repo}.git'
    repo_name = repo.split('/')[-1]

    if os.path.exists(os.path.join(repo_path, repo_name)):
        print(f'{repo_name} already exists. Skipping clone.')
        return repo_name
    try:
        result = subprocess.run(['git', 'clone', url], cwd=repo_path, check=True, capture_output=True, text=True, timeout=GLOBAL_TIMEOUT)
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
                    return False
            
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

def verify_tests_can_run(repo_path, repo, idx, file_path_to_update, file_path_to_update_failures=None, should_write_to_file=True, is_post_migration=False, files_migrated=-1, should_clone = True):
    repo_name = repo
    if should_clone:
        repo_name = clone_repo(repo_path, repo['repo_name'])    

    if not repo_name:
        logging.error(f"Failed to clone repository {repo}")
        if should_write_to_file and file_path_to_update_failures is not None:
            write_failure(repo, file_path_to_update_failures)
        return

    repo_path = os.path.join(repo_path, repo_name)
    if not install_dependencies(repo_path, idx):
        logging.error(f"Failed to install dependencies for {repo}")
        if should_write_to_file and file_path_to_update_failures is not None:
            write_failure(repo, file_path_to_update_failures)
        return

    try:
        passing_tests, failing_tests, passing_test_suites, failing_test_suites = run_test_suite(repo_path, idx)
    except Exception as e:
        logging.error(f"An error occurred while running the test suite for {repo}: {e}")
        if should_write_to_file and file_path_to_update_failures is not None:
            write_failure(repo, file_path_to_update_failures)
        return

    logging.info(f"Test suite completed for {repo}")

    if passing_tests == -1:
        logging.warning(f"No passing tests for {repo}")
        if should_write_to_file and file_path_to_update_failures is not None:
            write_failure(repo, file_path_to_update_failures)
        return

    if should_write_to_file:
        data_to_append = [
            str(passing_tests), str(failing_tests),
            str(passing_test_suites), str(failing_test_suites),
            str(files_migrated)
        ]
        if is_post_migration:
            append_to_csv(file_path_to_update, repo, data_to_append)
        else:
            write_success(repo, data_to_append, file_path_to_update)

    logging.info(f"Results written for {repo}")

def write_failure(repo, failure_file):
    with file_lock:
        with open(failure_file, mode='a', encoding='utf-8') as file:
            file.write(f"{repo}\n")

def write_success(repo, data, success_file):
    with file_lock:
        with open(success_file, mode='a', encoding='utf-8') as file:
            file.write(f"{repo}," + ",".join(data) + "\n")

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

def test_single_repo(repo, repo_path = ABSOLUTE_PATH, ):
    repo_name = clone_repo(repo_path, repo)
    if repo_name:
        repo_path = os.path.join(ABSOLUTE_PATH, repo_name)
        if install_dependencies(repo_path, 0):
            passing_tests, failing_tests, passing_tests_suites, failing_tests_suites = run_test_suite(repo_path, 0)
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

def find_all_matching_strings(dependencies, dev_dependencies, string_list):
    dependencies_result = {s for s in string_list if s in dependencies}
    dev_dependencies_result = {s for s in string_list if s in dev_dependencies}
    return dependencies_result.union(dev_dependencies_result)

def increment_nested_counter(nested_counter, UI_test_framework, unit_test_library, ui_framework, test_framework=None, unit_library=None):
    print("Increment the counter: ", nested_counter, test_framework, unit_library)
    if ui_framework in nested_counter:
        print("Increment the framework: ", ui_framework)
        if test_framework in UI_test_framework:
            nested_counter[ui_framework][test_framework] += 1
        if unit_library in unit_test_library:
            nested_counter[ui_framework][unit_library] += 1
    else:
        print(f"{ui_framework} is not in the list of UI frameworks.")

def check_package_in_repo(repo, nested_counter, UI_framework, UI_test_framework, unit_test_library, branch='master'):
    url = f'https://raw.githubusercontent.com/{repo}/{branch}/package.json'
    response = requests.get(url)
    
    
    print(f"Checking repo: {repo}")

    if response.status_code != 200:
        print(f"Failed to fetch {url}")
        return False
    
    try:
        package_json = response.json()
    except ValueError:
        print(f"Error decoding JSON for {repo}")
        return False

    dependencies = package_json.get('dependencies', {})
    dev_dependencies = package_json.get('devDependencies', {})

    for package_name in UI_framework:
        if package_name in dependencies or package_name in dev_dependencies:
            print(f"{package_name} found in dependencies.")
            repo_name = 'angular' if package_name == '@angular/core' else package_name
            repos_with_UI_framework_path = os.path.join(SEART_FILTERED_REPOS, repo_name, 'repos_with_UI_framework.txt')
            
            # try:
            #     with open(repos_with_UI_framework_path, mode='a', encoding='utf-8') as file:
            #         file.write(f"{repo}\n")
            #         print(f"{package_name} written to file")
            # except Exception as e:
            #     print(f"An error occurred while writing to file: {e}") 
            
            # Consolidate test framework and unit test library matching
            test_frameworks = find_all_matching_strings(dependencies, dev_dependencies, UI_test_framework)   
            unit_test_libraries = find_all_matching_strings(dependencies, dev_dependencies, unit_test_library)

            # Iterate through every combination of test_frameworks and unit_test_libraries
            for test_framework, unit_library in product(test_frameworks, unit_test_libraries):
                print("Updating counter")
                increment_nested_counter(nested_counter, UI_test_framework, unit_test_library, package_name, test_framework, unit_library)

            if not test_frameworks:
                print("No test framework")
                continue

            ui_repo_path = os.path.join(SEART_FILTERED_REPOS, repo_name, 'repos.txt')

            try:
                with open(ui_repo_path, mode='a', encoding='utf-8') as file:
                    file.write(f"{repo},{test_frameworks},{unit_test_libraries}\n")
                    print(f"{package_name} written to file")
            except Exception as e:
                print(f"An error occurred while writing to file: {e}")  
            return True
    return False


def run_parallel_package_checks(repos, nested_counter, UI_framework, UI_test_framework, unit_test_library, branch='master'):
    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
        futures = {executor.submit(check_package_in_repo, repo, nested_counter, UI_framework, UI_test_framework, unit_test_library, branch): repo for repo in repos}
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            try:
                future.result(timeout=GLOBAL_TIMEOUT)
            except Exception as exc:
                print(f"Repo {repo} generated an exception: {exc}")

def run_parallel_verifications(repos, file_to_update, failure_file_to_update):
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {
            executor.submit(
                verify_tests_can_run,
                ABSOLUTE_PATH,
                repo,
                idx,
                file_to_update,
                failure_file_to_update,
                False,
                False
            ): repo for idx, repo in enumerate(repos)
        }
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            repo_name = repo['repo_name'].split('/')[-1]
            path = os.path.join(ABSOLUTE_PATH, repo_name)
            try:
                # Ensure the future completed successfully
                future.result()
                print("Done verifying tests can run for", repo_name)
            except Exception as exc:
                print(f"Repo {repo} generated an exception: {exc}")
            finally:
                # Clean up the directory regardless of success or failure
                print("Removing directory...")
                # remove_directory(path)


