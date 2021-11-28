import logging
from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from multiprocessing import Manager
from multiprocessing.pool import ThreadPool

from ws_sdk import WS, ws_constants


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
