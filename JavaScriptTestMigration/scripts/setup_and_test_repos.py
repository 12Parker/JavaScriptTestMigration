from ..repo_names.repos_with_running_tests import repos
from ..utils.utils import run_parallel_verifications


def main():
    start = 0
    end = 2
    run_parallel_verifications(repos[start:end])
if __name__ == '__main__':
    main()
