# JavaScriptTestMigration
JavaScript Test Suite Migration Tool

JavascriptRepos.csv contains a list of approximately 30k JavaScript repositories, downloaded from the SEART website: https://seart-ghs.si.usi.ch/

Step 1:
To begin replication, start with collect_valid_repos.py.
This script will check the repositories under JavascriptRepos.csv and verify that they contain a testing library
It is currently setup to look for: 'enzyme', '@testing-library/react', 'jest', 'mocha', 'chai', 'karma', 'karma-enzyme', 'karma-chai', 'karma-jasmine', 'chai-enzyme', and 'jasmine-core'

It will run in parallel and should complete in a few minutes. It will save the valid repositories to a text file called 'valid_repos.txt'
Manual step: paste the repos from 'valid_repos.txt' into repoNames.py (TODO: Automate this)

Step 2:
Run the script called setup_and_test_repos.py
This script will perform several steps:
    1. Clone the repos from 'repoNames.py'
    2. Install dependencies from the package.json file 
    3. Run the 'test' script in the package.json file
    4. If the test suite is able to run, it saves the repo name to 'success'

Step 3:
This script will attempt to migrate a given test file from the original testing library to a chosen library (ex. Enzyme to React-testing-library)
It will create a new file and then run the test suite to determine if the migrated test file is able to pass
TODO: The script will also update the package.json and reinstall dependencies before running the test script


