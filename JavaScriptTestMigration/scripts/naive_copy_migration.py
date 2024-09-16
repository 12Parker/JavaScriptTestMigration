import subprocess
from ..constants import *
from ..utils.utils import verify_tests_can_run
from ..utils.utils import extract_repo_name_and_brace_UI_test_framework
import os
import argparse
import logging

def remove_lines_with_original_framework(file_path, original_framework):
    # Set up logging configuration
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
    logger = logging.getLogger(__name__)
    logger.info(f"Processing file: {file_path}")

    original_framework_lower = original_framework.lower()

    try:
        # Attempt to open and read the file
        with open(file_path, 'r') as file:
            lines = file.readlines()
    except Exception as e:
        logger.error(f"Error reading file '{file_path}': {e}")
        return  # Stop execution if file can't be read

    try:
        # Attempt to open the file in write mode
        with open(file_path, 'w') as file:
            skip_block = False
            brace_count = 0  # To keep track of nested braces

            for line_number, line in enumerate(lines, start=1):
                try:
                    line_lower = line.lower()

                    if not skip_block:
                        # Check if the line starts the configure block
                        if f"{original_framework_lower}.configure" in line_lower:
                            skip_block = True
                            brace_count += line.count('{') - line.count('}')
                            logger.info(f"Ignoring line {line_number} (start of configure block): {line.strip()}")
                            continue
                        # Check if the line contains the original framework
                        elif original_framework_lower in line_lower:
                            logger.info(f"Ignoring line {line_number} (contains original framework): {line.strip()}")
                            continue
                        else:
                            file.write(line)
                    else:
                        # Inside the configure block
                        brace_count += line.count('{') - line.count('}')
                        logger.info(f"Ignoring line {line_number} (inside configure block): {line.strip()}")
                        if brace_count <= 0:
                            skip_block = False
                        continue
                except Exception as e:
                    logger.error(f"Error processing line {line_number}: {e}")
                    # Continue to the next line after logging the error
                    continue
    except Exception as e:
        logger.error(f"Error writing to file '{file_path}': {e}")
        return  # Stop execution if file can't be written

    logger.info(f"Finished processing file: {file_path}")

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

# python -m JavaScriptTestMigration.scripts.naive_copy_migration
def main():
    start = 0
    repos = extract_repo_name_and_brace_UI_test_framework('/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/Enzyme/repos_with_running_tests.txt')

    for repo in repos[start:]:
        repo_name = repo['repo_name'].split('/')[-1]
        migrated_test_files = 0
        files = find_test_files(repo_name)
        full_repo_path = os.path.join(ABSOLUTE_PATH_NAIVE_COPY, repo_name)

        framework_conversion_info = {'original': 'enzyme', 'new': '@testing-library/react'}

        print("Found test files: ", len(files))
        for file in files:
            input_file_path = file  # Path to the input file
            remove_lines_with_original_framework(input_file_path, framework_conversion_info['original'])
        #Re-run the test suite and save the results
        print("\nRe-running the test suite after naive copy\n")
        try:
            verify_tests_can_run(ABSOLUTE_PATH_NAIVE_COPY, repo_name, 0, ENZYME_REPOS_NAIVE_COPY_PATH, '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/Enzyme/repos_naive_copy_failures.txt', True, False, migrated_test_files, False)
        except Exception as e:
            print(f"Encountered exception {e}, for repo {repo_name}")

# Ex. python -m JavaScriptTestMigration.scripts.naive_copy_migration
if __name__ == '__main__':
    main()
