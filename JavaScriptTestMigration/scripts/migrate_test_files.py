from openai import OpenAI
import subprocess
import constants
import os
import argparse

# Set up your OpenAI API key
client = OpenAI(api_key=constants.OPENAI_API_KEY)

def read_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content

def write_file(file_path, content):
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
                10. Do not include code tags or any comments. Return only the updated file"
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
            {"role": "user", "content":f"Update the package.json file to include all new packages listed previously. Here is the package.json file: {package_json_file}.\
            Do not include code tags or any comments. Return only the updated file"
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
    test_files = []
    for root, dirs, files in os.walk(repo_path):
        # Skip node_modules directory
        dirs[:] = [d for d in dirs if d != 'node_modules']
        
        for file in files:
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

def main(repo):
    files = find_test_files(repo)
    new_packages = set()

    for file in files[:2]:
        input_file_path = file  # Path to the input file
        output_file_path = add_migrated_to_filename(file)  # Path to the output file
        # Read the content from the input file
        full_file_name = f"{input_file_path}"
        content = read_file(full_file_name)

        # Make changes to the content using OpenAI API
        modified_content = make_changes_to_content(content, 'Enzyme', 'React Testing Library')

        # Write the modified content to the output file
        write_file(output_file_path, modified_content)

        print(f"Modified content has been written to {output_file_path}")
        new_packages_list = list_new_packages(content, modified_content)
        # Split the comma-separated list and strip any surrounding whitespace from each item
        items = [item.strip() for item in new_packages_list.split(',')]
        
        # Add each item to the set
        for item in items:
            new_packages.add(item)

    package_json_file_path = repo + '/package.json'
    package_json_file = read_file(package_json_file_path) 
    modified_package_json = make_changes_to_package(new_packages, package_json_file, 'Enzyme', 'React Testing Library')
    write_file(repo + '/package-updated.json', modified_package_json)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test your repo')
    parser.add_argument('--repo', metavar='path', required=True,
                        help='the repo name you want to test')
    args = parser.parse_args()
    main(repo=args.repo)

