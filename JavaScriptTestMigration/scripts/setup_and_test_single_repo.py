import argparse

from ..utils.utils import test_single_repo


# # python -m JavaScriptTestMigration.scripts.setup_and_test_single_repo --repo "akameco/pixivdeck"
def main(repo):
    test_single_repo(repo)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test your repo')
    parser.add_argument('--repo', metavar='path', required=True,
                        help='the repo name you want to test')
    args = parser.parse_args()
    main(repo=args.repo)
