import os
import subprocess
import json
import fnmatch
import csv
import requests
import concurrent.futures

from ..utils.utils import run_parallel_package_checks
from ..utils.utils import read_names_from_csv
from ..constants import SEART_REPOS

def main():
    repos = read_names_from_csv(SEART_REPOS)
    print("Repos: ", len(repos))
    package_names = ['enzyme', '@testing-library/react']

    run_parallel_package_checks(repos[50:150], package_names)
    print("All checks completed.")
if __name__ == '__main__':
    main()