from openai import OpenAI
import subprocess
from ..constants import *
from ..utils.utils import *

import logging
import os
import json
import argparse
import re
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
    full_path = os.path.join(ABSOLUTE_PATH_MIGRATION, repo_path)

    test_files = []
    for root, dirs, files in os.walk(full_path):
        # Skip node_modules and other unwanted directories
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.github', '__snapshots__')]

        # Check if 'test' or 'tests' is in the current directory path
        relative_root = os.path.relpath(root, full_path)
        path_parts = relative_root.split(os.sep)

        is_test_directory = 'test' in path_parts or 'tests' in path_parts

        for file in files:
            if "snapshot" in file or ".snap" in file or "test_suite_results" in file:
                continue

            # If the file is in a 'test' or 'tests' directory, include it
            if is_test_directory:
                test_files.append(os.path.join(root, file))
                continue

            # Include files that match test patterns
            if file.endswith('.test.js') or file.endswith('.spec.js') or 'test' in file:
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
    is_installed = False
    if is_jest_installed(repo_path):
        is_installed = True
        logger.info("Jest is already installed in the repository.")

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
        command = ['yarn', 'add', '--dev', 'jest@24' , 'babel-jest@24']
    else:
        command = ['npm', 'install', '--save-dev', 'jest@24', 'babel-jest@24']

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
    Updates the package.json file to configure Jest as the test runner and
    ensures the test script includes output options.

    Args:
        repo_path (str): The file system path to the repository.

    Raises:
        RuntimeError: If updating package.json fails.
    """
    logger = logging.getLogger(__name__)

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

    # Options to be added
    output_options = '--debug --json --outputFile=output.json'

    if 'jest' not in test_script:
        # If Jest is not in the test script, set it with the output options
        scripts['test'] = f'jest {output_options}'
        logger.info("Updated test script to use Jest with output options.")
    else:
        # Jest is already in the test script
        if output_options not in test_script:
            # Append the output options to the existing test script
            scripts['test'] = f'{test_script} {output_options}'
            logger.info("Appended output options to existing Jest test script.")
        else:
            logger.info("Test script already contains output options.")

    package_json['scripts'] = scripts

    # Optionally, add a basic Jest configuration if it doesn't exist
    if 'jest' not in package_json:
        package_json['jest'] = {
            "testEnvironment": "node"
        }
        logger.info("Added basic Jest configuration.")

    # Write the updated package.json back to the file
    with open(package_json_path, 'w', encoding='utf-8') as f:
        json.dump(package_json, f, indent=2)
        logger.info("package.json updated successfully.")

def process_repository(repo):
    repo_name = os.path.basename(repo['repo_name'])
    full_repo_path = os.path.join(ABSOLUTE_PATH_MIGRATION, repo_name)
    is_yarn_repo = os.path.exists(os.path.join(full_repo_path, 'yarn.lock'))
    new_packages = set()
    migrated_test_files = 0

    # Add Jest to the repository
    try:
        add_jest_to_repository(full_repo_path)
        setup_jest_dom_configuration(full_repo_path)
    except Exception as e:
        logger.error(f"Error adding Jest to '{repo_name}': {e}")
        return

    # Add new packages
    try:
        add_new_packages(full_repo_path, is_yarn_repo)
    except Exception as e:
        logger.error(f"Error adding new packages in '{repo_name}': {e}")
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
        command = ['yarn', 'add', '--dev', '@testing-library/react@12', '@testing-library/jest-dom@6']
    else:
        command = ['npm', 'install', '--save-dev', '@testing-library/react@12', '@testing-library/jest-dom@6']

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

def is_jest_dom_installed(repo_path):
    """
    Checks if jest-dom is installed in the given repository.

    Args:
        repo_path (str): The file system path to the repository.

    Returns:
        bool: True if jest-dom is installed, False otherwise.
    """
    package_json_path = os.path.join(repo_path, 'package.json')
    with open(package_json_path, 'r') as f:
        package_json = json.load(f)
    dependencies = package_json.get('dependencies', {})
    dev_dependencies = package_json.get('devDependencies', {})
    return '@testing-library/jest-dom' in dependencies or '@testing-library/jest-dom' in dev_dependencies

def install_jest_dom(repo_path, is_yarn_repo):
    """
    Installs jest-dom in the given repository.

    Args:
        repo_path (str): The file system path to the repository.
        is_yarn_repo (bool): True if the repository uses Yarn, False if it uses npm.
    """
    command = ['yarn', 'add', '@testing-library/jest-dom', '--dev'] if is_yarn_repo else ['npm', 'install', '@testing-library/jest-dom', '--save-dev']
    subprocess.run(command, cwd=repo_path, check=True)

def setup_jest_dom_configuration(repo_path):
    """
    Sets up jest-dom configuration by updating the setup files.

    Args:
        repo_path (str): The file system path to the repository.
    """
    logger = logging.getLogger(__name__)

    # Possible Jest configuration files
    jest_config_js = os.path.join(repo_path, 'jest.config.js')
    jest_config_json = os.path.join(repo_path, 'jest.config.json')
    package_json_path = os.path.join(repo_path, 'package.json')

    # Determine where Jest configuration exists and load it
    jest_config = None
    config_type = None
    package_json = None

    if os.path.exists(jest_config_json):
        # Load Jest configuration from jest.config.json
        with open(jest_config_json, 'r', encoding='utf-8') as f:
            try:
                jest_config = json.load(f)
                config_type = 'json'
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing jest.config.json: {e}")
                return
    elif os.path.exists(package_json_path):
        # Load Jest configuration from package.json
        with open(package_json_path, 'r', encoding='utf-8') as f:
            try:
                package_json = json.load(f)
                jest_config = package_json.get('jest', {})
                config_type = 'package'
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing package.json: {e}")
                return
    elif os.path.exists(jest_config_js):
        # Attempt to parse jest.config.js (limited parsing)
        jest_config = parse_jest_config_js(jest_config_js, logger)
        config_type = 'js'
    else:
        # No Jest configuration found; will create jest.config.js later
        jest_config = {}
        config_type = 'none'

    # Collect setup files from Jest configuration
    setup_files = []
    if 'setupFilesAfterEnv' in jest_config:
        setup_files = jest_config['setupFilesAfterEnv']
        if isinstance(setup_files, str):
            setup_files = [setup_files]
    elif 'setupTestFrameworkScriptFile' in jest_config:
        setup_file = jest_config['setupTestFrameworkScriptFile']
        if setup_file:
            setup_files = [setup_file]

    setup_files_updated = False
    root_dir = repo_path  # Assuming <rootDir> is repo_path

    # Process each setup file
    for idx, setup_file in enumerate(setup_files):
        # Resolve <rootDir>
        setup_file_path = setup_file.replace('<rootDir>', root_dir)
        # Make sure the path is absolute
        if not os.path.isabs(setup_file_path):
            setup_file_path = os.path.join(repo_path, setup_file_path)
        if os.path.exists(setup_file_path):
            # Check if jest-dom is already imported
            with open(setup_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if "@testing-library/jest-dom" not in content:
                with open(setup_file_path, 'a', encoding='utf-8') as f:
                    f.write("\nimport '@testing-library/jest-dom';\n")
                logger.info(f"Imported jest-dom into existing setup file: {setup_file}")
            else:
                logger.info(f"jest-dom is already imported in setup file: {setup_file}")
        else:
            # Setup file does not exist, create it
            os.makedirs(os.path.dirname(setup_file_path), exist_ok=True)
            with open(setup_file_path, 'w', encoding='utf-8') as f:
                f.write("import '@testing-library/jest-dom';\n")
            logger.info(f"Created setup file: {setup_file} and imported jest-dom.")

        # If using deprecated 'setupTestFrameworkScriptFile', update to 'setupFilesAfterEnv'
        if 'setupTestFrameworkScriptFile' in jest_config:
            jest_config['setupFilesAfterEnv'] = jest_config.get('setupFilesAfterEnv', [])
            if setup_file not in jest_config['setupFilesAfterEnv']:
                jest_config['setupFilesAfterEnv'].append(setup_file)
            del jest_config['setupTestFrameworkScriptFile']
            setup_files_updated = True

    if not setup_files:
        # No setup files specified in configuration
        # Create setupTests.js and update configuration
        setup_file = 'setupTests.js'
        setup_file_path = os.path.join(repo_path, setup_file)
        if not os.path.exists(setup_file_path):
            with open(setup_file_path, 'w', encoding='utf-8') as f:
                f.write("import '@testing-library/jest-dom';\n")
            logger.info("Created setupTests.js and imported jest-dom.")
        else:
            # Check if jest-dom is already imported
            with open(setup_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if "@testing-library/jest-dom" not in content:
                with open(setup_file_path, 'a', encoding='utf-8') as f:
                    f.write("\nimport '@testing-library/jest-dom';\n")
                logger.info("Imported jest-dom into existing setupTests.js.")
            else:
                logger.info("jest-dom is already imported in setupTests.js.")
        # Update Jest configuration to include setupFilesAfterEnv
        jest_config['setupFilesAfterEnv'] = [f'<rootDir>/{setup_file}']
        setup_files_updated = True

    # Write back the updated configuration
    if config_type == 'json':
        with open(jest_config_json, 'w', encoding='utf-8') as f:
            json.dump(jest_config, f, indent=2)
            logger.info("Updated jest.config.json with setupFilesAfterEnv.")
    elif config_type == 'package':
        # Update package.json Jest configuration
        package_json['jest'] = jest_config
        with open(package_json_path, 'w', encoding='utf-8') as f:
            json.dump(package_json, f, indent=2)
            logger.info("Updated package.json Jest configuration with setupFilesAfterEnv.")
    elif config_type == 'js':
        # Updating jest.config.js is complex; inform the user
        if setup_files_updated:
            logger.warning("Please update jest.config.js to include 'setupFilesAfterEnv' with the setup file.")
    else:
        # No existing configuration, create jest.config.js
        jest_config_js = os.path.join(repo_path, 'jest.config.js')
        with open(jest_config_js, 'w', encoding='utf-8') as f:
            f.write("module.exports = {\n")
            f.write(f"  setupFilesAfterEnv: ['<rootDir>/{setup_file}'],\n")
            f.write("  testEnvironment: 'jsdom',\n")
            f.write("};\n")
        logger.info("Created jest.config.js with setupFilesAfterEnv configuration.")

def parse_jest_config_js(jest_config_js, logger):
    """
    Parses jest.config.js to extract Jest configuration.

    Args:
        jest_config_js (str): Path to jest.config.js file.
        logger (Logger): Logger instance.

    Returns:
        dict: Parsed Jest configuration.
    """
    import ast

    jest_config = {}
    try:
        with open(jest_config_js, 'r', encoding='utf-8') as f:
            content = f.read()
        # Very basic parsing to extract setupFilesAfterEnv and setupTestFrameworkScriptFile
        setup_files = []

        # Match setupFilesAfterEnv: ['<rootDir>/setupTests.js']
        match = re.search(r'setupFilesAfterEnv\s*:\s*(\[[^\]]*\])', content)
        if match:
            array_str = match.group(1)
            array_str = array_str.replace("'", '"')
            setup_files = json.loads(array_str)
            jest_config['setupFilesAfterEnv'] = setup_files
        else:
            # Match setupTestFrameworkScriptFile: '<rootDir>/test/testSetup.js'
            match = re.search(r'setupTestFrameworkScriptFile\s*:\s*["\']([^"\']+)["\']', content)
            if match:
                setup_file = match.group(1)
                jest_config['setupTestFrameworkScriptFile'] = setup_file

    except Exception as e:
        logger.error(f"Error parsing jest.config.js: {e}")

    return jest_config
def update_jest_config_js(jest_config_js, setup_file, logger):
    """
    Updates jest.config.js to include setupFilesAfterEnv .

    Args:
        jest_config_js (str): Path to jest.config.js file.
        setup_file (str): Path to setupTests.js file.
        logger (Logger): Logger instance.
    """
    with open(jest_config_js, 'r', encoding='utf-8') as f:
        jest_config_content = f.read()

    if 'setupFilesAfterEnv' not in jest_config_content:
        # Append the setupFilesAfterEnv  configuration
        with open(jest_config_js, 'a', encoding='utf-8') as f:
            f.write(f"\nmodule.exports.setupFilesAfterEnv  = '<rootDir>/{os.path.basename(setup_file)}';\n")
        logger.info("Added setupFilesAfterEnv  to jest.config.js.")
    else:
        logger.info("setupFilesAfterEnv  is already configured in jest.config.js.")

def update_jest_config_json(jest_config_json, setup_file, logger):
    """
    Updates jest.config.json to include setupFilesAfterEnv .

    Args:
        jest_config_json (str): Path to jest.config.json file.
        setup_file (str): Path to setupTests.js file.
        logger (Logger): Logger instance.
    """
    with open(jest_config_json, 'r', encoding='utf-8') as f:
        jest_config = json.load(f)

    if 'setupFilesAfterEnv' not in jest_config:
        jest_config['setupFilesAfterEnv'] = f'<rootDir>/{os.path.basename(setup_file)}'
        with open(jest_config_json, 'w', encoding='utf-8') as f:
            json.dump(jest_config, f, indent=2)
        logger.info("Added setupFilesAfterEnv  to jest.config.json.")
    else:
        logger.info("setupFilesAfterEnv  is already configured in jest.config.json.")

def update_package_json_jest(package_json_path, setup_file, logger):
    """
    Updates package.json's Jest configuration to include setupFilesAfterEnv .

    Args:
        package_json_path (str): Path to package.json file.
        setup_file (str): Path to setupTests.js file.
        logger (Logger): Logger instance.
    """
    with open(package_json_path, 'r', encoding='utf-8') as f:
        package_json = json.load(f)

    jest_config = package_json.get('jest', {})
    if 'setupFilesAfterEnv' not in jest_config:
        jest_config['setupFilesAfterEnv'] = f'<rootDir>/{os.path.basename(setup_file)}'
        package_json['jest'] = jest_config
        with open(package_json_path, 'w', encoding='utf-8') as f:
            json.dump(package_json, f, indent=2)
        logger.info("Added setupFilesAfterEnv  to Jest configuration in package.json.")
    else:
        logger.info("setupFilesAfterEnv  is already configured in package.json.")

def create_jest_config_js(jest_config_js, setup_file, logger):
    """
    Creates jest.config.js with setupFilesAfterEnv  configuration.

    Args:
        jest_config_js (str): Path to create jest.config.js file.
        setup_file (str): Path to setupTests.js file.
        logger (Logger): Logger instance.
    """
    with open(jest_config_js, 'w', encoding='utf-8') as f:
        f.write("module.exports = {\n")
        f.write(f"  setupFilesAfterEnv : '<rootDir>/{os.path.basename(setup_file)}',\n")
        f.write("  testEnvironment: 'jsdom',\n")
        f.write("};\n")
    logger.info("Created jest.config.js with setupFilesAfterEnv  configuration.")


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
        future_to_repo = {executor.submit(process_repository, repo): repo for repo in repos[70:]}

        for future in concurrent.futures.as_completed(future_to_repo):
            repo = future_to_repo[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing repository '{repo.get('repo_name', 'Unknown')}': {e}")

# Ex. python -m JavaScriptTestMigration.scripts.migrate_test_files
if __name__ == '__main__':
    main()


# TODO: add docs as context: https://testing-library.com/docs/react-testing-library/migrate-from-enzyme/
# TODO: add imports as context
# TODO: generate DOM and add as context 
