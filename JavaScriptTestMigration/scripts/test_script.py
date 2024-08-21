import re

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


# Specify the correct file path
file_path = '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repositories/math-input/test/test_context-tracking_spec.js'

# Read the test file content
with open(file_path, 'r') as file:
    file_content = file.read()

# Split the content into blocks
imports, describe_blocks = split_test_file(file_content)

# Output the blocks
print("Imports:")
print("\n".join(imports))
print("\nDescribe Blocks:")
for idx, block in enumerate(describe_blocks):
    print(f"\nDescribe Block {idx + 1}:")
    print(block)
    print("\n---\n")
