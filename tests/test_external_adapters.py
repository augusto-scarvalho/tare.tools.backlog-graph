from __future__ import annotations
import json
import tempfile
from pathlib import Path
import unittest

from graph_backlog.adapters import (
    GitHubIssuesAdapter,
    LinearAdapter,
    GitLabAdapter,
    MarkdownAdapter
)
from graph_backlog.core import WorkGraph
from graph_backlog.validation import validate_work_graph
from graph_backlog.cli import main

class ExternalAdaptersTests(unittest.TestCase):
    def test_github_issues_adapter(self):
        sample_gh_issues = [
            {
                "number": 101,
                "title": "Configure Database Schema",
                "body": "Setup PostgreSQL tables and migrations.\n- [x] Run initial migration\n- [x] Seed data",
                "state": "CLOSED",
                "labels": [{"name": "cluster:database"}, {"name": "P0"}, {"name": "H0"}],
                "html_url": "https://github.com/org/repo/issues/101"
            },
            {
                "number": 102,
                "title": "Build Auth API",
                "body": "Implement JWT endpoints.\nDepends on #101\n- [ ] Sign JWT tokens\n- [ ] Refresh token flow",
                "state": "OPEN",
                "labels": [{"name": "cluster:auth"}, {"name": "priority:P1"}, {"name": "H1"}],
                "html_url": "https://github.com/org/repo/issues/102"
            },
            {
                "number": 103,
                "title": "Build Frontend Login",
                "body": "Login page interface.\n- [ ] #102: Auth API ready\nBlocks #104",
                "state": "OPEN",
                "labels": [{"name": "cluster:frontend"}, {"name": "P2"}],
                "html_url": "https://github.com/org/repo/issues/103"
            },
            {
                "number": 104,
                "title": "User Dashboard",
                "body": "Main dashboard landing page.",
                "state": "OPEN",
                "labels": [{"name": "cluster:frontend"}, {"name": "P2"}],
                "html_url": "https://github.com/org/repo/issues/104"
            }
        ]

        graph_dict = GitHubIssuesAdapter.from_issues(sample_gh_issues, id_prefix="GH-")
        
        # Validate schema and structure
        val = validate_work_graph(graph_dict)
        self.assertEqual(val["status"], "PASS", f"Validation failed: {val}")
        
        # Test Nodes
        nodes = {n["id"]: n for n in graph_dict["nodes"]}
        self.assertEqual(len(nodes), 4)
        
        self.assertEqual(nodes["GH-101"]["completion"]["status"], "DONE")
        self.assertEqual(nodes["GH-101"]["cluster"], "database")
        self.assertEqual(nodes["GH-101"]["priority"], "P0")
        self.assertEqual(nodes["GH-101"]["horizon"], "H0")
        
        self.assertEqual(nodes["GH-102"]["completion"]["status"], "NOT_DONE")
        self.assertEqual(nodes["GH-102"]["cluster"], "auth")
        self.assertEqual(nodes["GH-102"]["priority"], "P1")
        
        # Test Edges
        edges = {(e["from"], e["to"]) for e in graph_dict["edges"]}
        self.assertIn(("GH-101", "GH-102"), edges) # from Depends on #101
        self.assertIn(("GH-102", "GH-103"), edges) # from - [ ] #102
        self.assertIn(("GH-103", "GH-104"), edges) # from Blocks #104
        
        # Test WorkGraph instantiation and frontier
        wg = WorkGraph(graph_dict)
        from graph_backlog.algorithms import compute_frontier
        frontier = compute_frontier(wg)
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0]["id"], "GH-102") # GH-101 is DONE, so GH-102 is ready

    def test_linear_adapter_csv(self):
        sample_csv = """ID,Title,Description,Status,Priority,Project,Blocked by,Blocking,Labels
ENG-10,Setup Cloud Infrastructure,Deploy terraform k8s cluster,Done,Urgent,Infrastructure,,ENG-11,"devops,cloud"
ENG-11,Deploy Core Microservice,Deploy backend API,In Progress,High,Backend,ENG-10,ENG-12,"backend,api"
ENG-12,Deploy Client Web App,Deploy Next.js portal,Todo,Medium,Frontend,ENG-11,,"frontend"
"""
        graph_dict = LinearAdapter.from_csv(sample_csv)
        val = validate_work_graph(graph_dict)
        self.assertEqual(val["status"], "PASS")
        
        nodes = {n["id"]: n for n in graph_dict["nodes"]}
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes["ENG-10"]["completion"]["status"], "DONE")
        self.assertEqual(nodes["ENG-10"]["priority"], "P0")
        self.assertEqual(nodes["ENG-11"]["completion"]["status"], "PARTIAL")
        self.assertEqual(nodes["ENG-11"]["priority"], "P1")
        self.assertEqual(nodes["ENG-12"]["completion"]["status"], "NOT_DONE")
        
        edges = {(e["from"], e["to"]) for e in graph_dict["edges"]}
        self.assertIn(("ENG-10", "ENG-11"), edges)
        self.assertIn(("ENG-11", "ENG-12"), edges)

    def test_linear_adapter_json(self):
        sample_json = [
            {
                "identifier": "LIN-01",
                "title": "Database Schema Setup",
                "description": "Create Postgres models",
                "state": {"name": "Done", "type": "completed"},
                "priority": 1,
                "project": {"name": "Database"},
                "relations": [
                    {"type": "blocks", "relatedIssue": {"identifier": "LIN-02"}}
                ]
            },
            {
                "identifier": "LIN-02",
                "title": "API Gateway Route",
                "description": "Route requests to auth",
                "state": {"name": "Todo", "type": "unstarted"},
                "priority": 2,
                "project": {"name": "Gateway"},
                "relations": [
                    {"type": "blocked_by", "relatedIssue": {"identifier": "LIN-01"}}
                ]
            }
        ]
        graph_dict = LinearAdapter.from_json(sample_json)
        val = validate_work_graph(graph_dict)
        self.assertEqual(val["status"], "PASS")
        
        nodes = {n["id"]: n for n in graph_dict["nodes"]}
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes["LIN-01"]["completion"]["status"], "DONE")
        self.assertEqual(nodes["LIN-02"]["completion"]["status"], "NOT_DONE")
        
        edges = {(e["from"], e["to"]) for e in graph_dict["edges"]}
        self.assertEqual(edges, {("LIN-01", "LIN-02")})

    def test_gitlab_adapter_json(self):
        sample_gl_issues = [
            {
                "iid": 1,
                "title": "Init Repository CI/CD",
                "description": "Configure gitlab-ci.yml pipeline",
                "state": "closed",
                "labels": ["cluster::devops", "priority::P0", "horizon::H0"],
                "issue_links": [
                    {"link_type": "blocks", "target_issue": {"iid": 2}}
                ]
            },
            {
                "iid": 2,
                "title": "Build Container Image",
                "description": "Docker multi-stage build\nDepends on #1",
                "state": "opened",
                "labels": ["cluster::devops", "priority::P1", "horizon::H1"]
            }
        ]
        graph_dict = GitLabAdapter.from_issues(sample_gl_issues, id_prefix="GL-")
        val = validate_work_graph(graph_dict)
        self.assertEqual(val["status"], "PASS")
        
        nodes = {n["id"]: n for n in graph_dict["nodes"]}
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes["GL-1"]["completion"]["status"], "DONE")
        self.assertEqual(nodes["GL-2"]["completion"]["status"], "NOT_DONE")
        
        edges = {(e["from"], e["to"]) for e in graph_dict["edges"]}
        self.assertIn(("GL-1", "GL-2"), edges)

    def test_jira_adapter_csv(self):
        sample_csv = """Issue key,Summary,Description,Status,Priority,Project name,Outward issue link (Blocks),Inward issue link (Blocks),Labels
PROJ-1,Setup Database,Initial schema,Done,Highest,Infrastructure,PROJ-2,,backend
PROJ-2,Build REST API,API endpoints,In Progress,High,Backend,,PROJ-1,"api,rest"
PROJ-3,User Interface,React web app,To Do,Medium,Frontend,,,frontend
"""
        from graph_backlog.adapters import JiraAdapter
        graph_dict = JiraAdapter.from_csv(sample_csv)
        val = validate_work_graph(graph_dict)
        self.assertEqual(val["status"], "PASS")
        
        nodes = {n["id"]: n for n in graph_dict["nodes"]}
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes["PROJ-1"]["completion"]["status"], "DONE")
        self.assertEqual(nodes["PROJ-1"]["priority"], "P0")
        self.assertEqual(nodes["PROJ-2"]["completion"]["status"], "PARTIAL")
        self.assertEqual(nodes["PROJ-2"]["priority"], "P1")
        self.assertEqual(nodes["PROJ-3"]["completion"]["status"], "NOT_DONE")
        
        edges = {(e["from"], e["to"]) for e in graph_dict["edges"]}
        self.assertIn(("PROJ-1", "PROJ-2"), edges)

    def test_jira_adapter_json(self):
        sample_json = {
            "issues": [
                {
                    "key": "JIRA-100",
                    "fields": {
                        "summary": "Core Auth Module",
                        "description": "JWT tokens setup",
                        "status": {"name": "Closed", "statusCategory": {"key": "done"}},
                        "priority": {"name": "Blocker"},
                        "project": {"name": "Auth"},
                        "issuelinks": [
                            {
                                "type": {"name": "Blocks", "outward": "blocks"},
                                "outwardIssue": {"key": "JIRA-101"}
                            }
                        ]
                    }
                },
                {
                    "key": "JIRA-101",
                    "fields": {
                        "summary": "Login Screen",
                        "description": "Depends on JIRA-100",
                        "status": {"name": "Open", "statusCategory": {"key": "new"}},
                        "priority": {"name": "Major"},
                        "project": {"name": "Frontend"},
                        "issuelinks": []
                    }
                }
            ]
        }
        from graph_backlog.adapters import JiraAdapter
        graph_dict = JiraAdapter.from_json(sample_json)
        val = validate_work_graph(graph_dict)
        self.assertEqual(val["status"], "PASS")
        
        nodes = {n["id"]: n for n in graph_dict["nodes"]}
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes["JIRA-100"]["completion"]["status"], "DONE")
        self.assertEqual(nodes["JIRA-100"]["priority"], "P0")
        self.assertEqual(nodes["JIRA-101"]["completion"]["status"], "NOT_DONE")
        self.assertEqual(nodes["JIRA-101"]["priority"], "P1")
        
        edges = {(e["from"], e["to"]) for e in graph_dict["edges"]}
        self.assertIn(("JIRA-100", "JIRA-101"), edges)

    def test_cli_import_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            
            # 1. Test CLI import-github
            gh_input = tmp / "gh.json"
            gh_out = tmp / "gh-graph.json"
            gh_input.write_text(json.dumps([
                {"number": 1, "title": "Setup", "state": "closed", "body": "Initial task"},
                {"number": 2, "title": "App", "state": "open", "body": "Depends on #1"}
            ]), encoding="utf-8")
            
            ret = main(["import-github", str(gh_input), "--out", str(gh_out)])
            self.assertEqual(ret, 0)
            self.assertTrue(gh_out.exists())
            
            data = json.loads(gh_out.read_text(encoding="utf-8"))
            self.assertEqual(len(data["nodes"]), 2)
            self.assertEqual(len(data["edges"]), 1)

            # 2. Test CLI import-linear
            lin_input = tmp / "lin.csv"
            lin_out = tmp / "lin-graph.json"
            lin_input.write_text("ID,Title,Status,Priority\nLIN-1,Core,Done,Urgent\nLIN-2,API,Todo,High\n", encoding="utf-8")
            
            ret = main(["import-linear", str(lin_input), "--out", str(lin_out)])
            self.assertEqual(ret, 0)
            self.assertTrue(lin_out.exists())

            # 3. Test CLI import-gitlab
            gl_input = tmp / "gl.json"
            gl_out = tmp / "gl-graph.json"
            gl_input.write_text(json.dumps([
                {"iid": 10, "title": "DB", "state": "closed", "description": ""},
                {"iid": 20, "title": "Server", "state": "opened", "description": "/depends_on #10"}
            ]), encoding="utf-8")
            
            ret = main(["import-gitlab", str(gl_input), "--out", str(gl_out)])
            self.assertEqual(ret, 0)
            self.assertTrue(gl_out.exists())

            # 4. Test CLI import-jira
            jira_input = tmp / "jira.csv"
            jira_out = tmp / "jira-graph.json"
            jira_input.write_text("Key,Summary,Status,Priority,Outward issue link (Blocks)\nJ-1,DB,Done,Blocker,J-2\nJ-2,Web,To Do,Major,\n", encoding="utf-8")
            
            ret = main(["import-jira", str(jira_input), "--out", str(jira_out)])
            self.assertEqual(ret, 0)
            self.assertTrue(jira_out.exists())
            data_jira = json.loads(jira_out.read_text(encoding="utf-8"))
            self.assertEqual(len(data_jira["nodes"]), 2)
            self.assertEqual(len(data_jira["edges"]), 1)

            # 5. Test CLI import-md
            md_input = tmp / "tasks.md"
            md_out = tmp / "md-graph.json"
            md_input.write_text("- [x] T-1: Task One\n- [ ] T-2: Task Two (depends: T-1)\n", encoding="utf-8")
            
            ret = main(["import-md", str(md_input), "--out", str(md_out)])
            self.assertEqual(ret, 0)
            self.assertTrue(md_out.exists())

if __name__ == "__main__":
    unittest.main()
