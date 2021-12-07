import logging
import os
import sys
from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from multiprocessing import Manager
from multiprocessing.pool import ThreadPool

from ws_sdk import ws_errors, WS, ws_constants

from ws_cleanup_tool._version import __tool_name__
from ws_cleanup_tool.config import configuration

skip_report_generation = bool(os.environ.get("SKIP_REPORT_GENERATION", 0))
skip_project_deletion = bool(os.environ.get("SKIP_PROJECT_DELETION", 0))

logging.basicConfig(level=logging.DEBUG if bool(os.environ.get("DEBUG", "false")) is True else logging.INFO,
                    handlers=[logging.StreamHandler(stream=sys.stdout)],
                    format='%(levelname)s %(asctime)s %(thread)d %(name)s: %(message)s',
                    datefmt='%y-%m-%d %H:%M:%S')
logger = logging.getLogger(__tool_name__)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('root').setLevel(logging.INFO)

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
            product_name = replace_invalid_chars(project['productName'])
            project_name = replace_invalid_chars(project['name'])
            project['project_archive_dir'] = os.path.join(os.path.join(conf.archive_dir, product_name), project_name)

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
            logging.debug(f"Project {project['name']} is valid")
        elif self.should_filter_by_tag and is_tag_exist(project):
            logging.debug(f"Project {project['name']} contains appropriate key:value pair: {self.conf.analyzed_project_tag_t}")
        else:
            logging.debug(f"Project {project['name']} does not contain appropriate key:value pair: {self.conf.analyzed_project_tag_t}")
            ret = False

        return ret


class FilterProjectsByUpdateTime(FilterProjectsInt):
    def get_projects_to_archive(self) -> list:
        days_to_keep = timedelta(days=self.conf.to_keep)
        archive_date = datetime.utcnow() - days_to_keep
        logging.info(f"Keeping {days_to_keep.days} days. Archiving projects older than {archive_date}")

        manager = Manager()
        projects_to_archive_q = manager.Queue()
        with ThreadPool(processes=self.conf.project_parallelism_level) as pool:
            pool.starmap(self.get_projects_to_archive_w,
                         [(archive_date, prod, self.conf.ws_conn, projects_to_archive_q) for prod in self.products_to_clean])
        return extract_from_q(projects_to_archive_q)

    def get_projects_to_archive_w(self, archive_date, prod, ws_conn, projects_to_archive_q):
        curr_prod_projects = ws_conn.get_projects(product_token=prod['token'])
        logging.info(f"Handling product: {prod['name']} number of projects: {len(curr_prod_projects)}")

        for project in curr_prod_projects:
            project_time = datetime.strptime(project['lastUpdatedDate'], "%Y-%m-%d %H:%M:%S +%f")
            if project_time < archive_date and self.is_valid_project(project):
                logging.debug(f"Project {project['name']} Token: {project['token']} Last update: {project['lastUpdatedDate']} will be archived")
                projects_to_archive_q.put(project)


class FilterProjectsByLastCreatedCopies(FilterProjectsInt):
    def get_projects_to_archive(self) -> list:
        logging.info(f"Keeping last recent {self.conf.to_keep} projects. Archiving the rest")
        manager = Manager()
        projects_to_archive_q = manager.Queue()
        with ThreadPool(processes=self.conf.project_parallelism_level) as pool:
            pool.starmap(self.get_projects_to_archive_w,
                         [(prod['token'], self.conf.ws_conn, projects_to_archive_q) for prod in self.products_to_clean])
        projects_to_archive = extract_from_q(projects_to_archive_q)

        if not projects_to_archive:
            logging.info("No projects to archive were found")

        return projects_to_archive

    def get_projects_to_archive_w(self, product_token: str, ws_conn: WS, projects_to_archive_q):
        projects = ws_conn.get_projects(product_token=product_token, sort_by=ws_constants.ScopeSorts.UPDATE_TIME)
        filtered_projects = [project for project in projects if self.is_valid_project(project)]
        if len(filtered_projects) > self.conf.to_keep:
            index = len(filtered_projects) - self.conf.to_keep
            last_projects = filtered_projects[:index]
            logging.debug(f"Total {len(filtered_projects)}. Archiving first {index}")
            projects_to_archive_q.put(last_projects)
        else:
            logging.debug(f"Total {len(filtered_projects)}. Archiving none")


def extract_from_q(projects_to_archive_q):
    projects_to_archive = []
    while not projects_to_archive_q.empty():
        item = projects_to_archive_q.get(block=True, timeout=0.05)
        projects_to_archive.append(item) if isinstance(item, dict) else projects_to_archive.extend(item)

    return projects_to_archive


def get_reports_to_archive(projects_to_archive: list) -> list:
    project_reports_desc_list = []

    for project in projects_to_archive:  # Creating list of report to-be-produced meta data
        if not os.path.exists(project['project_archive_dir']):
            os.makedirs(project['project_archive_dir'])

        for report in conf.reports:
            curr_project_report = project.copy()
            curr_project_report['report'] = report

            project_reports_desc_list.append(curr_project_report)

    logger.info(f"Found total {len(projects_to_archive)} projects to archive ({len(project_reports_desc_list)} reports will be produced)")

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
        logger.warning(f"{len(failed_projects)} projects were failed to archive")

    return failed_projects


def generate_report_w(report_desc: dict, connector: WS, w_f_proj_tokens_q) -> None:
    def get_suffix(entity):     # Handling case where list of 2 suffices returns
        return entity if isinstance(entity, str) else entity[0]

    report_name = f"{report_desc['report'].name}.{get_suffix(report_desc['report'].bin_sfx)}"
    report_full_path = os.path.join(report_desc['project_archive_dir'], report_name)
    if conf.dry_run:
        logger.info(f"[DRY_RUN] Generating report: '{report_full_path}' project: '{report_desc['name']}'")
    else:
        logger.debug(f"Generating report: '{report_full_path}' on project: '{report_desc['name']}'")
        try:
            report = report_desc['report'].func(connector, token=report_desc['token'], report=True)
            f = open(report_full_path, 'bw')
            if not report:
                report = bytes()
            f.write(report)
        except ws_errors.WsSdkServerError or OSError:
            logger.exception(f"Error producing report: '{report_desc['report_type']}' on project {report_desc['name']}. Project will not be deleted.")
            w_f_proj_tokens_q.put(report_desc['token'])


def delete_projects(projects_to_archive: list, failed_project_tokens: list) -> None:
    projects_to_delete = projects_to_archive.copy()
    for project in projects_to_archive:
        if project['token'] in failed_project_tokens:
            projects_to_delete.remove(project)
    logger.info(f"Out of {len(projects_to_archive)} projects, {len(projects_to_delete)} projects will be deleted")

    if projects_to_delete:
        with ThreadPool(processes=1) as thread_pool:
            thread_pool.starmap(worker_delete_project, [(conf.ws_conn, project, conf.dry_run) for project in projects_to_delete])
        logger.info(f"{len(projects_to_archive)} projects deleted")


def worker_delete_project(conn, project, w_dry_run):
    if w_dry_run:
        logger.info(f"[DRY_RUN] Deleting project: {project['name']} Token: {project['token']}")
    else:
        logger.info(f"Deleting project: {project['name']} Token: {project['token']}")
        conn.delete_scope(project['token'])


def main():
    global conf
    start_time = datetime.now()
    try:
        conf = configuration.parse_config()
    except FileNotFoundError:
        exit(-1)

    logger.info(f"Starting project cleanup in {conf.operation_mode} archive mode. Generating {len(conf.reports)} report types with {conf.project_parallelism_level} threads")
    products_to_clean = get_products_to_archive(conf.included_product_tokens, conf.excluded_product_tokens)
    # filter_class = FilterStrategy(eval(conf.operation_mode)(products_to_clean, conf))
    filter_class = FilterStrategy(globals()[conf.operation_mode](products_to_clean, conf))
    projects_to_archive = filter_class.execute()
    reports_to_archive = get_reports_to_archive(projects_to_archive)
    failed_project_tokens = []

    if skip_report_generation:
        logger.info("Skipping Report Generation")
    else:
        failed_project_tokens = generate_reports_m(reports_to_archive)
    if skip_project_deletion:
        logger.info("Skipping Project Deletion")
    else:
        delete_projects(projects_to_archive, failed_project_tokens)

    logger.info(f"Project Cleanup finished. Run time: {datetime.now() - start_time}")


if __name__ == '__main__':
    main()

