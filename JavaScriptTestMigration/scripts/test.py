from openai import OpenAI
import subprocess
from ..constants import *
from ..repo_names.enzyme_repos_with_running_tests import repos
# from ..repo_names.rtl_repos_with_running_tests import repos
from ..utils.utils import verify_tests_can_run
import os
import argparse
import re
from pathlib import Path


# Set up your OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)

def PACKAGE_UPDATE_PROMPT(package_json_file, error_file_content, history):
    return f"Here is a package.json file: {package_json_file}.\n\
            These dependencies were added previously: {history}\n\n \
            Using this error message as context: {error_file_content}\n\n \
            Determine if the package.json file needs to be updated. \
            If the file needs to be updated, you should only update the previously added dependencies.\
            Do not include code tags or any comments. Return only the updated file"

def read_file(file_path):
    print("FILE: ", file_path)
    with open(file_path, 'r') as file:
        content = file.read()
    return content

def write_file(file_path, content):
    print("WRITE TO FILE: ", file_path)
    with open(file_path, 'w') as file:
        file.write(content)

def make_changes_to_content(content, original_test_framework, new_test_framework, imported_file_contents):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content":f"Here is a test file that was previously migrated from {original_test_framework} to {new_test_framework}:\n\n{content}\n\n \
                This is the content of each import statement at the top of the test file: {imported_file_contents} \
                Using this content as context you must fix the file to ensure all tests are passing. \
                You must ensure to: \
                1. Return the entire file with all converted test cases.\
                2. Do not modify anything else, including imports for React components and helpers.\
                3. Preserve all abstracted functions as they are and use them in the converted file.\
                4. Maintain the original organization and naming of describe and it blocks.\
                5. VERY IMPORTANT: Do not include code tags or any comments. Return only the updated file"
            }
        ],
    )
    return response.choices[0].message.content

def make_changes_to_package(history, package_json_file, original_test_framework, new_test_framework, error_file_content):
    print("History: ", history)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "assistant", "content": f"Previously added packages: {history}"},
            {"role": "user", "content": PACKAGE_UPDATE_PROMPT(package_json_file, error_file_content, history)
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
    full_path = REPO_DIR + repo_path
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
    if lines[0].startswith("
"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "
":
        lines = lines[:-1]

    # Join the lines back into a single string
    return "\n".join(lines)

def extract_import_paths(js_file_path):
    import_paths = []
    
    # Define regular expression patterns to match ES6-style, Python-style, and require() import statements
    es6_import_pattern = re.compile(r"import\s+.*\s+from\s+['\"](.*?)['\"];?")
    python_import_pattern = re.compile(r"from\s+(\S+)\s+import\s+.*")
    require_pattern = re.compile(r"const\s+\S+\s*=\s*require\s*\(\s*['\"](.*?)['\"]\s*\);?")
    
    try:
        with open(js_file_path, 'r', encoding='utf-8') as file:
            for line in file:
                # Match ES6-style import statements
                es6_match = es6_import_pattern.search(line)
                if es6_match:
                    import_paths.append(es6_match.group(1))
                
                # Match Python-style import statements
                python_match = python_import_pattern.search(line)
                if python_match:
                    import_paths.append(python_match.group(1))
                
                # Match require() statements
                require_match = require_pattern.search(line)
                if require_match:
                    import_paths.append(require_match.group(1))
        
        return import_paths
    
    except FileNotFoundError:
        print(f"The file {js_file_path} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

def search_and_read_file(import_path, base_dir):
    # Absolute path
    absolute_path = Path("/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repositories/pixivdeck/app/components/Loading/tests/Rect.test.js")

    # Relative path
    relative_path = Path("../Rect")

    # Combine and resolve the path
    resolved_path = str((absolute_path.parent / relative_path).resolve())
    print("RESOLVED: ", resolved_path)
    
    # Search for the file with potential extensions (.js, .py, .jsx, etc.)
    possible_extensions = ['', '.js', '.py', '.jsx', '.ts', '.tsx']
    
    for ext in possible_extensions:
        file_path = resolved_path + ext
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.readlines()  # Return file contents as a list of lines
            except Exception as e:
                print(f"An error occurred while reading {file_path}: {e}")
    
    print(f"File not found for import: {import_path}")
    return None

# TODO: Update the params to accept a list of repo's or make new method to handle single migration 
def main(repo_name):
    start = 0
    for repo in repos[start:]:
        files = find_test_files(repo)
        new_packages = set()

        full_repo_path = os.path.join(ABSOLUTE_PATH, repo_name)
        error_file_content = os.path.join(full_repo_path, 'test_suite_results.txt')

        print("Found test files: ", len(files))
        for file in files[:1]:
            input_file_path = file  # Path to the input file
            output_file_path = add_migrated_to_filename(file)  # Path to the output file
            # Read the content from the input file
            full_file_name = f"{input_file_path}"
            content = read_file(full_file_name)

            # Extract the import paths
            import_paths = extract_import_paths(full_file_name)

            # Array to store the contents of the imported files
            imported_file_contents = []
            print("Import paths: ", import_paths, input_file_path)
            # For each import path, search for the file and read its content
            for path in import_paths:
                file_content = search_and_read_file(path, input_file_path)
                if file_content:
                    imported_file_contents.append(file_content)

            print("Contents of imports: ", imported_file_contents)
            # Make changes to the content using OpenAI API
            modified_content = make_changes_to_content(content, 'enzyme', '@testing-library/react', imported_file_contents)

            # Attempt to remove any code tags from beginning and end of the file
            modified_content = remove_code_tags_from_string(modified_content)

            # Write the modified content to the output file
            write_file(output_file_path, modified_content)

            print(f"Modified content has been written to {output_file_path}")
            new_packages_list = list_new_packages(content, modified_content)
            # Split the comma-separated list and strip any surrounding whitespace from each item
            items = [item.strip() for item in new_packages_list.split(',')]
            
            # Add each item to the set
            for item in items:
                new_packages.add(item)

        package_json_file_path = REPO_DIR + repo + '/package.json'
        package_json_file = read_file(package_json_file_path) 
        
        modified_package_json = make_changes_to_package(new_packages, package_json_file, 'enzyme', '@testing-library/react', error_file_content)
        write_file(package_json_file_path, modified_package_json)
        
        #Re-run the test suite and save the results
        print("\nRe-running the test suite after migrating with context\n")
        try:
            verify_tests_can_run(repo, 0, ENZYME_REPOS_WITH_RUNNING_TESTS_USING_CONTEXT_PATH, True, True)
        except Exception as e:
            print(f"Encountered exception {e}, for repo {repo}")

# Ex. python -m JavaScriptTestMigration.scripts.migrate_and_fix_test_files --repo react-native-label-select
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test your repo')
    parser.add_argument('--repo', metavar='path', required=True,
                        help='the repo name you want to test')
    args = parser.parse_args()
    main(repo_name=args.repo)


# TODO: add docs as context: https://testing-library.com/docs/react-testing-library/migrate-from-enzyme/
# TODO: add imports as context
# TODO: generate DOM and add as context 