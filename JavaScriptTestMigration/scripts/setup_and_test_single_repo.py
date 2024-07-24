import argparse

# Use this when you want to re-test every repo that was verified previously
from ..repo_names.repos_with_running_tests import repos
from ..utils.utils import test_single_repo

def main(repo):
    test_single_repo(repo)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test your repo')
    parser.add_argument('--repo', metavar='path', required=True,
                        help='the repo name you want to test')
    args = parser.parse_args()
    main(repo=args.repo)
