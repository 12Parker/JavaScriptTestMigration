from ..repo_names.enzyme.enzyme_repos_for_setup_script import repos
# from ..repo_names.rtl_repos_with_running_tests import repos
from ..utils.utils import run_parallel_verifications
from ..constants import ENZYME_REPOS_WITH_NO_CHANGES_PATH
# python -m JavaScriptTestMigration.scripts.setup_and_test_repos
def main():
    start = 0
    end = 0
    run_parallel_verifications(repos[1:], ENZYME_REPOS_WITH_NO_CHANGES_PATH)
if __name__ == '__main__':
    main()
