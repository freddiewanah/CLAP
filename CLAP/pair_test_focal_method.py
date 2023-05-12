import os
import ast
import glob

target_dir = ''
save_dir = ''
source_dir = target_dir+''

tarFiles = ['']


def get_all_files(target_dir):
    pairs = {}
    all_files = {}
    unpaired_files = {}
    counter = 1
    all_files = {
        'Test Files': [],
        'Source Files': []
    }

    # visit the test folder first
    test_dir = os.path.join(target_dir, 'test/')
    for filename in glob.iglob(test_dir + '**/**', recursive=True):

        if 'test_' not in filename or not filename.endswith('.py') or "__init__" in filename:
            continue
        fileNameRaw = filename.replace(test_dir, '')
        # if fileNameRaw not in tarFiles:
        #     continue
        all_files['Test Files'].append(fileNameRaw.lower())

    # visit the source folder
    for filename in glob.iglob(source_dir + '**/**', recursive=True):

            if not filename.endswith('.py') or 'venv/' in filename:
                continue
            if 'test_' in filename:
                continue
            fileNameRaw = filename.replace(source_dir, '')
            all_files['Source Files'].append(fileNameRaw.lower())

    print(all_files)

    return all_files

class ClassExtractAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.classes = {}
        self.functions = {}
        self.is_inside_class = False
        self.currentClass = ''

    def visit_ClassDef(self, node):
        if node.name[0] != '_':
            self.classes[node.name] = ast.unparse(node)
            self.currentClass = node.name

        # Set is_inside_class to True when visiting a ClassDef node
        self.is_inside_class = True
        self.generic_visit(node)
        self.is_inside_class = False

    def visit_FunctionDef(self, node):
        if node.name[0] != '_' and self.is_inside_class:
            self.functions[self.currentClass+'++++'+node.name] = ast.unparse(node)
        elif node.name[0] != '_' and not self.is_inside_class:
            self.functions['++++'+node.name] = ast.unparse(node)

        self.generic_visit(node)

    def get_functions(self):
        return self.functions

    def get_classes(self):
        return self.classes


class ClassExtractTestAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.classes = {}
        self.functions = {}
        self.stats = []
        self.privateFunctions = {}
        self.classWithFunction = {}
        self.currentClass = 'default'

    def visit_Import(self, node):
        for alias in node.names:
            self.stats.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.stats.append(alias.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        if node.name[0] != '_':
            self.classes[node.name] = ast.unparse(node)
        self.currentClass = node.name
        for child_node in node.body:
            # Check if the child node is a FunctionDef node with the same name as the input function
            if isinstance(child_node, ast.FunctionDef):
                if node.name not in self.classWithFunction.keys():
                    self.classWithFunction[node.name] = []
                self.classWithFunction[node.name].append(child_node.name)

        self.generic_visit(node)

    def visit_FunctionDef(self, node):

        if node.name[0] != '_' and 'test' in node.name.lower():
            if self.currentClass in self.classWithFunction.keys() and node.name in self.classWithFunction[self.currentClass]:

                if self.currentClass not in self.functions.keys():
                    self.functions[self.currentClass] = {}
                self.functions[self.currentClass][node.name] = ast.unparse(node)
            else:
                if 'default' not in self.functions.keys():
                    self.functions['default'] = {}
                self.functions['default'][node.name] = ast.unparse(node)
        elif node.name == '__init__':
            privateParams = {}
            initContent = ast.unparse(node)
            # read initContent line by line
            for line in initContent.split('\n'):
                line = line.strip()
                # get the self defined parameters in the init function
                if line.startswith('self.') and '=' in line:
                    param = line.split('self.')[1].split('=')[0].strip()
                    privateParams[param] = line
            if self.currentClass not in self.privateFunctions.keys():
                self.privateFunctions[self.currentClass] = {}
            self.privateFunctions[self.currentClass][node.name] = privateParams
        elif node.name[0] == '_':
            if self.currentClass not in self.privateFunctions.keys():
                self.privateFunctions[self.currentClass] = {}
            self.privateFunctions[self.currentClass][node.name] = ast.unparse(node)
        self.generic_visit(node)

    def get_functions(self):
        return self.functions

    def get_classes(self):
        return self.classes

    def get_imports(self):
        return self.stats

    def get_private_functions(self):
        return self.privateFunctions

def get_all_focal_methods(all_files):
    focalMethodsDict = {}
    # visit the focal methods
    for fileName in all_files['Source Files']:
        if 'venv/' in fileName:
            continue
        # read the focal file and get all functions
        print('Reading: ', fileName, source_dir)
        with open(os.path.join(source_dir, fileName[1:]), 'r') as f:
            content = f.read()
            try:
                tree = ast.parse(content)
                analyzer = ClassExtractAnalyzer()
                analyzer.visit(tree)
                # get all functions and classes
                classes = analyzer.get_classes()
                functions = analyzer.get_functions()
                if fileName not in focalMethodsDict:
                    focalMethodsDict[fileName] = {}
                for funcName in functions.keys():
                    if funcName not in focalMethodsDict[fileName].keys():
                        focalMethodsDict[fileName][funcName] = functions[funcName]

            except Exception as e:
                print('Failed to parse: ', fileName)
                print(e)
                continue


    return focalMethodsDict


class FunctionCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.function_calls = set()

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
            self.function_calls.add(function_name)
        self.generic_visit(node)

def check_function(function, functions, dirName, file, imports, content, focalMethodsDict, privateFunctions, thisClassName):
    methodCalled = []
    # check if function has a line start with self.assert
    functionValid = False
    for line in functions[function].split('\n'):
        if line.strip().startswith('self.assert') or line.strip().startswith('assert '):
            functionValid = True
            break
    if not functionValid:
        return None
    try:
        funcTree = ast.parse(functions[function])
        for node in ast.walk(funcTree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    methodCalled.append(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    methodCalled.append(node.func.id)

    except Exception as e:
        print(e)
        return None
    potentialFunctions = []
    for fileNameTemp in focalMethodsDict.keys():
        for funcName in focalMethodsDict[fileNameTemp].keys():
             libName = fileNameTemp.replace('.py', '').split('/')[-1]
             className = funcName.split('++++')[0]
             funcName1 = funcName.split('++++')[1]
             for importedLib in imports:
                 if libName.lower() in importedLib.lower():
                     if className in content:
                         potentialFunctions.append((fileNameTemp, funcName, funcName1))
             for importedLib in imports:
                 if className in importedLib:
                     if funcName1 in content:
                         if (fileNameTemp, funcName, funcName1) not in potentialFunctions:
                             potentialFunctions.append((fileNameTemp, funcName, funcName1))
    #   reverse loop through the methodCalled
    for method in reversed(methodCalled):
        for potentialFunction in potentialFunctions:
            if method == potentialFunction[2] and len(potentialFunction[1].split('++++')[0]) > 0:
                # check if addtional information is needed
                additionalInformation = checkAdditonalInfo(privateFunctions, functions[function], thisClassName)
                return {
                    'focalFile': focalMethodsDict[potentialFunction[0]][potentialFunction[1]],
                    'testFunction': functions[function],
                    'additionalInformation': additionalInformation
                }
        for potentialFunction in potentialFunctions:
            if method == potentialFunction[2]:
                additionalInformation = checkAdditonalInfo(privateFunctions, functions[function], thisClassName)
                return {
                    'focalFile': focalMethodsDict[potentialFunction[0]][potentialFunction[1]],
                    'testFunction': functions[function],
                    'additionalInformation': additionalInformation
                }
    return None

def checkAdditonalInfo(privateFunctions, testFunction, className):
    additionalLines = []
    if className not in privateFunctions.keys():
        return additionalLines
    if '__init__' in privateFunctions[className].keys():
        for param in privateFunctions[className]['__init__'].keys():
            if 'self.' + param in testFunction:
                additionalLines.append(privateFunctions[className]['__init__'][param])
    for funcName in privateFunctions[className].keys():
        if '__init__' not in funcName:
            if 'self.' + funcName in testFunction:
                additionalLines.append(privateFunctions[className][funcName])
    return additionalLines

def get_pairs(focalMethodsDict, all_files, save_dir):
    count = 0
    noList = []
    allFilesCount = len(all_files['Test Files'])
    currentProgressCount = 0
    # visit the test files
    for testFileName in all_files['Test Files']:
        currentProgressCount += 1
        print('current progress: ', currentProgressCount, '/', allFilesCount)
        with open(os.path.join(target_dir, 'test', testFileName), 'r') as f:
            content = f.read()
            if 'assert' not in content:
                continue
            try:
                tree = ast.parse(content)
                analyzer = ClassExtractTestAnalyzer()
                analyzer.visit(tree)

                # get all functions and classes
                classes = analyzer.get_classes()
                functions = analyzer.get_functions()
                imports = analyzer.get_imports()
                privateFunctions = analyzer.get_private_functions()
                for thisClassName in functions.keys():
                    for function in functions[thisClassName].keys():
                        # check if file saved
                        if os.path.exists(os.path.join(save_dir, testFileName.replace('.py', ''), function + '.txt')):
                            continue

                        result = check_function(function, functions[thisClassName], testFileName, testFileName, imports, content, focalMethodsDict, privateFunctions, thisClassName)
                        if result is not None:

                            if not os.path.exists(os.path.join(save_dir, testFileName.replace('.py', ''))):
                                os.makedirs(os.path.join(save_dir, testFileName.replace('.py', '')))
                            with open(os.path.join(save_dir, testFileName.replace('.py', ''), function + '.txt'), 'w') as f:
                                f.write(result['focalFile'])
                                f.write('\n\n----------\n\n')
                                f.write(result['testFunction'])
                                f.write('\n\n----------\n\n')
                                f.write('\n'.join(result['additionalInformation']))
                                f.write(f'\n\nTest Class Name: {thisClassName}')

            except Exception as e:
                print(e)
                continue

if __name__ == '__main__':
    all_files = get_all_files(target_dir)
    focalMethodsDict = get_all_focal_methods(all_files)
    get_pairs(focalMethodsDict, all_files, save_dir)

