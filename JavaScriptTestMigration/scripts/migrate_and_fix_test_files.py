from openai import OpenAI
import subprocess
from ..constants import *
from ..repo_names.enzyme_repos_with_running_tests import repos
# from ..repo_names.rtl_repos_with_running_tests import repos
from ..utils.utils import verify_tests_can_run
import os
import argparse

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

def make_changes_to_content(content, original_test_framework, new_test_framework, error_file_content):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content":f"Here is a test file that was previously migrated from {original_test_framework} to {new_test_framework}:\n\n{content}\n\n \
                There are errors that need to be fixed for the tests to pass: {error_file_content} \
                Using the errors as context you must fix the file to ensure all tests are passing. \
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
    full_path = ABSOLUTE_PATH + repo_path
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

# TODO: Update the params to accept a list of repo's or make new method to handle single migration 
def main(repo_name):
    start = 5
    for repo in repos[start:]:
        files = find_test_files(repo)
        new_packages = set()

        full_repo_path = os.path.join(ABSOLUTE_PATH, repo_name)
        error_file_content = os.path.join(full_repo_path, 'test_suite_results.txt')

        print("Found test files: ", len(files))
        for file in files:
            input_file_path = file  # Path to the input file
            output_file_path = add_migrated_to_filename(file)  # Path to the output file
            # Read the content from the input file
            full_file_name = f"{input_file_path}"
            content = read_file(full_file_name)

            # Make changes to the content using OpenAI API
            modified_content = make_changes_to_content(content, 'enzyme', '@testing-library/react', error_file_content)

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

        package_json_file_path = ABSOLUTE_PATH + repo + '/package.json'
        package_json_file = read_file(package_json_file_path) 
        
        modified_package_json = make_changes_to_package(new_packages, package_json_file, 'enzyme', '@testing-library/react', error_file_content)
        write_file(package_json_file_path, modified_package_json)
        
        #Re-run the test suite and save the results
        print("\nRe-running the test suite after attempting to fix errors\n")
        try:
            verify_tests_can_run(ABSOLUTE_PATH, repo, 0, ENZYME_REPOS_WITH_RUNNING_TESTS_AFTER_FIX_PATH, True, True)
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
