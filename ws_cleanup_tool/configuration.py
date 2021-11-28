import argparse
import logging
import os
import sys
from configparser import ConfigParser
from dataclasses import dataclass

from ws_sdk import WS

from ws_cleanup_tool._version import __description__, __tool_name__, __version__
from cleanup_tool import logger, get_reports
from filter_strategies import FilterProjectsByUpdateTime, FilterProjectsInt


def parse_config():
    @dataclass
    class Config:
        ws_url: str
        ws_token: str
        ws_user_key: str
        excluded_product_tokens: list
        included_product_tokens: list
        analyzed_project_tag: dict
        operation_mode: str  # = retention  # time_based
        to_keep: int
        number_of_projects_to_retain: int
        dry_run: bool
        report_types: str
        reports: list
        archive_dir: str
        project_parallelism_level: int
        ws_conn: WS

    def get_conf_value(c_p_val, alt_val):
        return c_p_val if c_p_val else alt_val

    def generate_analyzed_project_tag(analyzed_project_tag):
        conf.analyzed_project_tag_t = tuple(analyzed_project_tag.replace(" ", "").split(":"))
        if len(conf.analyzed_project_tag_t) != 2:
            logging.error(f"Unable to parse Project tag: {conf.analyzed_project_tag}")
            conf.analyzed_project_tag_t = None
        else:
            logging.info(f"Project tag is set. The tool will only analyze projects with tag: '{conf.analyzed_project_tag}'")

    global conf

    if len(sys.argv) < 3:
        maybe_config_file = True
    if len(sys.argv) == 1:
        conf_file = "params.config"
    elif not sys.argv[1].startswith('-'):
        conf_file = sys.argv[1]
    else:
        maybe_config_file = False

    if maybe_config_file:                             # Covers no conf file or only conf file
        if os.path.exists(conf_file):
            logger.info(f"loading configuration from file: {conf_file}")
            config = ConfigParser()
            config.optionxform = str
            if os.path.exists(conf_file):
                logger.info(f"loading configuration from file: {conf_file}")
                config.read(conf_file)

                conf = Config(
                    ws_url=config['DEFAULT'].get("WsUrl"),
                    ws_token=get_conf_value(config['DEFAULT'].get("OrgToken"), os.environ.get("WS_TOKEN")),
                    ws_user_key=get_conf_value(config['DEFAULT'].get("UserKey"), os.environ.get("WS_USER_KEY")),
                    excluded_product_tokens=config['DEFAULT'].get("ExcludedProductTokens"),
                    included_product_tokens=config['DEFAULT'].get("IncludedProductTokens"),
                    analyzed_project_tag=config['DEFAULT'].get("AnalyzedProjectTag", None),
                    operation_mode=config['DEFAULT'].get("OperationMode", FilterProjectsByUpdateTime.__name__),
                    to_keep=config['DEFAULT'].getint("ToToKeep", 5),
                    number_of_projects_to_retain=config['DEFAULT'].getint("NumberOfProjectsToRetain", 1),
                    dry_run=config['DEFAULT'].getboolean("DryRun", False),
                    archive_dir=config['DEFAULT'].get('ReportsDir', os.getcwd()),
                    report_types=config['DEFAULT'].get('Reports'),
                    reports=None,
                    project_parallelism_level=config['DEFAULT'].getint('ProjectParallelismLevel', 5),
                    ws_conn=None)
        else:
            logging.error(f"No configuration file found at: {conf_file}")
            raise FileNotFoundError
    else:
        parser = argparse.ArgumentParser(description=__description__)
        parser.add_argument('-u', '--userKey', help="WS User Key", dest='ws_user_key', required=True)
        parser.add_argument('-k', '--token', help="WS Organization Key", dest='ws_token', required=True)
        parser.add_argument('-a', '--wsUrl', help="WS URL", dest='ws_url')
        parser.add_argument('-t', '--ReportTypes', help="Report Types to generate (comma seperated list)", dest='report_types')
        parser.add_argument('-m', '--operation_mode', help="Archive operation method", dest='operation_mode', default="FilterProjectsByUpdateTime",
                            choices=[s.__name__ for s in FilterProjectsInt.__subclasses__()])
        parser.add_argument('-o', '--out', help="Output directory", dest='archive_dir', default=os.getcwd())
        parser.add_argument('-e', '--excludedProductTokens', help="Excluded list", dest='excluded_product_tokens', default="")
        parser.add_argument('-i', '--IncludedProductTokens', help="Included list", dest='included_product_tokens', default="")
        parser.add_argument('-g', '--AnalyzedProjectTag', help="Allows only analyze whether to archive if project contains a specific K:V tag", dest='analyzed_project_tag')
        parser.add_argument('-r', '--ToKeep', help="Number of days to keep in FilterProjectsByUpdateTime or number of copies in FilterProjectsByLastCreatedCopies", dest='to_keep', type=int, default=5)
        parser.add_argument('-p', '--ProjectParallelismLevel', help="Project parallelism level", dest='project_parallelism_level', type=int, default=5)
        parser.add_argument('-y', '--DryRun', help="Whether to run the tool without performing anything", dest='dry_run', type=bool, default=False)
        conf = parser.parse_args()

    if conf.analyzed_project_tag:
        generate_analyzed_project_tag(conf.analyzed_project_tag)

    conf.included_product_tokens = conf.included_product_tokens.replace(" ", "").split(",") if conf.included_product_tokens else []
    conf.excluded_product_tokens = conf.excluded_product_tokens.replace(" ", "").split(",") if conf.excluded_product_tokens else []
    conf.reports = get_reports(conf.report_types)
    conf.ws_conn = WS(url=conf.ws_url,
                      user_key=conf.ws_user_key,
                      token=conf.ws_token,
                      tool_details=(f"ps-{__tool_name__.replace('_', '-')}", __version__))
    return conf
