import unittest
from unittest import TestCase
import ws_sdk

from ws_cleanup_tool import cleanup_tool, _version


class TestProjectsCleanup(TestCase):
    def setUp(self):
        self.dry_run = True
        self.logger_name = _version.__tool_name__
        self.project = {'name': 'NAME', 'token': 'TOKEN'}
        self.report_desc = {'report_type': "report_type", 'name': 'NAME', 'report_full_name': 'REPORT_FULL_NAME'}
        self.conn = cleanup_tool.WS(url="app",
                                    user_key="abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrstuvwxyz12",
                                    token="ORG_TOKEN",
                                    token_type=ws_sdk.ws_constants.ORGANIZATION)

    # @patch('getattr')
    # def test_worker_generate_report_method(self, mock_getattr):
    #     mock_getattr.return_value = "method"
    #     res = projects_cleanup.worker_generate_report(self.report_desc, "connector", "W_F_PROJ_TOKENS_Q")
    #
    # def test_worker_generate_report_method_not_found(self):
    #     with self.assertRaises(AttributeError):
    #         connector = Mock()
    #         projects_cleanup.worker_generate_report(self.report_desc, connector, "W_F_PROJ_TOKENS_Q")

    # @patch('ws_sdk.web.WS.delete_scope')
    # def test_delete_projects(self, mock_delete_scope):
    #     proj_to_archive = [self.project]
    #     failed_project_toks = []
    #     log_level = 'INFO'
    #     projects_cleanup.delete_projects(proj_to_archive, failed_project_toks)
    #     with self.assertLogs(self.logger_name, level=log_level) as cm:
    #         projects_cleanup.worker_delete_project(self.conn, self.project, self.dry_run)
    #         self.assertEqual(cm.output, [f"{log_level}:{self.logger_name}:Out of {len(proj_to_archive)} projects, {len(projects_to_delete)} projects will be deleted"])

    # def test_worker_delete_project_dry_run(self):
    #     log_level = 'INFO'
    #     with self.assertLogs(self.logger_name, level=log_level) as cm:
    #         cleanup_tool.worker_delete_project(self.conn, self.project, self.dry_run)
    #         self.assertIn(cm.output, ["Cleanup:[DRY_RUN] Deleting project: NAME Token: TOKEN"])


if __name__ == '__main__':
    unittest.main()
