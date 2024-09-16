# from ..repo_names.enzyme.enzyme_repos_for_setup_script import repos
# from ..repo_names.rtl_repos_with_running_tests import repos
from ..utils.utils import run_parallel_verifications
from ..utils.utils import extract_repo_name_and_brace_UI_test_framework
from ..constants import ENZYME_REPOS_WITH_NO_CHANGES_PATH
import re


# python -m JavaScriptTestMigration.scripts.setup_and_test_repos
def main():
    start = 0
    end = 50
    repos = extract_repo_name_and_brace_UI_test_framework('/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/Enzyme/repos_with_running_tests.txt')
    print("REPOS: ", repos[0]['repo_name'])
    run_parallel_verifications(repos[start:], '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/enzyme/repos_with_running_tests.txt', '/home/jovyan/code/JavaScriptTesting/JavaScriptTestMigration/JavaScriptTestMigration/repo_names/react/enzyme/repos_with_failing_tests.txt')
    print("Finished")
if __name__ == '__main__':
    main()
