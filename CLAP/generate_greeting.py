import re
import time

import os
from difflib import SequenceMatcher

import openai

import ast

projectDir = ''

tarFiles = []


def extract_first_two_params(call_node):
    tempList = [str(ast.unparse(node)) for node in call_node.args[:2]]
    if len(tempList) == 1:
        tempList.append('')
    return tempList[0], tempList[1]

def extract_function_params(code_string):
    if 'with ' in code_string and code_string.endswith(':'):
        code_string = code_string.replace('with ', '').replace(':', '')
    tree = ast.parse(code_string)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            return extract_first_two_params(node)


def extract_string(a):
    start_index = a.index('(') + 1
    end_index = a.rindex(')')
    return a[start_index:end_index]

def processGreetingFile(greetingFile):
    greetingPrompt = ''
    print('start processing greeting file')
    print(greetingFile)
    with open(greetingFile, 'r') as f:
        fileContent = f.read()
    [focalMethod, testCode, supportMethod] = fileContent.split('\n----------\n')
    newLines = []
    testCaseName = ''
    originalAssert = []
    assertCount = 1
    for line in testCode.split('\n'):
        if 'def ' in line and len(testCaseName) == 0:
            testCaseName = line.split(' ')[1].split('(')[0]
        if 'self.assert' in line:
            originalAssert.append(line.replace('\n', ''))
            newLine = re.sub(r'self.assert.*', f'"<AssertPlaceholder{assertCount}>"', line)
            newLines.append(newLine.replace('\n', ''))
            assertCount += 1
        else:
            newLines.append(line.replace('\n', ''))
    content = '\n'.join(newLines)
    testCode = content

    focalMethodName = ''
    for line in focalMethod.split('\n'):
        if 'def ' in line:
            focalMethodName = line.split(' ')[1].split('(')[0]
            break

    tempPrompt = f'I want you to act like a python unit testing expert. I will give you a method to be tested and an unfinished test case. Please provide step-by-step instructions for generating assertions of the test case. One <AssertPlaceholder> for one assert statement.\n\nHere is an example:\n\n#Suggest assert sentences for the following unit test case {testCaseName}:\n\n#Method to be tested:\n{focalMethod}\n#Unit test:\n{content}\n\n#Generate assertion to replace AssertPlaceholder:\nLet\'s think the answer step by step:\n1. The function is testing `{focalMethodName}` and the unit test is `{testCaseName}`.\n'
    count = 0
    for assertStatement in originalAssert:
        count += 1
        # get the assert method
        assertMethodTemp = (assertStatement.split('self.assert')[-1])
        assertMethod = 'assert'+assertMethodTemp.split('(')[0]
        # get the assert value by find the first '(' and the last ')'
        if '(' in assertMethodTemp:
            assertValue = extract_string(
                assertMethodTemp)
        else:
            assertValue = assertMethodTemp.split('(')[-1].split(')')[0]
        # get the parameter and expected value
        if ',' in assertValue:
            try:
                parameter, expectedValue = extract_function_params(assertStatement.strip())
            except:
                continue
            if expectedValue == '':
                tempPrompt += f'{count+1}. For AssertPlaceholder{count} is testing `{assertValue.strip()}` with `{assertMethod}`.\n'
            else:
                if (parameter.startswith('\'') and parameter.endswith('\'')) or (parameter.startswith('\"') and parameter.endswith('\"')):
                    valueTemp = parameter
                    parameter = expectedValue
                    expectedValue = valueTemp
                tempPrompt += f'{count+1}. For AssertPlaceholder{count} is testing `{parameter}` with `{assertMethod}`, and the expected value is `{expectedValue}`.\n'
        else:
            tempPrompt += f'{count+1}. For AssertPlaceholder{count} is testing `{assertValue.strip()}` with `{assertMethod}`.\n'
    tempPrompt += '\n#Generated assertions:\n'
    for assertStatement in originalAssert:
        assertStatementTem = assertStatement.strip()
        tempPrompt += f'{assertStatementTem}\n'

    greetingPrompt = tempPrompt + '\nIf you fully understand, please reply acknowledgement.\n'
    return greetingPrompt

def main():
    # read the existing files
    tarPath = projectDir
    result_list = []
    fileByDir = {}
    allFileNames = []
    for root, dirs, files in os.walk(tarPath):
        for file in files:
            for name in tarFiles:
                if name.replace('.py', '/') not in root:
                    continue
            if file.endswith('_result.txt'):
                result_list.append(file)
            elif file.endswith('_greeting.txt'):
                continue
            elif file.endswith('_prompt.txt'):
                continue
            else:
                dirName = root.replace(tarPath+'/', '')
                if dirName not in fileByDir:
                    fileByDir[dirName] = []
                fileByDir[dirName].append(file)
                if '.txt' not in file:
                    continue
                with open(os.path.join(root, file), 'r') as f:
                    content = f.read()
                print(os.path.join(root, file), dirName)
                for line in content.split('\n----------\n')[1].split('\n'):
                    if 'self.assert' in line:
                        allFileNames.append(os.path.join(dirName, file))
    similarFileNameDict = {}
    for dirName in fileByDir:

        for fileName in fileByDir[dirName]:
            myAssertCount = 0

            if '.txt' not in fileName:
                continue
            with open(os.path.join(tarPath, dirName, fileName), 'r') as f:
                for line in f.read().split('\n----------\n')[1].split('\n'):
                    if 'self.assert' in line:
                        myAssertCount += 1

            FileList = [f for f in fileByDir[dirName] if fileName not in f]

            maxSimilarity = 0
            maxSimilarityFileName = ''
            potentialFileList = {}
            similarThreshold = 0.7
            for f in FileList:

                similarity = SequenceMatcher(None, fileName.replace('.txt', ''), f.replace('.txt', '')).ratio()
                # count the assert number within the potential file list
                assertCount = 0
                if '.txt' not in f:
                    continue
                with open(os.path.join(tarPath, dirName, f), 'r') as tempFile:
                    for line in tempFile.read().split('\n----------\n')[1].split('\n'):
                        if 'self.assert' in line:
                            assertCount += 1
                if assertCount ==0:
                    continue
                if similarity > maxSimilarity:
                    maxSimilarity = similarity
                    maxSimilarityFileName = f
                if similarity > similarThreshold:
                    potentialFileList[f] = similarity

            if potentialFileList != {}:
                # count the assert number within the potential file list
                secondLayerFiles = {}
                for f in potentialFileList:
                    if potentialFileList[f] > 0.85:
                        similarFileNameDict[os.path.join(dirName, fileName)] = f
                        break
                    assertCount = 0
                    with open(os.path.join(tarPath, dirName, f), 'r') as file:
                        for line in file.read().split('\n----------\n')[1].split('\n'):
                            if 'self.assert' in line:
                                assertCount += 1
                    secondLayerFiles[f] = assertCount
                if similarFileNameDict.get(os.path.join(dirName, fileName)) is None:
                    for f in secondLayerFiles:
                        if secondLayerFiles[f] == myAssertCount:
                            similarFileNameDict[os.path.join(dirName, fileName)] = f
                            break
                    if similarFileNameDict.get(os.path.join(dirName, fileName)) is None:
                        for f in secondLayerFiles:
                            if secondLayerFiles[f] == myAssertCount - 1:
                                similarFileNameDict[os.path.join(dirName, fileName)] = f
                                break
                        if similarFileNameDict.get(os.path.join(dirName, fileName)) is None:
                            for f in secondLayerFiles:
                                if secondLayerFiles[f] == myAssertCount - 2:
                                    similarFileNameDict[os.path.join(dirName, fileName)] = f
                                    break
                            if similarFileNameDict.get(os.path.join(dirName, fileName)) is None:
                                similarFileNameDict[os.path.join(dirName, fileName)] = maxSimilarityFileName
            else:
                similarFileNameDict[os.path.join(dirName, fileName)] = maxSimilarityFileName

            if '503' in fileName:
                if len(similarFileNameDict[os.path.join(dirName, fileName)]) == 0:
                    print('no similar file: !!!!', fileName)
            if len(similarFileNameDict[os.path.join(dirName, fileName)]) == 0:
                # get the closest file
                maxSimilarity = 0
                maxSimilarityFileName = ''
                for allFileName in allFileNames:
                    similarity = SequenceMatcher(None, fileName.replace('.txt', ''), allFileName.split('/')[-1].replace('.txt', '')).ratio()
                    if similarity > maxSimilarity:
                        if similarity == 1 and dirName in allFileName:
                            continue

                        maxSimilarity = similarity
                        maxSimilarityFileName = allFileName
                similarFileNameDict[os.path.join(dirName, fileName)] = maxSimilarityFileName+'----'

    tarPath = projectDir
    for root, dirs, files in os.walk(tarPath):
        hasNew = False
        for name in tarFiles:
            if name.replace('.py', '') in root:
                hasNew = True
                break
        if not hasNew:
            continue
        for file in files:
            if not file.endswith('.txt'):
                continue
            if file.endswith('_result.txt') or file.endswith('_greeting.txt') or file.endswith('_prompt.txt'):
                continue
            # time.sleep(5)
            with open(os.path.join(root, file), 'r') as f:
                originalFile = f.read()

            print(os.path.join(root, file))
            [focalMethod, testCode, supportMethod] = originalFile.split('\n----------\n')
            # skip the file is there is no assert
            if 'self.assert' not in testCode:
                continue
            # skip the file is all lines are asserts
            if len(testCode.split('\n')) - len([line for line in testCode.split('\n') if 'self.assert' in line or 'def ' in line]) <= 2:
                print('skip for all asserts')
                continue
            #prepare for the greeting prompt
            #get the closest file

            dirName = root.replace(tarPath+'/', '')
            if os.path.join(dirName, file) not in similarFileNameDict:
                with open(
                        "",
                        'r') as f:
                    greetingPrompt = f.read()
            else:
                similarFileName = similarFileNameDict[os.path.join(dirName, file)]
                if len(similarFileName) == 0:
                    with open("", 'r') as f:
                        greetingPrompt = f.read()
                else:
                    tempRoot = root
                    if '/' in similarFileName:
                        # remove the last part of root path
                        if '----' in similarFileName:
                            similarFileName = similarFileName.replace('----', '')
                            tempRoot = tarPath
                            thePath = os.path.join(tempRoot, similarFileName)
                        else:
                            thePath = os.path.join('/'.join(tempRoot.split('/')[:-1]), similarFileName)
                    else:
                        if '----' in similarFileName:
                            similarFileName = similarFileName.replace('----', '')
                            tempRoot = tarPath
                        thePath = os.path.join(tempRoot, similarFileName)
                    greetingPrompt = processGreetingFile(thePath)
            # save the greeting prompt
            with open(os.path.join(root, file.replace('.txt', '_greeting.txt')), 'w') as f:
                f.write(greetingPrompt)


def checkAllGreets():
    tarPath = projectDir
    for root, dirs, files in os.walk(tarPath):
        for file in files:
            if not file.endswith('.txt'):
                continue
            if not file.endswith('_greeting.txt'):
                continue
            with open(os.path.join(root, file), 'r') as f:
                greeting = f.read()
            if greeting.count('<AssertPlaceholder') <= 1:
                print('no greeting', file)


if __name__ == '__main__':
    main()