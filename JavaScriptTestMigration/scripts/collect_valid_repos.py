import os
import subprocess
import json
import fnmatch
import csv
import requests
import concurrent.futures

from collections import Counter

from ..utils.utils import run_parallel_package_checks
from ..utils.utils import read_names_from_csv
from ..constants import SEART_REPOS

# python -m JavaScriptTestMigration.scripts.collect_valid_repos
def main():
    repos = read_names_from_csv(SEART_REPOS)
    print("Repos: ", len(repos))
    UI_framework = ['react', '@angular/core', 'vue', 'svelte', 'preact']
    UI_test_framework = ['enzyme', '@testing-library/react', '@angular/core',  '@testing-library/angular', '@testing-library/vue', '@vue/test-utils', '@testing-library/svelte', '@testing-library/preact', 'preact-render-spy', 'preact']
    unit_test_library = ['jest', 'chai', 'mocha', 'jasmine', 'karma', 'jasmine-core']

    nested_counter = {framework: Counter() for framework in UI_framework}

    run_parallel_package_checks(repos, nested_counter, UI_framework, UI_test_framework, unit_test_library)
    print("All checks completed: ", str(nested_counter))
if __name__ == '__main__':
    main()