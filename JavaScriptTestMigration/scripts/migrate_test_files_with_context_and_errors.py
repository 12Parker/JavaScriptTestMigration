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
                
                Please ensure the following:
                IMPORTANT: Remove any duplicate or repeated imports
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


def request_import_update(content, framework_conversion_info):
    message = f"""You are tasked with migrating the following test file from {framework_conversion_info['original']} to {framework_conversion_info['new']}:
                Your first task is to update the imports to work with {framework_conversion_info['new']} 
                Do not perform an update if {framework_conversion_info['new']} already exists in the file.
                Remove any duplicate imports.
                \nThese are the imports to be modified:
                {content}\n  
                
                Please ensure the following:
                Preserve Structure: 
                    Maintain the original structure and organization of the file, including:
                        Abstracted functions
                
                \nDo Not Modify Unrelated Code: Only modify the code necessary for the migration to ensure compatibility with the new framework.\n
                
                \nDo Not Include:
                VERY IMPORTANT: Do not include any code tags (such as ```)
                Comments or explanations in the returned code
                
                \nOutput: Return only the fully migrated and functional test file. The file should be ready to execute.
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
    full_path = os.path.join(REPO_DIR, repo_path)
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

def split_test_file(file_content):
    # Regular expressions for detecting different sections
    import_pattern = r"^(const|import).+$"
    describe_pattern = r"^describe\(.*$"
    function_pattern = r"^(beforeEach|afterEach|function|it).*$"
    
    imports = []
    describe_blocks = []
    
    current_block = 'imports'  # Start with imports by default
    describe_block = []
    bracket_count = 0
    is_inside_describe = False

    for line in file_content.splitlines():
        stripped_line = line.strip()
        
        # Handle the import section
        if current_block == 'imports' and re.match(import_pattern, stripped_line):
            imports.append(line)
            continue
        
        # Detect the beginning of a top-level describe block
        if re.match(describe_pattern, stripped_line) and not is_inside_describe:
            if current_block == 'imports':
                current_block = 'describe'  # Transition from imports to describe blocks
            is_inside_describe = True  # Mark that we are inside a describe block
            bracket_count = 1  # Start counting brackets
            describe_block.append(line)
            continue

        # If we're inside a describe block, handle it
        if is_inside_describe:
            # Count opening and closing brackets to detect when we exit a describe block
            bracket_count += line.count("{")
            bracket_count -= line.count("}")
            describe_block.append(line)
            
            # If bracket count returns to 0, we've closed a top-level describe block
            if bracket_count == 0:
                describe_blocks.append("\n".join(describe_block))
                describe_block = []
                is_inside_describe = False  # Reset flag to indicate we've exited the block
    
    return imports, describe_blocks

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
    for block in blocks:
        file_content += block + "\n\n"  # Ensure each block is separated by two newlines

    return file_content

def remove_duplicate_imports(file_content):
    # Regular expression to match import statements
    import_pattern = re.compile(r"import\s+((?:\*\s+as\s+\w+)|(?:\{[^}]+\})|(?:[^'{}]+))\s+from\s+['\"]([^'\"]+)['\"];?")
    
    import_dict = defaultdict(list)
    output_lines = []

    # Split file content into lines
    lines = file_content.splitlines()

    # Collect imports and other lines separately
    for line in lines:
        match = import_pattern.match(line.strip())
        if match:
            import_spec = match.group(1).strip()
            import_source = match.group(2).strip()
            
            # If it's not a wildcard or default import, split into named imports
            if import_spec.startswith("{"):
                named_imports = [imp.strip() for imp in import_spec.strip("{}").split(",")]
                import_dict[import_source].extend(named_imports)
            else:
                # For wildcard or default imports, store them directly
                import_dict[import_source].append(import_spec)
        else:
            # Non-import lines are kept as they are
            output_lines.append(line)

    # Combine the imports back into valid import statements
    unique_imports = []
    for source, imports in import_dict.items():
        # Get unique imports for the source
        unique_imports_set = sorted(set(imports))
        
        # Handle wildcard/default imports and named imports separately
        default_or_wildcard_imports = [imp for imp in unique_imports_set if not re.match(r"\w+\s+as\s+", imp) and not re.match(r"\{", imp)]
        named_imports = [imp for imp in unique_imports_set if not imp in default_or_wildcard_imports]
        
        if default_or_wildcard_imports:
            unique_imports.append(f"import {default_or_wildcard_imports[0]} from '{source}';")
        if named_imports:
            unique_imports.append(f"import {{ {', '.join(named_imports)} }} from '{source}';")

    # Combine the unique imports with the rest of the code
    file_content_cleaned = "\n".join(unique_imports + output_lines)

    return file_content_cleaned

def main():
    for repo in repos[1:2]:
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

            print("Splitting the test file")
            imports, describe_blocks = split_test_file(original_content)
            updated_content = []
            updated_file = ''
            # print("imports: ", imports)
            # print("describe_blocks: ", describe_blocks)


            # TODO: Think of better way to handle this...
            # If we don't have a describe block then the test file doesn't contain any describe statements
            # In this case we just pass the entire file to be migrated (until we can come up with a better splitting method)
            if imports and describe_blocks:
                if framework_conversion_info['new'] not in imports: 
                    # First pass in the imports -> perform the updates
                    updated_imports_pre_fix = request_import_update(imports[0], framework_conversion_info)
                    updated_content.append(remove_code_tags_from_string(updated_imports_pre_fix))
                else:
                    updated_content.append(imports[0])
          
                # Next pass in each describe block -> Save the output
                for idx, block in enumerate(describe_blocks):
                    print(f"Processing block {idx}")

                    updated_content_pre_fix = request_code_update(block, framework_conversion_info, imported_file_contents, error_file_content)
                    # Attempt to remove any code tags from beginning and end of the file
                    updated_content.append(remove_code_tags_from_string(updated_content_pre_fix))
                
                # Convert the blocks back into a proper file
                updated_file = convert_blocks_to_file(updated_content)
            else:
                print("Requesting full file update")
                updated_file_pre_fix = request_full_file_update(original_content, framework_conversion_info, imported_file_contents, error_file_content)
                updated_file = remove_code_tags_from_string(updated_file_pre_fix)

            print("updated_file: ", updated_file)

            removed_duplicate_imports = remove_duplicate_imports(updated_file)
            updated_file = remove_code_tags_from_string(removed_duplicate_imports)

            # Overwriting the file now instead of adding -migrated
            # output_file = update_file_name_with_migrated(test_file)
            write_file(test_file, updated_file)
            new_packages.update(list_new_packages(original_content, updated_file))
            migrated_test_files += 1
        
        package_json_file = os.path.join(REPO_DIR, repo, 'package.json')
        package_content = read_file(package_json_file)
        
        modified_package_json_pre_fix = generate_package_updates(new_packages, package_content, "test_suite_results.txt", framework_conversion_info['new'])
        modified_package_json = remove_code_tags_from_string(modified_package_json_pre_fix)
        
        write_file(package_json_file, modified_package_json)

        print(f"\n\nMigrated {migrated_test_files}\n\n")

        print(f"\nRe-running test suite for {repo}\n")
        verify_tests_can_run(repo, 0, ENZYME_REPOS_WITH_RUNNING_TESTS_USING_CONTEXT_AND_ERRORS_PATH, True, False)

# python -m JavaScriptTestMigration.scripts.migrate_test_files_with_context_and_errors
# TODO: Make a script to store all the test files at a timestamp to the repo.
# TODO: Make a script that can restore the repository to a given timestamp 
if __name__ == '__main__':
    main()
