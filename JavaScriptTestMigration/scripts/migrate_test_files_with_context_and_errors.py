import os
import re
import argparse
from pathlib import Path
import subprocess
from openai import OpenAI
from ..constants import *
from ..repo_names.enzyme.enzyme_repos_with_running_tests import repos
from ..utils.utils import verify_tests_can_run
from collections import defaultdict

# Set up your OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = 'gpt-4o-mini'

ESLINT = """{
  "extends": ["@react-bootstrap", "prettier"],
  "plugins": ["prettier"],
  "rules": {
    "react/jsx-filename-extension": "off",
    "import/no-extraneous-dependencies": "off",
    "react/jsx-props-no-spreading": "off",
    "max-len": "off",
    "no-nested-ternary": "off",
    "import/prefer-default-export": "off"
  },
  "env": {
    "browser": true,
    "node": true
  }
}"""

def build_package_update_prompt(package_json_file, error_file_content, history, new_testing_framework):
    return f"""Here is a package.json file: {package_json_file}.
            These dependencies were added previously: {history}

            Using this error message as context: {error_file_content}
            Determine if the package.json file needs to be updated. 
            IMPORTANT: Remove any duplicate or repeated imports.
            If it needs to be updated: 
                You should add all required libraries for the new test framework: {new_testing_framework}
                You should only update the previously added dependencies.
            Do not include code tags or any comments. Return only the updated file."""


def read_file(file_path):
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as file:
        return file.read()


def write_file(file_path, content):
    print(f"Writing to file: {file_path}")
    with open(file_path, 'w') as file:
        file.write(content)


def request_full_file_update(content, framework_conversion_info, imported_file_contents, error_file_content):
    message = f"""You are tasked with migrating the following test file from {framework_conversion_info['original']} to {framework_conversion_info['new']}:
                \nTest File Content:
                {content}\n  
                
                \nErrors to be fixed for the tests to pass:
                {error_file_content}\n  
                
                \nImports at the top of the file:
                {imported_file_contents}\n  

                The new file should respect the linting rules: {ESLINT}
                
                Please ensure the following:
                Fix the Tests: Resolve all errors to ensure that the tests pass successfully in the new framework.
                Preserve Structure: Maintain the original structure and organization of the file, including:
                Abstracted functions
                describe and it blocks
                Do Not Modify Unrelated Code: Only modify the code necessary for the migration to ensure compatibility with the new framework.
                Do Not Include:
                    VERY IMPORTANT: Do not include any code tags (such as ```) Code tags (such as ```)
                    Comments or explanations in the returned code
                Output: Return only the fully migrated and functional test file. The file should be ready to execute with all tests passing in the new framework.
            """
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content


def request_code_update(content, framework_conversion_info, imported_file_contents, error_file_content):
    message = f"""You are tasked with migrating the following test file from {framework_conversion_info['original']} to {framework_conversion_info['new']}:
                \nTest File Content:
                {content}\n  
                
                \nErrors to be fixed for the tests to pass:
                {error_file_content}\n  
                
                \nContent of the imports used in the test file:
                {imported_file_contents}\n  

                The new file should respect the linting rules: {ESLINT}
                
                Please ensure the following:
                    Fix the Tests: 
                        Resolve all errors to ensure that the tests pass successfully in the new framework.
                    
                    Preserve Structure: 
                        Maintain the original structure and organization of the file, including:
                            Abstracted functions
                            describe and it blocks
                    
                    Do Not Modify Unrelated Code: 
                        Only modify the code necessary for the migration to ensure compatibility with the new framework.
                    
                    Do Not Include:
                        VERY IMPORTANT: Do not include any code tags (such as ```) Code tags (such as ```)
                        Comments or explanations in the returned code
                    
                    Output: 
                        Return only the fully migrated and functional test file. The file should be ready to execute with all tests passing in the new framework.
            """
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content

REQUIRED_ENZYME_IMPORTS = ""
REQUIRED_RTL_IMPORTS = """These are the common imports for react-testing-library: 
    import {render, fireEvent, screen} from '@testing-library/react'
    import userEvent from '@testing-library/user-event'
    """



def request_import_update(migrated_file, imports, framework_conversion_info, common_imports):
    message = f"""You are tasked with migrating the following test file from {framework_conversion_info['original']} to {framework_conversion_info['new']}:
                Your first task is to update the imports to work with {framework_conversion_info['new']} 
                For reference, this is the file that was migrated: {migrated_file}
                You should adjust the imports to match this file.
                Be sure to include only the required imports for this specific file.

                \nThese are the current imports to be modified:
                {imports}\n  

                Only modify the imports. Do not modify other areas of the code.

                These imports are commonly used for {framework_conversion_info['new']}: {common_imports}
                
                Please ensure the following:
                Preserve Structure: 
                    Maintain the original structure and organization of the file, including:
                        Abstracted functions
                
                \nDo Not Modify Unrelated Code: Only modify the inputs necessary for the migration to ensure compatibility with the new framework.\n
                
                \nDo Not Include:
                VERY IMPORTANT: Do not include any code tags (such as ```)
                Comments or explanations in the returned code
                
                \nOutput: Return only the migrated imports.
            """
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content


def generate_package_updates(history, package_json_file, error_file_content, new_testing_framework):
    prompt = build_package_update_prompt(package_json_file, error_file_content, history, new_testing_framework)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "assistant", "content": f"Previously added packages: {history}"},
                  {"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def extract_import_paths(file_content):
    es6_import_pattern = re.compile(r"import\s+.*\s+from\s+['\"](.*?)['\"];?")
    require_pattern = re.compile(r"const\s+\S+\s*=\s*require\s*\(\s*['\"](.*?)['\"]\s*\);?")
    
    import_paths = []

    for line in file_content.splitlines():
        if es6_match := es6_import_pattern.search(line):
            import_paths.append(es6_match.group(1))
        if require_match := require_pattern.search(line):
            import_paths.append(require_match.group(1))
    
    return import_paths


def search_and_load_import_content(import_path, base_dir):
    # Handle package imports vs relative imports
    if not import_path.startswith(('.', '/')):
        # This is likely a package import from node_modules, we skip reading it
        print(f"Skipping package import: {import_path}")
        return None

    # Handle the case where the import path is '..' by appending '/index'
    if import_path == '..':
        import_path = '../index'
    
    # Resolve the relative path based on the base directory of the file
    absolute_base = Path(base_dir).parent
    resolved_path = (absolute_base / Path(import_path)).resolve()

    # Search for the file with potential extensions (.js, .py, .jsx, etc.)
    possible_extensions = ['', '.js', '.jsx', '.ts', '.tsx']

    # Try appending each possible extension to the resolved path
    for ext in possible_extensions:
        # Append new extension to existing suffix
        file_path = resolved_path.with_name(resolved_path.name + ext)  
        try:
            if file_path.exists():
                return read_file(file_path)
        except IsADirectoryError:
            print(f"Error: {file_path} is a directory, not a file.")
            return None

    print(f"File not found for import: {import_path}, looked in: {resolved_path}")
    return None


def list_new_packages(original_file, updated_file):
    prompt = f"List all of the new imports that you added to this file. Separate each package with a comma. Only respond with the package names."
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "assistant", "content": original_file},
            {"role": "assistant", "content": updated_file},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.split(',')


def find_test_files(repo_path):
    full_path = os.path.join(ABSOLUTE_PATH, repo_path)
    test_files = []

    for root, dirs, files in os.walk(full_path):
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.github', '__snapshots__')]
        
        test_files += [os.path.join(root, file) for file in files 
                       if file.endswith(('.test.js', '.spec.js')) and "snapshot" not in file]

    return test_files


def update_file_name_with_migrated(file_path):
    directory, filename = os.path.split(file_path)
    name_parts = filename.split('.', 1)
    
    if "migrated" in file_path:
        return file_path
    
    new_filename = f"{name_parts[0]}-migrated.{name_parts[1]}" if len(name_parts) > 1 else f"{name_parts[0]}-migrated"
    
    return os.path.join(directory, new_filename)

def remove_code_tags_from_string(text):
    lines = text.splitlines()

    # Remove the first and last line if they contain code tags
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    # Join the lines back into a single string
    return "\n".join(lines)

def split_file_to_strings(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    imports = []
    describe_blocks = []
    in_imports = True

    for line in lines:
        if in_imports:
            if line.startswith("describe('") or line.startswith("describe("):
                in_imports = False
                describe_blocks.append(line)
            else:
                imports.append(line)
        else:
            describe_blocks.append(line)

    imports_section = ''.join(imports)
    describe_section = ''.join(describe_blocks)

    return imports_section, describe_section

def convert_blocks_to_file(blocks):
    """
    Converts the imports and blocks back into a single string for a file.
    
    Parameters:
    - blocks: list of code blocks (either describe or test blocks)
    
    Returns:
    - A string that represents the content of the file.
    """
    # Add each block, separated by a new line
    file_content = ""
    for block in reversed(blocks):
        file_content += block + "\n\n"  # Ensure each block is separated by two newlines

    return file_content

def remove_duplicate_imports(input_string):
    lines = input_string.splitlines()
    
    import_dict = {}
    other_lines = []
    current_import = []
    inside_multiline_import = False

    for line in lines:
        # Detect the start of a multiline import
        if line.startswith('import') and '{' in line and '}' not in line:
            inside_multiline_import = True
            current_import.append(line)
        elif inside_multiline_import:
            # Continue collecting the lines for multiline imports
            current_import.append(line)
            if '}' in line:
                full_import = '\n'.join(current_import)
                import_part = current_import[0].split('from')[0].strip()
                if import_part not in import_dict:
                    import_dict[import_part] = full_import
                current_import = []
                inside_multiline_import = False
        elif line.startswith('import') and not inside_multiline_import:
            # Single-line import
            import_part = line.split('from')[0].strip()
            if import_part not in import_dict:
                import_dict[import_part] = line
        else:
            other_lines.append(line)

    # Combine unique imports and other lines back into a string
    unique_imports = sorted(import_dict.values())
    output_string = '\n'.join(unique_imports + other_lines)
    
    return output_string

def main():
    for repo in repos[3:]:
        migrated_test_files = 0
        test_files = find_test_files(repo)
        new_packages = set()

        full_repo_path = os.path.join(ABSOLUTE_PATH, repo)
        error_file_content = os.path.join(full_repo_path, 'test_suite_results.txt')

        print(f"Found {len(test_files)} test files")                         
        for test_file in test_files:
            original_content = read_file(test_file)
            import_paths = extract_import_paths(original_content)
            print("Import paths: ", import_paths)

            framework_conversion_info = {'original': 'enzyme', 'new': '@testing-library/react'}
            if framework_conversion_info['original'] not in import_paths and framework_conversion_info['new'] not in import_paths: 
                # Either it was already migrated or it doesn't use a DOM testing library
                print("Doesn't contain required testing library")
                continue

            print("Found a testing library, continuing")
            
            imported_file_contents = [search_and_load_import_content(path, test_file) for path in import_paths]
            updated_content = []
            print("Splitting the test file")
            imports, describe = split_file_to_strings(test_file)
            # print("Imports: ", imports)
            # print("\n\n\nDescribe: ", describe)

            # TODO: Think of better way to handle this...
            # If we don't have a describe block then the test file doesn't contain any describe statements
            # In this case we just pass the entire file to be migrated (until we can come up with a better splitting method)
            if imports and describe:        
                updated_content_pre_fix = request_code_update(describe, framework_conversion_info, imported_file_contents, error_file_content)
                # Attempt to remove any code tags from beginning and end of the file
                updated_content.append(remove_code_tags_from_string(updated_content_pre_fix))

                # Pass in the imports -> perform the updates
                updated_imports_pre_fix = request_import_update(updated_content[0], imports, framework_conversion_info, REQUIRED_RTL_IMPORTS)
                # print("\n\nupdated_imports_pre_fix: ", updated_imports_pre_fix)
                updated_imports_after_fix = remove_code_tags_from_string(updated_imports_pre_fix)
                # print("\n\nupdated_imports_after_fix: ", updated_imports_after_fix)
                updated_content.append(updated_imports_after_fix)

                updated_content[1] = remove_duplicate_imports(updated_content[1])
                # Convert the blocks back into a proper file
                updated_file = convert_blocks_to_file(updated_content)
            else:
                print("Requesting full file update")
                updated_file_pre_fix = request_full_file_update(original_content, framework_conversion_info, imported_file_contents, error_file_content)
                updated_file = remove_code_tags_from_string(updated_file_pre_fix)

            print("\n\nupdated_file: ", updated_file)

            updated_file = remove_code_tags_from_string(updated_file)

            # Overwriting the file now instead of adding -migrated
            # output_file = update_file_name_with_migrated(test_file)
            write_file(test_file, updated_file)
            new_packages.update(list_new_packages(original_content, updated_file))
            migrated_test_files += 1
        
        package_json_file = os.path.join(ABSOLUTE_PATH, repo, 'package.json')
        package_content = read_file(package_json_file)
        
        modified_package_json_pre_fix = generate_package_updates(new_packages, package_content, "test_suite_results.txt", framework_conversion_info['new'])
        modified_package_json = remove_code_tags_from_string(modified_package_json_pre_fix)
        
        write_file(package_json_file, modified_package_json)

        print(f"\n\nMigrated {migrated_test_files}\n\n")

        print(f"\nRe-running test suite for {repo}\n")
        verify_tests_can_run(ABSOLUTE_PATH, repo, 0, ENZYME_REPOS_WITH_RUNNING_TESTS_USING_CONTEXT_AND_ERRORS_PATH, True, False, migrated_test_files)

# python -m JavaScriptTestMigration.scripts.migrate_test_files_with_context_and_errors
# TODO: Make a script to store all the test files at a timestamp to the repo.
# TODO: Make a script that can restore the repository to a given timestamp 
if __name__ == '__main__':
    main()
