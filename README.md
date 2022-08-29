[![Logo](https://resources.mend.io/mend-sig/logo/mend-dark-logo-horizontal.png)](https://www.mend.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)
[![WS projects cleanup](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml)
[![Python 3.6](https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Blue_Python_3.6%2B_Shield_Badge.svg/86px-Blue_Python_3.6%2B_Shield_Badge.svg.png)](https://www.python.org/downloads/release/python-360/)
[![PyPI](https://img.shields.io/pypi/v/ws-cleanup-tool?style=plastic)](https://pypi.org/project/ws-cleanup-tool/)

# Mend Projects Cleanup CLI Tool
* The self-hosted CLI tool features cleaning up projects and generating reports before deletion in 2 modes:
  * By stating _OperationMode=FilterProjectsByUpdateTime_ and how many days to keep (-r/ DaysToKeep=)
  * By stating _OperationMode=FilterProjectsByLastCreatedCopies_ and how many copies to keep (-r/ DaysToKeep=)
* The reports are saved in the designated location as follows: _[ReportsDir]/[PRODUCT NAME]/[PROJECT NAME]/[REPORT NAME]_  
* To review the outcome before actual deletion use _-y true_ / _DryRun=True_ flag. It will _NOT_ delete any project nor create reports 
* By default, the tool generates all possible project-level reports. By specifying ((_-t_ / _Reports=_/) it is possible to select specific reports
* The full parameters list is available below
* There are two ways to configure the tool:
  * By configuring _params.config_ on the executed dir or passing a path to the file in the same format
  * By setting command line parameters as specified in the usage below
  
## Supported Operating Systems
- **Linux (Bash):**	CentOS, Debian, Ubuntu, RedHat
- **Windows (PowerShell):**	10, 2012, 2016

## Pre-requisites
* Python 3.8+

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
3. Configure the appropriate parameters either by using the command line or `params.config`.
4. Execute: `python cleanup_tool.py <CONFIG_FILE>` 

## Examples:
Perform dry run check-in to get to know which projects would have been deleted:  
`ws_cleanup_tool -r 30 -m FilterProjectsByUpdateTime -u <USER_KEY> -k <ORG_TOKEN> -y true`

---

Keep the last 60 days on each product, omitting a product token <PRODUCT_1> from analyzing:  
`ws_cleanup_tool -r 60 -m FilterProjectsByUpdateTime -u <USER_KEY> -k <ORG_TOKEN> -e <PRODUCT_TOKEN_1>`

---

Keep only two of the newest projects in each product token PRODUCT_1 and PRODUCT_2:  
`ws_cleanup_tool -r 2 -m FilterProjectsByLastCreatedCopies -u <USER_KEY> -k <ORG_TOKEN> -i <PRODUCT_TOKEN_1>,<PRODUCT_TOKEN_2>`

---

Analyze only the projects that have the specified Mend tag and keep the newest project in each product:  
`ws_cleanup_tool -r 1 -m FilterProjectsByLastCreatedCopies -u <USER_KEY> -k <ORG_TOKEN> -g <KEY>:<VALUE>`

---

Keep the last 2 weeks and analyze only the projects whose match their tag key and the tag value contains the specified regex:  
`ws_cleanup_tool -r 14 -m FilterProjectsByUpdateTime -u <USER_KEY> -k <ORG_TOKEN> -g <KEY>:<REGEX_VALUE>`

---

Keep the last 100 days for both PRODUCT_1 and PRODUCT_2, but do not delete the project PROJECT_1 (which is a project in one of the included products):  
`ws_cleanup_tool -r 100 -m FilterProjectsByUpdateTime -u <USER_KEY> -k <ORG_TOKEN> -i <PRODUCT_TOKEN_1>,<PRODUCT_TOKEN_2> -x <PROJECT_TOKEN_1>`

---

Keep the last month for both PRODUCT_1 and PRODUCT_2, but do not delete projects that contain provided strings in their names:  
`ws_cleanup_tool -r 31 -m FilterProjectsByUpdateTime -u <USER_KEY> -k <ORG_TOKEN> -i <PRODUCT_TOKEN_1>,<PRODUCT_TOKEN_2> -n CI_,-test`

---


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
                    Analyze only the projects whose contain the specific Mend tag (key:value)
  -v ANALYZED_PROJECT_TAG_REGEX_IN_VALUE, --AnalyzedProjectTagRegexInValue
                    Analyze only the projects whose match their tag key and the tag value contains the specified regex (key:regexValue)
  -r DAYS_TO_KEEP, --DaysToKeep
                    Number of days to keep in FilterProjectsByUpdateTime or number of copies in FilterProjectsByLastCreatedCopies
  -p PROJECT_PARALLELISM_LEVEL, --ProjectParallelismLevel
                    Project parallelism level
  -y DRY_RUN, --DryRun
                    Logging the projects that are supposed to be deleted without deleting and creating reports
                    default False
  -s SKIP_REPORT_GENERATION, --SkipReportGeneration
                    Skip report generation step
                    default True
  -j SKIP_PROJECT_DELETION, --SkipProjectDeletion
                    Skip project deletion step
                    default False                                        
  -x EXCLUDED_PROJECT_TOKENS, --excludedProjectTokens
                    List of excluded projects
  -n EXCLUDED_PROJECT_NAME_PATTERNS, --excludedProjectNamePatterns
                    List of excluded project name patterns                 
```

**note:** The optimal cleanup scope is derived from the size of the environment, Mend scope size (memory and CPU) allocated for the server, and runtime time constraints.    
