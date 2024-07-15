from openai import OpenAI
import subprocess
import constants
client = OpenAI(api_key=constants.OPENAI_API_KEY)
import os

# Set up your OpenAI API key

def read_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content

def write_file(file_path, content):
    with open(file_path, 'w') as file:
        file.write(content)

def make_changes_to_content(content):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content":f"Here is a text file content:\n\n{content}\n\nPlease perform the following tasks:\
                1. Complete the conversion for the test file.\
                2. Convert all test cases and ensure the same number of tests in the file\
                3. Replace React Testing Library methods with the equivalent Enzyme methods.\
                4. Update React Testing Library imports to Enzyme imports.\
                5. Adjust React Testing Library matchers for Enzyme.\
                6. Return the entire file with all converted test cases.\
                7. Do not modify anything else, including imports for React components and helpers.\
                8. Preserve all abstracted functions as they are and use them in the converted file.\
                9. Maintain the original organization and naming of describe and it blocks."
            }
        ],
    )
    print(response.choices[0])
    return response.choices[0].message.content

def main():
    input_file_path = 'react-beautiful-dnd/test/unit/integration/draggable/dragging.spec.js'  # Path to the input file
    output_file_path = 'react-beautiful-dnd/test/unit/integration/draggable/dragging-migrated.spec.js'  # Path to the output file
    working_directory = 'react-beautiful-dnd/'
    # Read the content from the input file
    content = read_file(input_file_path)

    # Make changes to the content using OpenAI API
    modified_content = make_changes_to_content(content)

    # Write the modified content to the output file
    write_file(output_file_path, modified_content)

    print(f"Modified content has been written to {output_file_path}")

    result = subprocess.run(["yarn test /test/unit/integration/draggable/dragging-migrated.spec.js"], cwd=working_directory, shell=True)


if __name__ == "__main__":
    main()
