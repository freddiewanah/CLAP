import os
import subprocess

import unittest
import sys
import ast
def run_unittest(test_case_name, test_function_name):
    # Load the test case from the other project
    sys.path.append('/path/to/other/project')
    module = __import__(test_case_name)
    test_case = getattr(module, test_case_name)

    # Create a TestSuite containing just the specified test function
    test_suite = unittest.TestSuite()
    test = test_case(test_function_name)
    test_suite.addTest(test)

    # Run the test and return the result
    result = unittest.TextTestRunner().run(test_suite)
    if result.wasSuccessful():
        return None
    else:
        return result.errors[0][1]

projectFolder = ""


command = ""

def save_temp_file(tarFile, newCode, testFuncName):
    tarFilePath = find_file_within_folder(projectFolder, tarFile)
    print("tar file path: " + tarFilePath)
    # Read the contents of file_a.py
    with open(tarFilePath, 'r') as f:
        code = f.read()

    try:
        # Parse the source code to an AST
        module = ast.parse(code)

        # Find the function definition for funcB
        for node in module.body:
            if isinstance(node, ast.ClassDef):
                for func_node in node.body:
                    if isinstance(func_node, ast.FunctionDef) and func_node.name == testFuncName:
                        # Replace the funcB node with the new code
                        new_func_node = ast.parse(newCode).body[0]
                        node.body[node.body.index(func_node)] = new_func_node
            if isinstance(node, ast.FunctionDef) and node.name == testFuncName:
                # Replace the funcB node with the new code
                new_func_node = ast.parse(newCode).body[0]
                module.body[module.body.index(node)] = new_func_node
        # Generate the modified code from the updated AST
        new_code = ast.unparse(module)
    except Exception as e:
        print(e)
        return None

    # Save the modified code as a new file
    tempFilepath = tarFilePath.replace('.py', '_temp.py')
    with open(tempFilepath, 'w') as f:
        f.write(new_code)
    print("temp file saved at: " + tempFilepath)
    return tempFilepath

def find_file_within_folder(folder, file_name):
    if '/' in file_name:
        file_name = file_name.split('/')[-1]
    for root, dirs, files in os.walk(folder):
        for file in files:
            # print(file)
            # print('file_name: ' + file_name)
            if file == file_name:
                return os.path.join(root, file)
    return None

def parse_error_message(message):
    error_lines = [line.decode('utf-8').replace('|n', '\n').replace("|", "") for line in message.split(b'\n') if
                   line.startswith(b'FAILED') or b'actual=' in line]
    error = '\n'.join(error_lines)
    short_error_lines = []
    startFlag = False
    is_error = any("ERROR" in line for line in error_lines)
    print('is_error:  ', is_error)
    if is_error:
        return 'ERROR'
    for line in error.split('\n'):
        if line.startswith('>') or ' expected=' in line or ': AssertionError' in line:
            startFlag = True
        if startFlag:
            short_error_lines.append(line)
    expectedValue = ''
    keyMessage = ''
    for line in short_error_lines:
        if 'expected=' in line and 'locationHint=' in line:
            expectedValue = line.split('expected=')[1].split('locationHint=')[0]
        if ' != ' in line and 'locationHint' not in line:
            keyMessage = line
    if expectedValue == '':
        return '\n'.join(short_error_lines)
    return f'The assert failed because:{keyMessage}. The expected value should be {expectedValue}!!'


def parse_noself_message(message):
    error_lines = [line.decode('utf-8').replace('|n', '\n').replace("|", "") for line in message.split(b'\n')]
    is_error = any("ERROR" in line for line in error_lines)
    print('is_error:  ', is_error)
    if is_error:
        return 'ERROR'

    error_lines = [line.decode('utf-8').replace('|n', '\n').replace("|", "") for line in message.split(b'\n') if
                   line.startswith(b'FAILED') or b'actual' in line]
    error = '\n'.join(error_lines)
    short_error_lines = []
    startFlag = False

    for line in error.split('\n'):
        # print(line)
        if line.startswith('>') or 'actual=' in line.lower() or ': AssertionError' in line or 'expected' in line.lower():
            startFlag = True
        if startFlag:
            short_error_lines.append(line)
    expectedValue = ''
    keyMessage = ''
    for line in short_error_lines:
        if 'actual=' in line and 'details=' in line:
            expectedValue = line.split('actual=')[1].split('details=')[0]
        elif 'actual=' in line:
            expectedValue = line.split('actual=')[1]
        if ' != ' in line and 'locationHint' not in line:
            keyMessage = line
    if expectedValue == '' and keyMessage == '':
        return '\n'.join(short_error_lines)
    return f'The assert failed because:{keyMessage}. The expected value should be {expectedValue}!!'


def run_pytest_noself(test_file, test_function, envDir, newCode, className, noClass):
    # get the temp file
    test_file = test_file+".py"
    tempFilepath = save_temp_file(test_file, newCode, test_function)
    if tempFilepath is None:
        return None

    # Run pytest as a subprocess and capture its output
    cmd = [envDir, '', '--target', tempFilepath + '::' + className + '.' + test_function]
    if className == 'default' or noClass:
        cmd = [envDir, '', '--target', tempFilepath + '::' + test_function]
    # print(noClass,cmd)
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output
        print("all error: " + str(output))
        os.remove(tempFilepath)
        return parse_noself_message(output)

    print("all error: " + str(output))
    # If pytest succeeded, return None
    if b'collected 1 item' in output and b'1 passed in' in output:
        os.remove(tempFilepath)
        return None

    # If pytest failed, extract the error message and return it
    os.remove(tempFilepath)
    return parse_noself_message(output)


def run_pytest(test_file, test_function, envDir, newCode, className, noClass):
    # get the temp file
    test_file = test_file+".py"
    tempFilepath = save_temp_file(test_file, newCode, test_function)
    if tempFilepath is None:
        return None

    # Run pytest as a subprocess and capture its output
    cmd = [envDir, '', '--target', tempFilepath + '::' + className + '.' + test_function]
    if className == 'default' or noClass:
        cmd = [envDir, '', '--target', tempFilepath + '::' + test_function]

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output
        print("error origin: " + str(e))
        os.remove(tempFilepath)
        if 'exit status 4' in str(e):
            return 'ERROR'
        return parse_error_message(output)

    # If pytest succeeded, return None
    if b'collected 1 item' in output and b'1 passed in' in output:
        os.remove(tempFilepath)
        return None

    # If pytest failed, extract the error message and return it
    os.remove(tempFilepath)
    if 'exit status 4' in str(output):
        return 'ERROR'
    return parse_error_message(output)

