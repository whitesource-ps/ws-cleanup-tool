[![Logo](https://whitesource-resources.s3.amazonaws.com/ws-sig-images/Whitesource_Logo_178x44.png)](https://www.whitesourcesoftware.com/)
[![License](https://img.shields.io/badge/License-Apache%202.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)
[![WS projects cleanup](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml)
[![Python 3.6](https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Blue_Python_3.6%2B_Shield_Badge.svg/86px-Blue_Python_3.6%2B_Shield_Badge.svg.png)](https://www.python.org/downloads/release/python-360/)
[![PyPI](https://img.shields.io/pypi/v/ws-cleanup-tool?style=plastic)](https://pypi.org/project/ws-cleanup-tool/)

# WhiteSource Projects Cleanup Tool
### Tool to clean up projects from White Source Application.
* The tool generates reports for each project in **WhiteSource** Organization in 2 modes: 
  * By stating _***REMOVED***_ and how many days to keep (-r/ DaysToKeep=)
  * By stating _OperationMode=FilterProjectsByLastCreatedCopies_ and how many copies to keep (-r/ DaysToKeep=)
* The reports are been saved in a designated location in the form of: _[ReportsDir]/[PRODUCT NAME]/[PROJECT NAME]/[REPORT NAME]_  
* _-y true_ / _DryRun=True_ flag can be used to review the outcome of a run. It will _NOT_ delete any project nor create reports 
* By default, the tool generates all possible project level reports. It is possible to state which reports to generate ((_-t_ / _Reports=_/).
* Full parameters list is available below
* The tool can be configured in 2 modes:
  * By configuring _params.config_ on the executed dir or passing a path to file in the same format.
  * By setting command line parameters as specified in the usage below. 
  
## Supported Operating Systems
- **Linux (Bash):**	CentOS, Debian, Ubuntu, RedHat
- **Windows (PowerShell):**	10, 2012, 2016

## Pre-requisites
* Python 3.7+

## Permissions
* The user used to execute the tool has to have "Organization Administrator" or "Product Administrator" on all the maintained products and "Organization Auditor" permissions. 
* It is recommended to use a service user.

## Installation and Execution from PyPi (recommended):
1. Install by executing: `pip install ws-cleanup-tool`
2. Configure the appropriate parameters either by using the command line or in `params.config`.
3. Execute the tool (`ws_cleanup_tool ...`). 

## Installation and Execution from GitHub:
1. Download and unzip **ws-cleanup-tool.zip** 
2. Install requirements: `pip install -r requirements.txt`
3. Configure the appropriate parameters either by using the command line or in `params.config`.
4. Execute: `python cleanup_tool.py <CONFIG_FILE>` 

## Full Usage flags:
```shell
usage: ws_cleanup_tool [-h] -u WS_USER_KEY -k WS_TOKEN [-a WS_URL] [-t REPORT_TYPES] [-m {FilterProjectsByUpdateTime,FilterProjectsByLastCreatedCopies}] [-o OUTPUT_DIR] [-e EXCLUDED_PRODUCT_TOKENS] [-i INCLUDED_PRODUCT_TOKENS]
                    [-g ANALYZED_PROJECT_TAG] [-r DAYS_TO_KEEP] [-p PROJECT_PARALLELISM_LEVEL] [-y DRY_RUN]

WS Cleanup Tool

optional arguments:
  -h, --help            show this help message and exit
  -u WS_USER_KEY, --userKey 
                    WS User Key
  -k WS_ORG_TOKEN, --orgToken
                    WS Organization Key (API Key)
  -a WS_URL, --wsUrl
                    WS URL
  -t REPORT_TYPES, --reportTypes
                    Report Types to generate (comma seperated list)
  -m OPERATION_MODE, --operationMode {FilterProjectsByUpdateTime,FilterProjectsByLastCreatedCopies}
                    Cleanup operation mode
  -o OUTPUT_DIR, --outputDir
                    Output directory
  -e EXCLUDED_PRODUCT_TOKENS, --excludedProductTokens
                    List of excluded products
  -i INCLUDED_PRODUCT_TOKENS, --includedProductTokens
                    List of included products
  -g ANALYZED_PROJECT_TAG, --AnalyzedProjectTag
                    Allows analyze to cleanup only if a project contains the specific WhiteSource tag
  -r DAYS_TO_KEEP, --DaysToKeep
                    Number of days to keep in FilterProjectsByUpdateTime or number of copies in FilterProjectsByLastCreatedCopies
  -p PROJECT_PARALLELISM_LEVEL, --ProjectParallelismLevel
                    Project parallelism level
  -y DRY_RUN, --DryRun
                    Logging the projects that should be deleted without deleting and creating reports
```
## Examples:
```shell
# Perform dry run check-in for getting know which projects would have been deleted: 
ws_cleanup_tool -r 30 -m FilterProjectsByUpdateTime -u <USER_KEY> -t <ORG_TOKEN> -y true 
# Keep last 60 days on each product, omitting a product token x from analyzing:
ws_cleanup_tool -r 60 -m FilterProjectsByUpdateTime -u <USER_KEY> -t <ORG_TOKEN> -e x
# Keep only 2 of the newest projects in each product token x and y:
ws_cleanup_tool -r 2 -m FilterProjectsByLastCreatedCopies -u <USER_KEY> -t <ORG_TOKEN> -i x,y
# Analyze only the projects that have a WhiteSource tag and keep the newest project in each product token:
ws_cleanup_tool -r 1 -m FilterProjectsByLastCreatedCopies -u <USER_KEY> -t <ORG_TOKEN>
```

**note:** The optimal number is derived from the size of the environment, WhiteSource scope size (memory and CPU) allocated for the server, and runtime time constraints.    