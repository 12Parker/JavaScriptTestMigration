from openai import OpenAI
import subprocess
from ..constants import *
from ..utils.utils import *

import logging
import os
import json
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Constants
FRAMEWORK_CONVERSION_INFO = {
    'original': 'enzyme',
    'new': '@testing-library/react'
}

# Set up your OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)

def read_file(file_path):
    print("FILE: ", file_path)
    with open(file_path, 'r') as file:
        content = file.read()
    return content

def write_file(file_path, content):
    print("WRITE TO FILE: ", file_path)
    with open(file_path, 'w') as file:
        file.write(content)

def make_changes_to_content(content, original_test_framework, new_test_framework):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content":f"Here is a text file content:\n\n{content}\n\nPlease perform the following tasks:\
                1. Complete the conversion for the test file.\
                2. Convert all test cases and ensure the same number of tests in the file\
                3. Replace {original_test_framework} methods with the equivalent {new_test_framework} methods.\
                4. Update {original_test_framework} imports to {new_test_framework} imports.\
                5. Adjust {original_test_framework} matchers for {new_test_framework}.\
                6. Return the entire file with all converted test cases.\
                7. Do not modify anything else, including imports for React components and helpers.\
                8. Preserve all abstracted functions as they are and use them in the converted file.\
                9. Maintain the original organization and naming of describe and it blocks.\
                10. VERY IMPORTANT: Do not include code tags or any comments. Return only the updated file"
            }
        ],
    )
    return response.choices[0].message.content

def list_new_packages(original_file,updated_file):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "assistant", "content": original_file},
            {"role": "assistant", "content": updated_file},
            {"role": "user", "content":f"List all of the new imports that you added to this file. Separate each package with a comma. Only respond with the package names."
            }
        ],
    )
    return response.choices[0].message.content

def find_test_files(repo_path):
    full_path = os.path.join(ABSOLUTE_PATH_MIGRATION,repo_path)

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

def add_migrated_to_filename(file_path):
    directory, filename = os.path.split(file_path)
    name_parts = filename.split('.', 1)  # Split at the first period
    if "migrated" in file_path:
        print("Already has migrated in name, use same file name")
        return file_path
    if len(name_parts) > 1:
        new_filename = f"{name_parts[0]}-migrated.{name_parts[1]}"
    else:
        new_filename = f"{name_parts[0]}-migrated"  # In case there's no period
    new_file_path = os.path.join(directory, new_filename)
    return new_file_path

def remove_code_tags_from_string(text):
    lines = text.splitlines()

    # Remove the first and last line if they contain code tags
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    # Join the lines back into a single string
    return "\n".join(lines)

# TODO: Update this to check for jest-dom not only jest
def add_jest_to_repository(repo_path):
    """
    Adds Jest testing library to the given repository.

    Args:
        repo_path (str): The file system path to the repository.

    Raises:
        RuntimeError: If installation fails.
    """
    is_yarn_repo = is_yarn_repository(repo_path)

    # Check if Jest is already installed
    if is_jest_installed(repo_path):
        logger.info("Jest is already installed in the repository.")
        return

    # Install Jest
    try:
        install_jest(repo_path, is_yarn_repo)
    except Exception as e:
        logger.error(f"Error installing Jest: {e}")
        raise

    # Update package.json to use Jest for testing
    try:
        update_package_json_for_jest(repo_path)
    except Exception as e:
        logger.error(f"Error updating package.json for Jest: {e}")
        raise

    logger.info("Jest has been successfully added to the repository.")

def is_yarn_repository(repo_path):
    """
    Determines if the repository uses Yarn by checking for a yarn.lock file.

    Args:
        repo_path (str): The file system path to the repository.

    Returns:
        bool: True if Yarn is used, False otherwise.
    """
    yarn_lock_path = os.path.join(repo_path, 'yarn.lock')
    is_yarn = os.path.exists(yarn_lock_path)
    logger.debug(f"Repository uses {'Yarn' if is_yarn else 'npm'}.")
    return is_yarn

def is_jest_installed(repo_path):
    """
    Checks if Jest is already listed in the repository's dependencies or devDependencies.

    Args:
        repo_path (str): The file system path to the repository.

    Returns:
        bool: True if Jest is installed, False otherwise.
    """
    package_json_path = os.path.join(repo_path, 'package.json')
    if not os.path.exists(package_json_path):
        logger.warning("package.json not found in the repository.")
        return False

    with open(package_json_path, 'r', encoding='utf-8') as f:
        try:
            package_json = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing package.json: {e}")
            return False

    dependencies = package_json.get('dependencies', {})
    dev_dependencies = package_json.get('devDependencies', {})
    jest_installed = 'jest' in dependencies or 'jest' in dev_dependencies

    logger.debug(f"Jest installed: {jest_installed}")
    return jest_installed

def install_jest(repo_path, is_yarn_repo):
    """
    Installs Jest using npm or Yarn.

    Args:
        repo_path (str): The file system path to the repository.
        is_yarn_repo (bool): True if Yarn is used, False if npm is used.

    Raises:
        RuntimeError: If the installation command fails.
    """
    if is_yarn_repo:
        command = ['yarn', 'add', '--dev', 'jest']
    else:
        command = ['npm', 'install', '--save-dev', 'jest']

    logger.info(f"Installing Jest using {'Yarn' if is_yarn_repo else 'npm'}...")
    result = subprocess.run(
        command,
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=GLOBAL_TIMEOUT
    )

    if result.returncode != 0:
        error_message = result.stderr.strip() or 'Unknown error'
        logger.error(f"Failed to install Jest: {error_message}")
        raise RuntimeError(f"Jest installation failed: {error_message}")

    logger.info("Jest installation successful.")

def update_package_json_for_jest(repo_path):
    """
    Updates the package.json file to configure Jest as the test runner.

    Args:
        repo_path (str): The file system path to the repository.

    Raises:
        RuntimeError: If updating package.json fails.
    """
    package_json_path = os.path.join(repo_path, 'package.json')
    if not os.path.exists(package_json_path):
        raise RuntimeError("package.json not found in the repository.")

    with open(package_json_path, 'r', encoding='utf-8') as f:
        try:
            package_json = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing package.json: {e}")
            raise RuntimeError("Failed to parse package.json.")

    # Update the test script
    scripts = package_json.get('scripts', {})
    test_script = scripts.get('test', '')

    if 'jest' not in test_script:
        scripts['test'] = 'jest'
        package_json['scripts'] = scripts
        logger.info("Updated test script to use Jest.")

    # Optionally, add a basic Jest configuration
    if 'jest' not in package_json:
        package_json['jest'] = {
            "testEnvironment": "node"
        }
        logger.info("Added basic Jest configuration.")

    # Write the updated package.json back to the file
    with open(package_json_path, 'w', encoding='utf-8') as f:
        json.dump(package_json, f, indent=2)
        logger.info("package.json updated successfully.")
# TODO: Update the params to accept a list of repo's or make new method to handle single migration 
def main():
    # Path to the file containing the list of repositories
    repos_file_path = '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/Enzyme/repos_with_running_tests.txt'  # Replace with your actual path

    # Extract repositories
    try:
        repos = extract_repo_name_and_brace_UI_test_framework(repos_file_path)
    except Exception as e:
        logger.error(f"Error extracting repositories: {e}")
        return

    # Define the maximum number of workers
    max_workers = min(32, os.cpu_count() + 4)

    # Use ThreadPoolExecutor for I/O-bound tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a dictionary to hold futures
        future_to_repo = {executor.submit(process_repository, repo): repo for repo in repos[4:]}

        for future in concurrent.futures.as_completed(future_to_repo):
            repo = future_to_repo[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing repository '{repo.get('repo_name', 'Unknown')}': {e}")

def process_repository(repo):
    repo_name = os.path.basename(repo['repo_name'])
    full_repo_path = os.path.join(ABSOLUTE_PATH_MIGRATION, repo_name)
    is_yarn_repo = os.path.exists(os.path.join(full_repo_path, 'yarn.lock'))
    new_packages = set()
    migrated_test_files = 0

    # Add Jest to the repository
    try:
        add_jest_to_repository(full_repo_path)
    except Exception as e:
        logger.error(f"Error adding Jest to '{repo_name}': {e}")
        return

    # Find test files
    try:
        test_files = find_test_files(full_repo_path)
        logger.info(f"Found {len(test_files)} test files in repository '{repo_name}'")
    except Exception as e:
        logger.error(f"Error finding test files in '{repo_name}': {e}")
        return

    # Process each test file
    for file_path in test_files:
        try:
            if process_test_file(file_path, new_packages):
                migrated_test_files += 1
        except Exception as e:
            logger.error(f"Error processing file '{file_path}': {e}")

    if migrated_test_files == 0:
        logger.info(f"No test files migrated in repository '{repo_name}'")
        return

    # Add new packages
    try:
        add_new_packages(full_repo_path, is_yarn_repo)
    except Exception as e:
        logger.error(f"Error adding new packages in '{repo_name}': {e}")
        return

    # Re-run the test suite
    try:
        verify_tests_can_run(
            '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/react_enzyme_repositories_zero_shot', 
            repo_name, 
            0, 
            '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/Enzyme/repos_migrated.txt', 
            '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/Enzyme/repos_migrated_failures.txt', 
            True, 
            False, 
            migrated_test_files, 
            False
        )
    except Exception as e:
        logger.error(f"Error verifying tests in '{repo_name}': {e}")

def process_test_file(file_path, new_packages):
    content = read_file(file_path)
    original_framework = FRAMEWORK_CONVERSION_INFO['original']
    new_framework = FRAMEWORK_CONVERSION_INFO['new']

    if original_framework not in content and new_framework not in content:
        logger.info(f"Skipping '{file_path}': Does not contain '{original_framework}' or '{new_framework}'")
        return False

    # Make changes to the content using OpenAI API
    modified_content = make_changes_to_content(content, original_framework, new_framework)

    # Remove code tags if any
    modified_content = remove_code_tags_from_string(modified_content)

    # Write the modified content back to the file
    write_file(file_path, modified_content)
    logger.info(f"Modified content written to '{file_path}'")

    # List new packages
    new_packages_list = list_new_packages(content, modified_content)
    items = [item.strip() for item in new_packages_list.split(',') if item.strip()]
    new_packages.update(items)
    return True

def add_new_packages(repo_path, is_yarn_repo):
    if is_yarn_repo:
        command = ['yarn', 'add', '--dev', '@testing-library/react', '@testing-library/jest-dom']
    else:
        command = ['npm', 'install', '--save-dev', '@testing-library/react', '@testing-library/jest-dom']

    logger.info(f"Adding new packages in '{repo_path}' using {'Yarn' if is_yarn_repo else 'npm'}")
    result = subprocess.run(
        command,
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=GLOBAL_TIMEOUT
    )

    if result.returncode != 0:
        error_message = result.stderr.strip() or 'Unknown error'
        logger.error(f"Failed to add new packages: {error_message}")
        raise RuntimeError(f"Package installation failed: {error_message}")

    logger.info("New packages added successfully")

# Ex. python -m JavaScriptTestMigration.scripts.migrate_test_files
if __name__ == '__main__':
    main()


# TODO: add docs as context: https://testing-library.com/docs/react-testing-library/migrate-from-enzyme/
# TODO: add imports as context
# TODO: generate DOM and add as context 
