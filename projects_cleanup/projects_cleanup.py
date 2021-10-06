import logging
import os
import re
import sys
from configparser import ConfigParser
from datetime import datetime, timedelta
from multiprocessing import Manager
from multiprocessing.pool import ThreadPool

import ws_sdk.ws_constants
from ws_sdk import ws_constants
from ws_sdk.web import WS

file_handler = logging.FileHandler(filename='cleanup.log')
stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [file_handler, stdout_handler]
logging.basicConfig(level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
                    format='%(levelname)s %(asctime)s %(thread)d %(name)s: %(message)s',
                    handlers=handlers
                    )
logger = logging.getLogger('Project Cleanup')

c_org = None
config = None
dry_run = False
report_types = {}
archive_dir = None
project_parallelism_level = 5

PS = "ps-"
AGENT_NAME = "cleanup-tool"
AGENT_VERSION = "0.1.8"


def replace_invalid_chars(directory: str) -> str:
    for char in ws_sdk.ws_constants.INVALID_FS_CHARS:
        directory = directory.replace(char, "_")
    return directory


def get_product_to_archive() -> list:
    products_str = config['DEFAULT'].get('IncludedProductTokens')
    prod_tokens = products_str.strip().split(",") if products_str else []
    if prod_tokens:
        logging.debug(f"Product tokens to check for cleanup: {prod_tokens}")
        prods = [c_org.get_scopes(scope_type=ws_constants.PRODUCT, token=prod_t).pop() for prod_t in prod_tokens]
    else:
        logging.debug("Getting all products")
        prods = c_org.get_products()

    exc_prods_str = config['DEFAULT'].get('ExcludedProductTokens')
    excluded_prod_tokens = exc_prods_str.strip().split(",") if exc_prods_str else []
    if excluded_prod_tokens:
        logging.debug(f"Product tokens to be excluded from cleanup: {excluded_prod_tokens}")
        prods = [prod for prod in prods if prod['token'] not in excluded_prod_tokens]
    logging.debug(f"Product names for cleanup check: {[prod['name'] for prod in prods]}")

    return prods


def get_reports_to_archive() -> tuple:
    products = get_product_to_archive()
    logger.info(f"{len(products)} Products to handle out of {len(products)}")
    days_to_keep = timedelta(days=config.getint('DEFAULT', 'DaysToKeep'))
    archive_date = datetime.utcnow() - days_to_keep
    logger.info(f"Keeping {days_to_keep.days} days. Archiving projects older than {archive_date}")
    projects_to_archive, project_report_desc_list = get_projects_and_reports(archive_date, products)

    return projects_to_archive, project_report_desc_list


def get_projects_and_reports(archive_date, products) -> tuple:
    manager = Manager()
    projects_to_archive_q = manager.Queue()
    project_report_desc_list_q = manager.Queue()
    with ThreadPool(processes=project_parallelism_level) as pool:
        pool.starmap(get_prod_projects_and_reports_w, [(archive_date, prod, c_org, projects_to_archive_q, project_report_desc_list_q) for prod in products])

    projects_to_archive = []
    while not projects_to_archive_q.empty():
        projects_to_archive.append(projects_to_archive_q.get(block=True, timeout=0.05))

    project_report_desc_list = []
    while not project_report_desc_list_q.empty():
        project_report_desc_list.append(project_report_desc_list_q.get(block=True, timeout=0.05))

    logger.info(f"Found total {len(projects_to_archive)} projects to archive ({len(project_report_desc_list)} reports will be produced)")

    return projects_to_archive, project_report_desc_list


def get_prod_projects_and_reports_w(archive_date, prod, ws_conn, projects_to_archive_q, project_report_desc_list_q):
    curr_prod_proj_to_archive = []
    logger.debug(f"About to handle product: {prod['name']} token type: {type(prod['token'])}")
    curr_prod_projects = ws_conn.get_projects(product_token=prod['token'])
    logger.info(f"Handling product: {prod['name']} number of projects: {len(curr_prod_projects)}")

    for project in curr_prod_projects:
        project_time = datetime.strptime(project['lastUpdatedDate'], "%Y-%m-%d %H:%M:%S +%f")
        if project_time < archive_date:
            logger.debug(f"Project {project['name']} Token: {project['token']} Last update: {project['lastUpdatedDate']} will be archived")
            # Characters validation
            product_name = replace_invalid_chars(project['productName'])
            project_name = replace_invalid_chars(project['name'])
            project['project_archive_dir'] = os.path.join(os.path.join(archive_dir, product_name), project_name)
            curr_prod_proj_to_archive.append(project)
            projects_to_archive_q.put(project)

    logger.info(f"Found {len(curr_prod_proj_to_archive)} projects to archive on product: {prod['name']}")

    for project in curr_prod_proj_to_archive:  # Creating list of report to-be-produced meta data
        if not os.path.exists(project['project_archive_dir']):
            os.makedirs(project['project_archive_dir'])
        for report_type in report_types.keys():
            project_report = project.copy()
            project_report['report_type'] = report_type
            project_report['report_full_name'] = os.path.join(project_report['project_archive_dir'],
                                                              report_types[report_type])
            project_report_desc_list_q.put(project_report)


def generate_reports_manager(reports_desc_list: list) -> list:
    global project_parallelism_level
    manager = Manager()
    failed_proj_tokens_q = manager.Queue()
    with ThreadPool(processes=project_parallelism_level) as pool:
        pool.starmap(worker_generate_report,
                     [(report_desc, c_org, failed_proj_tokens_q) for report_desc in reports_desc_list])

    failed_projects = []
    while not failed_proj_tokens_q.empty():
        failed_projects.append(failed_proj_tokens_q.get(block=True, timeout=0.05))

    if failed_projects:
        logger.warning(f"{len(failed_projects)} projects were failed to archive")

    return failed_projects


def worker_generate_report(report_desc: dict, connector: WS, w_f_proj_tokens_q) -> None:
    logger.debug(f"Running report {report_desc['report_type']} on project: {report_desc['name']}. location: {report_desc['report_full_name']}")
    method_name = f"get_{report_desc['report_type']}"
    try:
        method_to_call = getattr(WS, method_name)
        global dry_run
        if dry_run:
            logger.info(f"[DRY_RUN] Generating report: {report_desc['project_archive_dir']}")
        else:
            logger.debug(f"Generating report: {report_desc['project_archive_dir']}")
            report = method_to_call(connector, token=report_desc['token'], report=True)
            f = open(report_desc['report_full_name'], 'bw')  # Creating the reports files in the ReportsDir
            f.write(report)
    except AttributeError:
        logger.error(f"report: {method_name} was not found")
    except Exception:
        logger.exception(f"Error producing report: {report_desc['report_type']} on project {report_desc['name']}. Project will not be deleted.")
        w_f_proj_tokens_q.put(report_desc['token'])


def delete_projects(projects_to_archive: list, failed_project_toks: list) -> None:
    projects_to_delete = projects_to_archive.copy()
    for project in projects_to_archive:
        if project['token'] in failed_project_toks:
            projects_to_delete.remove(project)
    logger.info(f"Out of {len(projects_to_archive)} projects, {len(projects_to_delete)} projects will be deleted")

    if projects_to_delete:
        global dry_run, c_org
        with ThreadPool(processes=1) as thread_pool:
            thread_pool.starmap(worker_delete_project, [(c_org, project, dry_run) for project in projects_to_delete])
        logger.info(f"{len(projects_to_archive)} projects deleted")


def worker_delete_project(conn, project, w_dry_run):
    if w_dry_run:
        logger.info(f"[DRY_RUN] Deleting project: {project['name']} Token: {project['token']}")
    else:
        logger.info(f"Deleting project: {project['name']} Token: {project['token']}")
        conn.delete_scope(project['token'])


def parse_config(config_file: str):
    global config, dry_run, report_types, archive_dir, project_parallelism_level
    config = ConfigParser()
    config.optionxform = str
    config.read(config_file)

    project_parallelism_level = config['DEFAULT'].getint('ProjectParallelismLevel', project_parallelism_level)
    dry_run = config['DEFAULT'].getboolean('DryRun', False)
    archive_dir = config['DEFAULT'].get('ReportsDir', os.getcwd())
    reports = config['DEFAULT']['Reports'].replace(' ', '').split(",")
    for report in reports:  # Generate SDK methods from the conf report list
        report_types[re.sub('_report.+', '', report)] = report
    logger.info(f"Generating {len(report_types)} report types with {project_parallelism_level} threads")


def parse_cli():
    params = {}
    for arg in [('ws_user_key', 2), ('ws_org_token', 3), ('ws_url', 4)]:
        try:
            params[arg[0]] = sys.argv[arg[1]]
        except IndexError:
            params[arg[0]] = None

    return params


if __name__ == '__main__':
    start_time = datetime.now()
    if len(sys.argv) > 1:
        conf_file = sys.argv[1]
    else:
        conf_file = 'params.config'
    logger.info(f"Using configuration file: {conf_file}")
    parse_config(conf_file)
    alt_params = parse_cli()

    c_org = WS(url=config['DEFAULT'].get('WsUrl', alt_params.get('ws_url')),
               user_key=config['DEFAULT'].get('UserKey', alt_params.get('ws_user_key')),
               token=config['DEFAULT'].get('OrgToken', alt_params.get('ws_org_token')),
               tool_details=(PS + AGENT_NAME, AGENT_VERSION))
    if dry_run:
        logger.info("Running in DRY_RUN mode. Project will not be deleted and reports will not be generated!!!")
    proj_to_archive, reports_to_archive = get_reports_to_archive()
    failed_project_tokens = []
    if config['DEFAULT'].getboolean('SkipReportGeneration', False):
        logger.info("Skipping Report Generation")
    else:
        failed_project_tokens = generate_reports_manager(reports_to_archive)
    if config['DEFAULT'].getboolean('SkipProjectDeletion', False):
        logging.info("Skipping Project Deletion")
    else:
        delete_projects(proj_to_archive, failed_project_tokens)

    logger.info(f"Project Cleanup finished. Run time: {datetime.now() - start_time}")
