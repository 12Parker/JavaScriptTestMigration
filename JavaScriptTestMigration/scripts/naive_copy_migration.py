import subprocess
from ..constants import *
from ..repo_names.enzyme.enzyme_repos_with_running_tests import repos
# from ..repo_names.rtl.rtl_repos_with_running_tests import repos
from ..utils.utils import verify_tests_can_run
import os
import argparse

def remove_lines_with_original_framework(file_path, original_framework):
    print("File_path: ", file_path)
    # Open the file in read mode to get the lines
    with open(file_path, 'r') as file:
        lines = file.readlines()

    # Open the file in write mode to overwrite it without the unwanted lines
    # Enzyme.configure or 
    with open(file_path, 'w') as file:
        for line in lines:
            # Only write the line if it doesn't contain "from '<original_framework>'"
            if f"{original_framework}" not in line.lower():
                file.write(line)
            else:
                print("Ignoring this line")

def find_test_files(repo_path):
    full_path = os.path.join(ABSOLUTE_PATH_NAIVE_COPY,repo_path)

    test_files = []
    for root, dirs, files in os.walk(full_path):
        # Skip node_modules directory
        dirs[:] = [d for d in dirs if d != 'node_modules' and d != '.github' and d != '__snapshots__']
        
        for file in files:
            if "snapshot" in file or ".snap" in file or "test_suite_results" in file: 
                continue
            if file.endswith('.test.js') or file.endswith('.spec.js') or "test" in file:
                test_files.append(os.path.join(root, file))
    return test_files

def main():
    start = 0

    for repo in repos[start:]:
        migrated_test_files = 0
        files = find_test_files(repo)
        full_repo_path = os.path.join(ABSOLUTE_PATH_NAIVE_COPY, repo)

        framework_conversion_info = {'original': 'enzyme', 'new': '@testing-library/react'}

        print("Found test files: ", len(files))
        for file in files:
            input_file_path = file  # Path to the input file
            # remove_lines_with_original_framework(input_file_path, framework_conversion_info['original'])
        #Re-run the test suite and save the results
        print("\nRe-running the test suite after naive copy\n")
        try:
            verify_tests_can_run(ABSOLUTE_PATH_NAIVE_COPY, repo, 0, ENZYME_REPOS_NAIVE_COPY_PATH, True, False, migrated_test_files)
        except Exception as e:
            print(f"Encountered exception {e}, for repo {repo}")

# Ex. python -m JavaScriptTestMigration.scripts.naive_copy_migration
if __name__ == '__main__':
    main()
