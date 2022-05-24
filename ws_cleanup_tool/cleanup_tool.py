import argparse
import logging
import os
import sys
from abc import ABC, abstractmethod
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import timedelta, datetime
from multiprocessing import Manager
from multiprocessing.pool import ThreadPool

from ws_sdk import ws_errors, WS, ws_constants

from ws_cleanup_tool._version import __description__, __tool_name__, __version__

# skip_report_generation = bool(os.environ.get("SKIP_REPORT_GENERATION", 0))
# skip_project_deletion = bool(os.environ.get("SKIP_PROJECT_DELETION", 0))

logging.basicConfig(level=logging.DEBUG if bool(os.environ.get("DEBUG", "false")) is True else logging.INFO,
                    handlers=[logging.StreamHandler(stream=sys.stdout)],
                    format='%(levelname)s %(asctime)s %(thread)d %(name)s: %(message)s',
                    datefmt='%y-%m-%d %H:%M:%S')
logger = logging.getLogger(__tool_name__)
logging.getLogger('urllib3').setLevel(logging.WARNING)

conf = None


class FilterStrategy:
    def __init__(self, filter_projects) -> None:
        self._filter_projects = filter_projects

    def execute(self):
        def replace_invalid_chars(directory: str) -> str:
            for char in ws_constants.INVALID_FS_CHARS:
                directory = directory.replace(char, "_")

            return directory

        projects = self._filter_projects.get_projects_to_archive()

        for project in projects:
            product_name = replace_invalid_chars(project['product_name'])
            project_name = replace_invalid_chars(project['name'])
            project['project_output_dir'] = os.path.join(os.path.join(conf.output_dir, product_name), project_name)

        return projects


class FilterProjectsInt(ABC):
    def __init__(self, products_to_clean, config):
        self.products_to_clean = products_to_clean
        self.conf = config
        self.should_filter_by_tag = True if self.conf.analyzed_project_tag else False

    @abstractmethod
    def get_projects_to_archive(self):
        ...

    def is_valid_project(self, project):
        def is_tag_exist(p):
            project_metadata_d = p.get('project_metadata_d', {})
            if self.conf.analyzed_project_tag_t[0] in project_metadata_d.keys() \
                    and project_metadata_d[self.conf.analyzed_project_tag_t[0]] == self.conf.analyzed_project_tag_t[1]:
                return True
            else:
                return False

        ret = True
        if not self.should_filter_by_tag:
            logger.debug(f"Project {project['name']} is valid")
        elif self.should_filter_by_tag and is_tag_exist(project):
            logger.debug(f"Project {project['name']} contains appropriate key:value pair: {self.conf.analyzed_project_tag_t}")
        else:
            logger.debug(f"Project {project['name']} does not contain appropriate key:value pair: {self.conf.analyzed_project_tag_t}")
            ret = False

        return ret


class FilterProjectsByUpdateTime(FilterProjectsInt):
    def get_projects_to_archive(self) -> list:
        days_to_keep = timedelta(days=self.conf.days_to_keep)
        archive_date = datetime.utcnow() - days_to_keep
        logger.info(f"Keeping {days_to_keep.days} days. Looking for the projects older than {archive_date}")

        manager = Manager()
        projects_to_archive_q = manager.Queue()
        with ThreadPool(processes=self.conf.project_parallelism_level) as pool:
            pool.starmap(self.get_projects_to_archive_w,
                         [(archive_date, prod, self.conf.ws_conn, projects_to_archive_q) for prod in self.products_to_clean])
        return extract_from_q(projects_to_archive_q)

    def get_projects_to_archive_w(self, archive_date, prod, ws_conn, projects_to_archive_q):
        curr_prod_projects = ws_conn.get_projects(product_token=prod['token'], include_prod_proj_names=True)
        logger.info(f"Handling product: {prod['name']} number of projects: {len(curr_prod_projects)}")

        for project in curr_prod_projects:
            project_time = datetime.strptime(project['lastUpdatedDate'], "%Y-%m-%d %H:%M:%S +%f")
            if project_time < archive_date and self.is_valid_project(project):
                logger.debug(f"Project {project['name']} Token: {project['token']} Last update: {project['lastUpdatedDate']} will be cleaned up")
                projects_to_archive_q.put(project)


class FilterProjectsByLastCreatedCopies(FilterProjectsInt):
    def get_projects_to_archive(self) -> list:
        logger.info(f"Keeping last recent {self.conf.days_to_keep} projects. Cleaning up the rest")
        manager = Manager()
        projects_to_archive_q = manager.Queue()
        with ThreadPool(processes=self.conf.project_parallelism_level) as pool:
            pool.starmap(self.get_projects_to_archive_w,
                         [(prod['token'], self.conf.ws_conn, projects_to_archive_q) for prod in self.products_to_clean])
        projects_to_archive = extract_from_q(projects_to_archive_q)

        if not projects_to_archive:
            logger.info("No projects to clean up were found")

        return projects_to_archive

    def get_projects_to_archive_w(self, product_token: str, ws_conn: WS, projects_to_archive_q):
        projects = ws_conn.get_projects(product_token=product_token, sort_by=ws_constants.ScopeSorts.UPDATE_TIME)
        filtered_projects = [project for project in projects if self.is_valid_project(project)]
        if len(filtered_projects) > self.conf.days_to_keep:
            index = len(filtered_projects) - self.conf.days_to_keep
            last_projects = filtered_projects[:index]
            logger.debug(f"Total {len(filtered_projects)}. Archiving first {index}")
            projects_to_archive_q.put(last_projects)
        else:
            logger.debug(f"Total {len(filtered_projects)}. Nothing to cleanup")


def extract_from_q(projects_to_archive_q):
    projects_to_archive = []
    while not projects_to_archive_q.empty():
        item = projects_to_archive_q.get(block=True, timeout=0.05)
        projects_to_archive.append(item) if isinstance(item, dict) else projects_to_archive.extend(item)

    return projects_to_archive


def get_reports_to_archive(projects_to_archive: list) -> list:
    project_reports_desc_list = []

    for project in projects_to_archive:  # Creating list of report to-be-produced meta data
        if not os.path.exists(project['project_output_dir']):
            os.makedirs(project['project_output_dir'])

        for report in conf.report_types:
            curr_project_report = project.copy()
            curr_project_report['report'] = report

            project_reports_desc_list.append(curr_project_report)

    logger.info(f"Found total {len(projects_to_archive)} projects to clean up ({len(project_reports_desc_list)} reports will be produced)")

    return project_reports_desc_list


def get_products_to_archive(included_product_tokens: list, excluded_product_tokens: list) -> list:
    if included_product_tokens:
        logger.debug(f"Product tokens to check for cleanup: {included_product_tokens}")
        prods = [conf.ws_conn.get_scopes(scope_type=ws_constants.ScopeTypes.PRODUCT, token=prod_t).pop() for prod_t in included_product_tokens]
    else:
        logger.debug("Getting all products")
        prods = conf.ws_conn.get_products()

    all_prods_n = len(prods)
    if excluded_product_tokens:
        logger.debug(f"Product tokens configured to be excluded from cleanup: {excluded_product_tokens}")
        prods = [prod for prod in prods if prod['token'] not in excluded_product_tokens]

    logger.info(f"Product names for cleanup check: {[prod['name'] for prod in prods]}")
    logger.info(f"{all_prods_n} Products to handle out of {len(prods)}")

    return prods


def exclude_projects(projects_to_archive: list, excluded_project_tokens: list, excluded_project_name_patterns: list) -> list:
    if excluded_project_tokens:
        if not ([proj for proj in projects_to_archive if proj['token'] in excluded_project_tokens]):
            logger.error(f"One of the project tokens hasn't been found in the provided products: {excluded_project_tokens} ")
            exit(-1)
        else:
            logger.debug(f"Exclude project tokens: {excluded_project_tokens}")
            projects = [proj for proj in projects_to_archive if proj['token'] not in excluded_project_tokens]
    else:
        projects = projects_to_archive

    if excluded_project_name_patterns:
        for patt in excluded_project_name_patterns:
            if not ([proj for proj in projects for k, v in proj.items() if k == "name" and patt in v]):
                logger.error(f"pattern {patt} hasn't been found for any project in the provided products")
                exit(-1)

            logger.debug(f"Exclude projects with name pattern: {patt}")
            projects = [proj for proj in projects for k, v in proj.items() if k == "name" and patt not in v]
    else:
        projects = projects_to_archive
    logger.info(f"Project names for cleanup check: {[proj['name'] for proj in projects]}")

    return projects


def generate_reports_m(reports_desc_list: list) -> list:
    manager = Manager()
    failed_proj_tokens_q = manager.Queue()
    with ThreadPool(processes=conf.project_parallelism_level) as pool:
        pool.starmap(generate_report_w,
                     [(report_desc, conf.ws_conn, failed_proj_tokens_q) for report_desc in reports_desc_list])

    failed_projects = []
    while not failed_proj_tokens_q.empty():
        failed_projects.append(failed_proj_tokens_q.get(block=True, timeout=0.05))

    if failed_projects:
        logger.warning(f"{len(failed_projects)} projects were failed to clean up")

    return failed_projects


def generate_report_w(report_desc: dict, connector: WS, w_f_proj_tokens_q) -> None:
    def get_suffix(entity):     # Handling case where more than 1 suffix
        return entity if isinstance(entity, str) else entity[0]

    if report_desc['report'].bin_sfx:
        report_name = f"{report_desc['report'].name}.{get_suffix(report_desc['report'].bin_sfx)}"
        report_full_path = os.path.join(report_desc['project_output_dir'], report_name)
        if conf.dry_run:
            logger.info(f"[DRY_RUN] Report: '{report_name}' has to be created on the project: '{report_desc['name']}'")
        else:
            logger.debug(f"Generating report: '{report_full_path}' on the project: '{report_desc['name']}'")
            try:
                report = report_desc['report'].func(connector, token=report_desc['token'], report=True)
                f = open(report_full_path, 'bw')
                if not report:
                    report = bytes()
                f.write(report)
            except ws_errors.WsSdkServerError or OSError:
                logger.exception(f"Error producing report: '{report_desc['report_type']}' on project {report_desc['name']}. Project will not be deleted.")
                w_f_proj_tokens_q.put(report_desc['token'])
    else:
        logger.debug(f"Skipping report: {report_desc['report'].name} is invalid")


def delete_projects(projects_to_archive: list, failed_project_tokens: list) -> None:
    w_dry_run = conf.dry_run
    projects_to_delete = projects_to_archive.copy()
    for project in projects_to_archive:
        if project['token'] in failed_project_tokens:
            projects_to_delete.remove(project)
    logger.info(f"Total found {len(projects_to_archive)} projects to delete. {len(projects_to_delete)} projects have valid tokens and should be deleted")

    if projects_to_delete:
        with ThreadPool(processes=1) as thread_pool:
            thread_pool.starmap(worker_delete_project, [(conf.ws_conn, project, w_dry_run) for project in projects_to_delete])
        if w_dry_run:
            logger.info(f"Total found {len(projects_to_delete)} projects that have to be deleted")
        else:
            logger.info(f"{len(projects_to_delete)} projects have been deleted")


def worker_delete_project(conn, project, w_dry_run):
    if w_dry_run:
        logger.info(f"[DRY_RUN] project: {project['name']}. Last update date is: {project['lastUpdatedDate']}. Token: {project['token']} ")
    else:
        logger.info(f"Deleting project: {project['name']}. Last update date is: {project['lastUpdatedDate']}. Token: {project['token']} ")
        conn.delete_scope(project['token'])


def parse_config():
    @dataclass
    class Config:
        ws_user_key: str
        ws_org_token: str
        ws_url: str
        report_types: str
        operation_mode: str
        output_dir: str
        excluded_product_tokens: list
        included_product_tokens: list
        excluded_project_tokens: list
        excluded_project_name_patterns: list
        analyzed_project_tag: dict
        days_to_keep: int
        project_parallelism_level: int
        dry_run: bool
        skip_report_generation: bool
        skip_project_deletion: bool

        ws_conn: WS

    def get_conf_value(c_p_val, alt_val):
        return c_p_val if c_p_val else alt_val

    def generate_analyzed_project_tag(analyzed_project_tag):
        conf.analyzed_project_tag_t = tuple(analyzed_project_tag.replace(" ", "").split(":"))
        if len(conf.analyzed_project_tag_t) != 2:
            logger.error(f"Unable to parse Project tag: {conf.analyzed_project_tag}")
            conf.analyzed_project_tag_t = None
        else:
            logger.info(f"Project tag is set. The tool will only analyze projects with tag: '{conf.analyzed_project_tag}'")

    global conf

    if len(sys.argv) < 3:
        maybe_config_file = True
    if len(sys.argv) == 1:
        conf_file = "../params.config"
    elif not sys.argv[1].startswith('-'):
        conf_file = sys.argv[1]
    else:
        maybe_config_file = False

    if maybe_config_file:                             # Covers no conf file or only conf file
        if os.path.exists(conf_file):
            logger.info(f"loading configuration from file: {conf_file}")
            config = ConfigParser()
            config.optionxform = str
            # if os.path.exists(conf_file):
            #     logger.info(f"loading configuration from file: {conf_file}")
            config.read(conf_file)
            operation_mode = get_conf_value(config['DEFAULT'].get("OperationMode"), FilterProjectsByUpdateTime.__name__)

            conf = Config(
                ws_user_key=get_conf_value(config['DEFAULT'].get("WsUserKey"), os.environ.get("WS_USER_KEY")),
                ws_org_token=get_conf_value(config['DEFAULT'].get("WsOrgToken"), os.environ.get("WS_ORG_TOKEN")),
                ws_url=get_conf_value(config['DEFAULT'].get("WsUrl"), os.environ.get("WS_URL")),
                report_types=get_conf_value(config['DEFAULT'].get('ReportTypes'), os.environ.get("REPORT_TYPES")),
                operation_mode=operation_mode,
                output_dir=get_conf_value(config['DEFAULT'].get('ReportsDir'), os.getcwd()),
                excluded_product_tokens=get_conf_value(config['DEFAULT'].get("ExcludedProductTokens", None), os.environ.get("EXCLUDED_PRODUCT_TOKENS")),
                included_product_tokens=get_conf_value(config['DEFAULT'].get("IncludedProductTokens", None), os.environ.get("INCLUDED_PRODUCT_TOKENS")),
                excluded_project_tokens=get_conf_value(config['DEFAULT'].get("ExcludedProjectTokens", None), os.environ.get("EXCLUDED_PROJECT_TOKENS")),
                excluded_project_name_patterns=get_conf_value(config['DEFAULT'].get("ExcludedProjectNamePatterns", None), os.environ.get("EXCLUDED_PROJECT_NAME_PATTERNS")),
                analyzed_project_tag=get_conf_value(config['DEFAULT'].get("AnalyzedProjectTag", None), os.environ.get("ANALYZED_PROJECT_TAG")),
                days_to_keep=get_conf_value(config['DEFAULT'].getint("DaysToKeep", 50000), os.environ.get("DAYS_TO_KEEP")),
                project_parallelism_level=config['DEFAULT'].getint('ProjectParallelismLevel', 5),
                dry_run=config['DEFAULT'].getboolean("DryRun", True),
                skip_report_generation=config['DEFAULT'].getboolean("SkipReportGeneration", True),
                skip_project_deletion=config['DEFAULT'].getboolean("SkipProjectDeletion", True),
                ws_conn=None
            )


        else:
            logger.error(f"No configuration file found at: {conf_file}")
            raise FileNotFoundError
    else:
        parser = argparse.ArgumentParser(description=__description__)
        parser.add_argument('-u', '--userKey', help="WS User Key", dest='ws_user_key', default=os.environ.get("WS_USER_KEY"))
        parser.add_argument('-k', '--orgToken', help="WS Organization Key", dest='ws_org_token', default=os.environ.get("WS_ORG_TOKEN"))
        parser.add_argument('-a', '--wsUrl', help="WS URL", dest='ws_url', default=os.environ.get("WS_URL"))
        parser.add_argument('-t', '--reportTypes', help="Report Types to generate (comma seperated list)", dest='report_types', default=os.environ.get("REPORT_TYPES"))
        parser.add_argument('-m', '--operationMode', help="Clean up operation method", dest='operation_mode', default="FilterProjectsByUpdateTime",
                            choices=[s.__name__ for s in FilterProjectsInt.__subclasses__()])
        parser.add_argument('-o', '--outputDir', help="Output directory", dest='output_dir', default=os.getcwd())
        parser.add_argument('-e', '--excludedProductTokens', help="Excluded Product Tokens list", dest='excluded_product_tokens', default=os.environ.get("EXCLUDED_PRODUCT_TOKENS"))
        parser.add_argument('-i', '--includedProductTokens', help="Included Product Tokens list", dest='included_product_tokens', default=os.environ.get("INCLUDED_PRODUCT_TOKENS"))
        parser.add_argument('-x', '--excludedProjectTokens', help="Excluded Project Tokens list", dest='excluded_project_tokens', default=os.environ.get("EXCLUDED_PROJECT_TOKENS"))
        parser.add_argument('-n', '--excludedProjectNamePatterns', help="ExcludedProjectNamePatterns", dest='excluded_project_name_patterns', default=os.environ.get("EXCLUDED_PROJECT_NAME_PATTERNS"))
        parser.add_argument('-g', '--analyzedProjectTag', help="Allows only analyze whether to clean up when a project contains the specific K:V tag", dest='analyzed_project_tag', default=os.environ.get("ANALYZED_PROJECT_TAG"))
        parser.add_argument('-r', '--daysToKeep', help="Number of days to keep in FilterProjectsByUpdateTime or number of copies in FilterProjectsByLastCreatedCopies", dest='days_to_keep', type=int, default=50000)
        parser.add_argument('-p', '--projectParallelismLevel', help="Project parallelism level", dest='project_parallelism_level', type=int, default=5)
        parser.add_argument('-y', '--dryRun', help="Whether to run the tool without performing anything", dest='dry_run', type=bool, default=True)
        parser.add_argument('-s', '--skipReportGeneration', help="Skip Report Generation", dest='skip_report_generation', type=bool, default=True)
        parser.add_argument('-j', '--skipProjectDeletion', help="Skip Project Generation", dest='skip_project_deletion', type=bool, default=True)
        conf = parser.parse_args()

    if conf.analyzed_project_tag:
        generate_analyzed_project_tag(conf.analyzed_project_tag)

    conf.included_product_tokens = conf.included_product_tokens.replace(" ", "").split(",") if conf.included_product_tokens else []
    conf.excluded_product_tokens = conf.excluded_product_tokens.replace(" ", "").split(",") if conf.excluded_product_tokens else []
    conf.excluded_project_tokens = conf.excluded_project_tokens.replace(" ", "").split(",") if conf.excluded_project_tokens else []
    conf.excluded_project_name_patterns = conf.excluded_project_name_patterns.split(",") if conf.excluded_project_name_patterns else []
    conf.report_types = get_reports(conf.report_types)
    conf.ws_conn = WS(url=conf.ws_url,
                      user_key=conf.ws_user_key,
                      token=conf.ws_org_token,
                      tool_details=(f"ps-{__tool_name__.replace('_', '-')}", __version__))
    return conf


def get_reports(report_types: str) -> list:
    reports_d = {}
    all_reports = WS.get_reports_meta_data(scope=ws_constants.ScopeTypes.PROJECT)

    if report_types:
        report_types_l = report_types.replace(' ', '').split(",")
        reports_to_gen_l = []
        for r in all_reports:               # Converting list of report meta data tuples to dict
            reports_d[r.name] = r

        for r_t in report_types_l:
            if r_t in reports_d.keys():
                reports_to_gen_l.append(reports_d[r_t])

    return reports_to_gen_l if report_types else all_reports


def main():
    global conf
    start_time = datetime.now()
    try:
        conf = parse_config()
    except FileNotFoundError:
        exit(-1)

    logger.info(f"Starting project cleanup in '{conf.operation_mode}' mode. Generating {len(conf.report_types)} report types with {conf.project_parallelism_level} threads")
    products_to_clean = get_products_to_archive(conf.included_product_tokens, conf.excluded_product_tokens)
    filter_class = FilterStrategy(globals()[conf.operation_mode](products_to_clean, conf))
    projects_to_archive = filter_class.execute()
    filtered_projects_to_archive = exclude_projects(projects_to_archive, conf.excluded_project_tokens, conf.excluded_project_name_patterns)
    reports_to_archive = get_reports_to_archive(filtered_projects_to_archive)
    failed_project_tokens = []

    if conf.skip_report_generation:
        logger.info("Skipping Report Generation")
    else:
        failed_project_tokens = generate_reports_m(reports_to_archive)
    if conf.skip_project_deletion:
        logger.info("Skipping Project Deletion")
    else:
        delete_projects(filtered_projects_to_archive, failed_project_tokens)

    logger.info(f"Project Cleanup has been finished. Run time: {datetime.now() - start_time}")


if __name__ == '__main__':
    main()
