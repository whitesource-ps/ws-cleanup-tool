![Logo](https://whitesource-resources.s3.amazonaws.com/ws-sig-images/Whitesource_Logo_178x44.png)  

[![License](https://img.shields.io/badge/License-Apache%202.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub release](https://img.shields.io/github/v/release/whitesource-ps/ws-cleanup-tool)](https://github.com/whitesource-ps/ws-cleanup-tool/releases/latest)  
[![WS projects cleanup](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/whitesource-ps/ws-cleanup-tool/actions/workflows/ci.yml)
[![Python 3.6](https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Blue_Python_3.6%2B_Shield_Badge.svg/86px-Blue_Python_3.6%2B_Shield_Badge.svg.png)](https://www.python.org/downloads/release/python-360/)

# WhiteSource Projects Cleanup Tool
### Tool to archive projects from White Source Application.
* The tool generates reports for each project in **WhiteSource** Organization whose last Update Date exceeds the designated Days to Keep (default 60)
* The reports are saved in a designated location in form of: _[ReportsDir]/[PRODUCT NAME]/[PROJECT NAME]/[REPORT NAME]_  
* The **DryRun** flag can be used to review the outcome of a run. It will _NOT_ delete any project nor create reports 
* **SkipReportGeneration** Can be used to delete projects without archiving

## Supported Operating Systems
- **Linux (Bash):**	CentOS, Debian, Ubuntu, RedHat
- **Windows (PowerShell):**	10, 2012, 2016

## Pre-requisites
* Python 3.6+

## Permissions
* The user used to execute the tool has to have "Organization Administrator" or "Product Administrator" on all the maintained products and "Organization Auditor" permissions. 
* It is recommended to use a service user.

## Installation and Execution:
1. Download and unzip **ws-projects-cleanup.zip** 
1. Install requirements: `pip install -r requirements.txt`
1. Edit the **param.config** file with the appropriate parameters
1. Execute: `python projects_cleanup.py <CONFIG_FILE>` 
  
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
 
  **note:** The optimal number is derived from the size of the environment, WhiteSource scope size, (memory and CPU) allocated for the server and runtime time constraints.    
