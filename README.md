[![Logo](https://whitesource-resources.s3.amazonaws.com/ws-sig-images/Whitesource_Logo_178x44.png)](https://www.whitesourcesoftware.com/)
[![License](https://img.shields.io/badge/License-Apache%202.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub release](https://img.shields.io/github/v/release/whitesource-ps/ws-cleanup-tool)](https://github.com/whitesource-ps/ws-cleanup-tool/releases/latest)  
[![WS projects cleanup](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml)
[![Python 3.6](https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Blue_Python_3.6%2B_Shield_Badge.svg/86px-Blue_Python_3.6%2B_Shield_Badge.svg.png)](https://www.python.org/downloads/release/python-360/)
[![PyPI](https://img.shields.io/pypi/v/ws-cleanup-tool?style=plastic)](https://pypi.org/project/ws-cleanup-tool/)

# WhiteSource Projects Cleanup Tool
### Tool to archive projects from White Source Application.
* The tool generates reports for each project in **WhiteSource** Organization in 2 modes: 
  * By stating _OperationMode=FilterProjectsByUpdateTime_ and how many days to keep (-r/ ToKeep=)
  * By stating _OperationMode=FilterProjectsByLastCreatedCopies_ and how many copies to keep (-r/ ToKeep=)
* The reports are saved in a designated location in form of: _[ReportsDir]/[PRODUCT NAME]/[PROJECT NAME]/[REPORT NAME]_  
* _-y true_ / _DryRun=True_ flag can be used to review the outcome of a run. It will _NOT_ delete any project nor create reports 
* By default, the tool generates all possible project level reports. It is possible to state which reports to generate (-t / Reports/).
* Full flag list is available below
* The tool can be configured in 2 modes:
  * By configuring _params.config_ on the executed dir or passing a path to file in the same format.
  * By setting command switched as specified in the usage below. 
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
2. Configure the appropriate flags either by using the command switches described below or in `params.config`.
3. Execute the tool (`ws_cleanup_tool ...`). 
## Installation and Execution from GitHub:
1. Download and unzip **ws-cleanup-tool.zip** 
1. Install requirements: `pip install -r requirements.txt`
1. Edit the **param.config** file with the appropriate parameters
1. Execute: `python cleanup_tool.py <CONFIG_FILE>` 
  
## Parameters Description (_params.config_)
* IncludedProductTokens - list of included products
* ExcludedProductTokens - list of excluded products
* WsUrl - URL of WhiteSource Application (optional) 
* UserKey WhiteSource User Key
* OrgToken Organization Token
* DryRun - If True, tool will not create reports and delete projects
* SkipReportGeneration - Whether to skip report generation  
* SkipProjectDeletion - whether to skip project deletion
* DaysToKeep - How many days since last update of a project to keep 
* Reports - Report names to run
* ReportsDir - Directory to save reports in
* ProjectParallelismLevel - Number of parallel processes to generate reports.
 
## Full Usage flags:
```shell
usage: ws_cleanup_tool [-h] -u WS_USER_KEY -k WS_TOKEN [-a WS_URL] [-t REPORT_TYPES] [-m {FilterProjectsByUpdateTime,FilterProjectsByLastCreatedCopies}] [-o ARCHIVE_DIR] [-e EXCLUDED_PRODUCT_TOKENS] [-i INCLUDED_PRODUCT_TOKENS]
                    [-g ANALYZED_PROJECT_TAG] [-r TO_KEEP] [-p PROJECT_PARALLELISM_LEVEL] [-y DRY_RUN]

WS Cleanup Tool

optional arguments:
  -h, --help            show this help message and exit
  -u WS_USER_KEY, --userKey WS_USER_KEY
                        WS User Key
  -k WS_TOKEN, --token WS_TOKEN
                        WS Organization Key
  -a WS_URL, --wsUrl WS_URL
                        WS URL
  -t REPORT_TYPES, --ReportTypes REPORT_TYPES
                        Report Types to generate (comma seperated list)
  -m {FilterProjectsByUpdateTime,FilterProjectsByLastCreatedCopies}, --operation_mode {FilterProjectsByUpdateTime,FilterProjectsByLastCreatedCopies}
                        Archive operation method
  -o ARCHIVE_DIR, --out ARCHIVE_DIR
                        Output directory
  -e EXCLUDED_PRODUCT_TOKENS, --excludedProductTokens EXCLUDED_PRODUCT_TOKENS
                        Excluded list
  -i INCLUDED_PRODUCT_TOKENS, --IncludedProductTokens INCLUDED_PRODUCT_TOKENS
                        Included list
  -g ANALYZED_PROJECT_TAG, --AnalyzedProjectTag ANALYZED_PROJECT_TAG
                        Allows only analyze whether to archive if project contains a specific K:V tag
  -r TO_KEEP, --ToKeep TO_KEEP
                        Number of days to keep in FilterProjectsByUpdateTime or number of copies in FilterProjectsByLastCreatedCopies
  -p PROJECT_PARALLELISM_LEVEL, --ProjectParallelismLevel PROJECT_PARALLELISM_LEVEL
                        Project parallelism level
  -y DRY_RUN, --DryRun DRY_RUN
                        Whether to run the tool without performing anything
```
## Examples:
```shell
# Performing dry run to check which project will get deleted if command will be executed this way: 
ws_cleanup_tool -r 30 -m FilterProjectsByUpdateTime -u <USER_KEY> -t <ORG_TOKEN> -y true 
# keep last 60 days on each product omitting product token x from analyze:
ws_cleanup_tool -r 60 -m FilterProjectsByUpdateTime -u <USER_KEY> -t <ORG_TOKEN> -e x
# Keep 2 of the newest projects in each product token x and y:
ws_cleanup_tool -r 2 -m FilterProjectsByLastCreatedCopies -u <USER_KEY> -t <ORG_TOKEN> -i x,y
# Only analyze project that has k1:v1 comment and keep the newest project in each product token:
ws_cleanup_tool -r 1 -m FilterProjectsByLastCreatedCopies -u <USER_KEY> -t <ORG_TOKEN>
```

**note:** The optimal number is derived from the size of the environment, WhiteSource scope size, (memory and CPU) allocated for the server and runtime time constraints.    
