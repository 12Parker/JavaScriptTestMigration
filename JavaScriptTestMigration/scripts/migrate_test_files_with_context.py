import os
import re
import argparse
from pathlib import Path
import subprocess
from openai import OpenAI
from ..constants import *
from ..repo_names.enzyme_repos_with_running_tests import repos
from ..utils.utils import verify_tests_can_run

# Set up your OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)


def build_package_update_prompt(package_json_file, error_file_content, history):
    return f"""Here is a package.json file: {package_json_file}.
            These dependencies were added previously: {history}

            Using this error message as context: {error_file_content}
            Determine if the package.json file needs to be updated. 
            If the file needs to be updated, you should only update the previously added dependencies.
            Do not include code tags or any comments. Return only the updated file."""


def read_file(file_path):
    print(f"Reading file: {file_path}")
    with open(file_path, 'r') as file:
        return file.read()


def write_file(file_path, content):
    print(f"Writing to file: {file_path}")
    with open(file_path, 'w') as file:
        file.write(content)


def request_code_update(content, framework_conversion_info, imported_file_contents):
    message = f"""Here is a test file that was previously migrated from {framework_conversion_info['original']} to {framework_conversion_info['new']}:
                {content}

                This is the content of each import statement at the top of the test file: {imported_file_contents}

                Using this context, you must fix the file to ensure all tests are passing.
                Preserve all abstracted functions, original organization, and naming of describe/it blocks.
                VERY IMPORTANT: Do not include code tags or any comments. Return only the updated file."""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content


def generate_package_updates(history, package_json_file, error_file_content):
    prompt = build_package_update_prompt(package_json_file, error_file_content, history)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
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
        file_path = resolved_path.with_suffix(ext)
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
        model="gpt-4o-mini",
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

def main():
    for repo in repos[13:]:
        test_files = find_test_files(repo)
        new_packages = set()

        print(f"Found {len(test_files)} test files")
        for test_file in test_files:
            original_content = read_file(test_file)
            import_paths = extract_import_paths(original_content)
            print("Import paths: ", import_paths)
            
            imported_file_contents = [search_and_load_import_content(path, test_file) for path in import_paths]

            framework_conversion_info = {'original': 'enzyme', 'new': '@testing-library/react'}
            updated_content = request_code_update(original_content, framework_conversion_info, imported_file_contents)

            # Attempt to remove any code tags from beginning and end of the file
            updated_content = remove_code_tags_from_string(updated_content)

            output_file = update_file_name_with_migrated(test_file)
            write_file(output_file, updated_content)

            new_packages.update(list_new_packages(original_content, updated_content))
        
        package_json_file = os.path.join(REPO_DIR, repo, 'package.json')
        package_content = read_file(package_json_file)
        modified_package_json = generate_package_updates(new_packages, package_content, "test_suite_results.txt")
        write_file(package_json_file, modified_package_json)

        print(f"\nRe-running test suite for {repo}\n")
        verify_tests_can_run(repo, 0, ENZYME_REPOS_WITH_RUNNING_TESTS_USING_CONTEXT_PATH, True, True)


if __name__ == '__main__':
    main()
