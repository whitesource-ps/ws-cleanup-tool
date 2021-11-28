import os
import sys
from ws_sdk import ws_errors

from ws_cleanup_tool import configuration
from ws_cleanup_tool.filter_strategies import *
from ws_cleanup_tool._version import __tool_name__

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
    # projects_filter = FilterStrategy(globals()[conf.operation_mode](products_to_clean, conf))   # Creating and initiating the strategy class
    projects_filter = FilterStrategy(eval(conf.operation_mode)(products_to_clean, conf))   # Creating and initiating the strategy class

    projects_to_archive = projects_filter.execute()
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
