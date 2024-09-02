from openai import OpenAI
import subprocess
from ..constants import *
from ..repo_names.enzyme.enzyme_repos_with_running_tests import repos
# from ..repo_names.rtl.rtl_repos_with_running_tests import repos
from ..utils.utils import verify_tests_can_run
import os
import argparse

# Set up your OpenAI API key
client = OpenAI(api_key=OPENAI_API_KEY)

def RTL_TO_ENZYME_PROMPT(package_json_file): 
    return f"Update the package.json file to include 'enzyme' the approriate enzyme-react-adapter package. \
                If the React version in package.json is 17 use '@wojtekmaj/enzyme-adapter-react-17'. \
                If the React version in package.json is 16 use 'enzyme-adapter-react-16'. \
                If the React version in package.json is 15 use 'enzyme-adapter-react-15'. \
                If the React version in package.json is 14 use 'enzyme-adapter-react-14'. \
                If the React version in package.json is 13 use 'enzyme-adapter-react-13'. \
                Also include 'react-dom' if it is not present. \
                Here is the package.json file: {package_json_file}.\
                Do not include code tags or any comments. Return only the updated file"

def ENZYME_TO_RTL_PROMPT(package_json_file):
    return f"Update the package.json file to include '@testing-library/react' and '@testing-library/jest-dom'. \
                Also include '@testing-library/user-event'. \
                Here is the package.json file: {package_json_file}.\
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

def make_changes_to_package(history, package_json_file, original_test_framework, new_test_framework):
    print("History: ", history)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "assistant", "content": f"Previously added packages: {history}"},
            {"role": "user", "content": ENZYME_TO_RTL_PROMPT(package_json_file)
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
    full_path = os.path.join(ABSOLUTE_PATH,repo_path)

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
def main():
    start = 0

    for repo in repos[start:]:
        migrated_test_files = 0
        files = find_test_files(repo)
        is_Yarn_repo = False
        full_repo_path = os.path.join(ABSOLUTE_PATH, repo)
        if os.path.exists(os.path.join(full_repo_path, 'yarn.lock')):
            is_Yarn_repo = True
        new_packages = set()

        print("Found test files: ", len(files))
        for file in files:
            input_file_path = file  # Path to the input file
            output_file_path = file  # Path to the output file
            # Read the content from the input file
            full_file_name = f"{input_file_path}"
            print("COMPARE: ", input_file_path, "\nvs: ", full_file_name)
            content = read_file(full_file_name)

            # Add a check here for the import statements (try to ignore testing specific imports)
            framework_conversion_info = {'original': 'enzyme', 'new': '@testing-library/react'}
            if framework_conversion_info['original'] not in content and framework_conversion_info['new'] not in content: 
                # Either it was already migrated or it doesn't use a DOM testing library
                print("Doesn't contain required testing library")
                continue

            # Make changes to the content using OpenAI API
            modified_content = make_changes_to_content(content, framework_conversion_info['original'], framework_conversion_info['new'])

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
            migrated_test_files += 1

        try:
            if is_Yarn_repo:
                res = subprocess.run(
                    ['yarn', 'add', '--dev', '@testing-library/react', '@testing-library/jest-dom'],
                    cwd=full_repo_path,
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=GLOBAL_TIMEOUT
                )

            else:
                res = subprocess.run(
                    ['npm', 'install', '--save-dev', '@testing-library/react', '@testing-library/jest-dom'],
                    cwd=full_repo_path,
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=GLOBAL_TIMEOUT
                )

        except Exception as e:
            print("There was an error while adding new packages: ", e)
            break

        # package_json_file_path = ABSOLUTE_PATH + repo + '/package.json'
        # package_json_file = read_file(package_json_file_path) 
        # modified_package_json = make_changes_to_package(new_packages, package_json_file, 'enzyme', '@testing-library/react')
        # write_file(package_json_file_path, modified_package_json)
        #Re-run the test suite and save the results
        print("\nRe-running the test suite after migration\n")
        try:
            verify_tests_can_run(ABSOLUTE_PATH, repo, 0, ENZYME_REPOS_WITH_RUNNING_TESTS_ZERO_SHOT_PATH, True, False, migrated_test_files)
        except Exception as e:
            print(f"Encountered exception {e}, for repo {repo}")

        # Add one more check where we pass in the test_suite_results file and attempt to fix the errors
        # test_suite_results_path = os.path.join(full_repo_path, 'test_suite_results.txt')
        # We can probably do this recursively? -> Set it up to go 1-3 levels deep and see if there are any improvements?

# Ex. python -m JavaScriptTestMigration.scripts.migrate_test_files --repo react-native-label-select
if __name__ == '__main__':
    main()


# TODO: add docs as context: https://testing-library.com/docs/react-testing-library/migrate-from-enzyme/
# TODO: add imports as context
# TODO: generate DOM and add as context 
