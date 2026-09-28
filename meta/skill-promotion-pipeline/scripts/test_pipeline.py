#!/usr/bin/env python3
"""Self-test for pipeline.py: every gate is shown to PASS on good input and FAIL on seeded bad input.

Run: python scripts/test_pipeline.py   (stdlib only; works in a temp dir, deletes only what it made)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(HERE, "pipeline.py")

MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy..."
ELV2 = "Elastic License 2.0\n\nAcceptance. By using the software, you agree to all of the terms..."
BODY = ("Always run the migration in a transaction and check the row count before commit. "
        "If the count differs from the dry run, roll back and report the difference to the user. ") * 6
SHEETS_BODY = " ".join("pivot%d formula%d chart%d" % (i, i, i) for i in range(80))
HTML_BODY = " ".join("guide%d step%d" % (i, i) for i in range(80))
GPL3 = ("GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007 Copyright (C) 2007 Free Software Foundation "
        + "terms " * 200 + "13. Use with the GNU Affero General Public License. Notwithstanding any other provision")
MPL2 = ("Mozilla Public License Version 2.0 1. Definitions " + "terms " * 200
        + "1.12. Secondary License means either the GNU General Public License, Version 2.0, the GNU Lesser "
        "General Public License, Version 2.1, the GNU Affero General Public License, Version 3.0")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def skill_md(name, desc, body="Body."):
    return "---\nname: %s\ndescription: \"%s\"\n---\n\n# %s\n\n%s\n" % (name, desc, name, body)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="skill-pipeline-test-")
        self.src = os.path.join(self.tmp, "upstream")
        self.reg = os.path.join(self.tmp, "registry")
        os.makedirs(self.reg)
        # an MIT pack with two skills, one of which bundles its own Elastic-licensed tree
        write(os.path.join(self.src, "LICENSE"), MIT)
        write(os.path.join(self.src, "skills", "db-migrations", "SKILL.md"), skill_md("db-migrations", "Run migrations.", BODY))
        write(os.path.join(self.src, "skills", "db-migrations", "references", "rollback.md"), "Rollback notes.\n")
        write(os.path.join(self.src, "skills", "db-migrations", "references", "guide.html"),
              "<html><body><p>%s</p></body></html>\n" % HTML_BODY)
        write(os.path.join(self.src, "skills", "DB_Migrations", "SKILL.md"), skill_md("DB_Migrations", "Other copy."))
        write(os.path.join(self.src, "vendor", "sheets", "LICENSE.txt"), ELV2)
        write(os.path.join(self.src, "vendor", "sheets", "SKILL.md"), skill_md("sheets", "Spreadsheets.", SHEETS_BODY))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, *args, root=None, cwd=None):
        r = subprocess.run([sys.executable, PIPELINE, "--root", root or self.reg] + list(args),
                           capture_output=True, text=True, cwd=cwd)
        return r.returncode, r.stdout + r.stderr

    def manifest(self):
        with open(os.path.join(self.reg, "archive", "manifest.jsonl"), encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def capture_and_cluster(self):
        code, out = self.run_cli("capture", self.src, "--origin", "example/pack")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("clusters")
        self.assertEqual(code, 0, out)
        return {r["name"]: r for r in self.manifest()}

    def curate(self, folder="data/db-migrations", cite=True):
        rows = {r["name"]: r for r in self.manifest()}
        oid = rows["db-migrations"]["id"]
        write(os.path.join(self.reg, folder, "SKILL.md"),
              skill_md(folder.rsplit("/", 1)[-1], "Safe database migrations. Use when migrating a schema.",
                       " ".join("original%d guidance" % i for i in range(60))))
        lines = ["name: " + folder.rsplit("/", 1)[-1], "version: 1.0.0", "sources:"]
        if cite:
            lines.append("- archive/objects/%s/SKILL.md" % oid)
        lines += ["provenance:", "- db-migrations"]
        write(os.path.join(self.reg, folder, "skill.yaml"), "\n".join(lines) + "\n")
        return oid

    # --- capture / clusters ---
    def test_capture_licence_nearest_wins_and_is_idempotent(self):
        rows = self.capture_and_cluster()
        self.assertEqual(rows["db-migrations"]["licence"], "MIT")
        self.assertTrue(rows["db-migrations"]["licence_clear"])
        self.assertEqual(rows["sheets"]["licence"], "ELv2")
        self.assertFalse(rows["sheets"]["licence_clear"])
        oid = rows["db-migrations"]["id"]
        self.assertTrue(os.path.isfile(os.path.join(self.reg, "archive", "objects", oid, "references", "rollback.md")))
        code, out = self.run_cli("capture", self.src, "--origin", "example/pack")
        self.assertEqual(code, 0, out)
        self.assertIn("new: 0", out)
        self.assertEqual(len(self.manifest()), 3)

    def test_clusters_group_by_normalised_name(self):
        self.capture_and_cluster()
        with open(os.path.join(self.reg, "archive", "clusters.json"), encoding="utf-8") as fh:
            clusters = json.load(fh)
        self.assertEqual(len(clusters["db-migrations"]), 2)

    # --- provenance ---
    def test_provenance_passes_on_good_citation(self):
        self.capture_and_cluster()
        self.curate()
        code, out = self.run_cli("provenance", "--deep")
        self.assertEqual(code, 0, out)
        self.assertIn("archive citations checked: 1", out)

    def test_provenance_fails_when_nothing_checked(self):
        self.capture_and_cluster()
        self.curate(cite=False)
        code, out = self.run_cli("provenance")
        self.assertEqual(code, 1, out)
        self.assertIn("checked 0", out)

    def test_provenance_fails_on_dangling_citation(self):
        self.capture_and_cluster()
        oid = self.curate()
        os.remove(os.path.join(self.reg, "archive", "objects", oid, "SKILL.md"))
        code, out = self.run_cli("provenance")
        self.assertEqual(code, 1, out)
        self.assertIn("does not exist", out)

    def test_provenance_deep_catches_edited_archive(self):
        rows = self.capture_and_cluster()
        self.curate()
        oid = rows["sheets"]["id"]
        write(os.path.join(self.reg, "archive", "objects", oid, "SKILL.md"), "edited\n")
        code, out = self.run_cli("provenance", "--deep")
        self.assertEqual(code, 1, out)
        self.assertIn("content changed", out)

    # --- ledger ---
    def test_ledger_append_then_refuses_same_batch(self):
        self.capture_and_cluster()
        self.curate()
        batch = os.path.join(self.tmp, "batch-001.json")
        write(batch, json.dumps([
            {"cluster": "db-migrations", "verdict": "new", "target": "data/db-migrations"},
            {"cluster": "sheets", "verdict": "skip", "note": "Elastic License 2.0 - copy nothing"}]))
        code, out = self.run_cli("ledger-append", batch, "--batch", "001")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("ledger-append", batch, "--batch", "001")
        self.assertEqual(code, 1, out)
        self.assertIn("refusing to append twice", out)
        code, out = self.run_cli("status")
        self.assertIn("curated 1", out)
        self.assertIn("skipped 1", out)

    def test_ledger_refuses_bad_rows(self):
        self.capture_and_cluster()
        batch = os.path.join(self.tmp, "batch-bad.json")
        write(batch, json.dumps([
            {"cluster": "db-migrations", "verdict": "merge", "target": "data/does-not-exist"},
            {"cluster": "sheets", "verdict": "skip"},
            {"cluster": "no-such-cluster", "verdict": "maybe"}]))
        code, out = self.run_cli("ledger-append", batch, "--batch", "002")
        self.assertEqual(code, 1, out)
        for needle in ("has no SKILL.md", "needs a reason", "not in archive/clusters.json", "verdict must be"):
            self.assertIn(needle, out)
        self.assertFalse(os.path.exists(os.path.join(self.reg, "decisions.jsonl")))

    def test_status_counts_cited_cluster_as_covered(self):
        self.capture_and_cluster()
        self.curate()
        code, out = self.run_cli("status", "--list", "open")
        self.assertEqual(code, 0, out)
        self.assertIn("covered 1", out)
        self.assertIn("sheets", out)

    # --- index ---
    def test_index_passes_then_refuses_bad_frontmatter(self):
        self.capture_and_cluster()
        self.curate()
        code, out = self.run_cli("index")
        self.assertEqual(code, 0, out)
        self.assertIn("1 skills", out)
        write(os.path.join(self.reg, "data", "misnamed", "SKILL.md"), skill_md("other-name", "x" * 1100))
        os.remove(os.path.join(self.reg, "registry-index.json"))
        code, out = self.run_cli("index")
        self.assertEqual(code, 1, out)
        self.assertIn("!= folder name", out)
        self.assertIn("max 1024", out)
        self.assertFalse(os.path.exists(os.path.join(self.reg, "registry-index.json")))

    def test_index_ignores_archive_objects(self):
        self.capture_and_cluster()
        self.curate()
        code, out = self.run_cli("index")
        self.assertIn("1 skills", out)  # the 3 archived SKILL.md files are not curated skills

    # --- overlap ---
    def test_overlap_passes_on_rewrite_and_fails_on_paste(self):
        self.capture_and_cluster()
        self.curate()
        code, out = self.run_cli("overlap", os.path.join(self.reg, "data", "db-migrations"))
        self.assertEqual(code, 0, out)
        write(os.path.join(self.reg, "data", "db-migrations", "references", "pasted.md"), BODY)
        code, out = self.run_cli("overlap", os.path.join(self.reg, "data", "db-migrations"))
        self.assertEqual(code, 1, out)
        self.assertIn("fold, don't paste", out)

    def test_overlap_strict_against_unclear_licence(self):
        rows = self.capture_and_cluster()
        self.curate()
        yml = os.path.join(self.reg, "data", "db-migrations", "skill.yaml")
        with open(yml, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace("sources:\n", "sources:\n- archive/objects/%s/SKILL.md\n" % rows["sheets"]["id"])
        write(yml, text)
        # 10% of one file copied from the Elastic-licensed tree: under --max, over --max-unclear
        mine = " ".join("sheetword%d" % i for i in range(300)) + " "
        write(os.path.join(self.reg, "data", "db-migrations", "references", "sheets.md"), mine + SHEETS_BODY[:180])
        code, out = self.run_cli("overlap", os.path.join(self.reg, "data", "db-migrations"))
        self.assertEqual(code, 1, out)
        self.assertIn("licence is not clear", out)

    def test_overlap_catches_uncited_unclear_paste(self):
        # the writer copied from the Elastic-licensed tree and (of course) did not cite it
        self.capture_and_cluster()
        self.curate()
        skill = os.path.join(self.reg, "data", "db-migrations")
        code, out = self.run_cli("overlap", skill)
        self.assertEqual(code, 0, out)
        mine = " ".join("sheetword%d" % i for i in range(300)) + " "
        write(os.path.join(skill, "references", "sheets.md"), mine + SHEETS_BODY[:180])
        code, out = self.run_cli("overlap", skill)
        self.assertEqual(code, 1, out)
        self.assertIn("uncited overlap", out)
        self.assertIn("ELv2", out)
        self.assertIn("e.g. \"", out)  # the shared phrases are shown, so a verifier can rule on them
        # archive shingles are cached per object id; a second run reads the cache and agrees
        cache = os.path.join(self.reg, "archive", "cache", "shingles-n8")
        self.assertTrue(os.listdir(cache))
        code2, out2 = self.run_cli("overlap", skill)
        self.assertEqual((code2, out2), (code, out))

    def test_overlap_runs_for_uncited_fresh_skill(self):
        # a skill written fresh (no archive sources) is still checked against unclear-licence objects
        self.capture_and_cluster()
        folder = os.path.join(self.reg, "data", "spreadsheets")
        write(os.path.join(folder, "SKILL.md"), skill_md("spreadsheets", "Sheets.", SHEETS_BODY))
        code, out = self.run_cli("overlap", folder)
        self.assertEqual(code, 1, out)
        self.assertIn("uncited overlap", out)

    # --- the shingle cache can never hide a paste ---
    def sheets_paste_setup(self):
        rows = self.capture_and_cluster()
        self.curate()
        skill = os.path.join(self.reg, "data", "db-migrations")
        oid = rows["sheets"]["id"]
        obj_md = os.path.join(self.reg, "archive", "objects", oid, "SKILL.md")
        cache = os.path.join(self.reg, "archive", "cache", "shingles-n8", oid + ".json")
        return skill, obj_md, cache

    def test_cache_edit_restore_then_paste_still_fails(self):
        skill, obj_md, cache = self.sheets_paste_setup()
        with open(obj_md, encoding="utf-8") as fh:
            original = fh.read()
        write(obj_md, "edited to something else entirely, nothing like the spreadsheet body at all\n")
        code, out = self.run_cli("overlap", skill)  # caches the EDITED text, and says so
        self.assertEqual(code, 1, out)
        self.assertIn("edited since capture", out)
        write(obj_md, original)  # restore, as the error tells you to
        code, out = self.run_cli("provenance", "--deep")
        self.assertEqual(code, 0, out)
        write(os.path.join(skill, "references", "sheets.md"), SHEETS_BODY)  # paste the original body
        code, out = self.run_cli("overlap", skill)
        self.assertEqual(code, 1, out)
        self.assertIn("uncited overlap", out)

    def test_tampered_or_truncated_cache_is_rebuilt(self):
        skill, obj_md, cache = self.sheets_paste_setup()
        write(os.path.join(skill, "references", "sheets.md"), SHEETS_BODY)
        code, out = self.run_cli("overlap", skill)
        self.assertEqual(code, 1, out)
        for bad in ('{"SKILL.md": []}', '{"tree": "x", "files": {"SKILL.md": []}}', '{"tree": "', "[]"):
            write(cache, bad)
            code, out = self.run_cli("overlap", skill)
            self.assertEqual(code, 1, out)
            self.assertIn("uncited overlap", out)
            self.assertNotIn("Traceback", out)
        # an entry with the right tree hash but hand-emptied lists fails its own digest
        with open(cache, encoding="utf-8") as fh:
            entry = json.load(fh)
        entry["files"] = {k: [] for k in entry["files"]}
        write(cache, json.dumps(entry))
        code, out = self.run_cli("overlap", skill)
        self.assertEqual(code, 1, out)
        self.assertIn("uncited overlap", out)

    def test_provenance_deep_drops_cache_of_changed_object(self):
        skill, obj_md, cache = self.sheets_paste_setup()
        self.run_cli("overlap", skill)
        self.assertTrue(os.path.isfile(cache))
        write(obj_md, "edited\n")
        code, out = self.run_cli("provenance", "--deep")
        self.assertEqual(code, 1, out)
        self.assertFalse(os.path.exists(cache))

    def test_cited_non_markdown_source_is_compared(self):
        rows = self.capture_and_cluster()
        self.curate()
        skill = os.path.join(self.reg, "data", "db-migrations")
        oid = rows["db-migrations"]["id"]
        yml = os.path.join(skill, "skill.yaml")
        with open(yml, encoding="utf-8") as fh:
            text = fh.read()
        write(yml, text.replace("sources:\n", "sources:\n- archive/objects/%s/references/guide.html\n" % oid))
        write(os.path.join(skill, "references", "guide.md"), HTML_BODY)
        code, out = self.run_cli("overlap", skill)
        self.assertEqual(code, 1, out)
        self.assertIn("references/guide.html", out)
        self.assertIn("fold, don't paste", out)

    # --- paths relative to --root, clean errors ---
    def test_commands_resolve_paths_against_root(self):
        self.capture_and_cluster()
        self.curate()
        write(os.path.join(self.reg, "work", "batch-001", "decisions.json"), json.dumps(
            [{"cluster": "db-migrations", "verdict": "new", "target": "data/db-migrations"}]))
        # run from the registry's parent with a relative --root and paths relative to the root
        code, out = self.run_cli("ledger-append", "work/batch-001/decisions.json", "--batch", "001",
                                 root="registry", cwd=self.tmp)
        self.assertEqual(code, 0, out)
        code, out = self.run_cli("overlap", "data/db-migrations", root="registry", cwd=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("cited archive files: 1", out)
        # the same paths written relative to the current directory also work
        code, out = self.run_cli("overlap", "registry/data/db-migrations", root="registry", cwd=self.tmp)
        self.assertEqual(code, 0, out)

    def test_missing_paths_fail_cleanly(self):
        self.capture_and_cluster()
        code, out = self.run_cli("ledger-append", "work/nope.json", "--batch", "009")
        self.assertEqual(code, 1, out)
        self.assertIn("decisions file not found", out)
        self.assertNotIn("Traceback", out)
        code, out = self.run_cli("overlap", "data/nope")
        self.assertEqual(code, 1, out)
        self.assertIn("skill folder not found", out)
        self.assertNotIn("Traceback", out)


class UnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True  # importing must not leave __pycache__ in the skill folder
        sys.path.insert(0, HERE)
        import pipeline
        cls.p = pipeline

    def test_fallback_parser_flow_lists(self):
        d = self.p.parse_simple_yaml("\n".join(["name: x", "sources: []", 'provenance: [a, "b c"]', "version: 1.0.0"]))
        self.assertEqual(d["sources"], [])
        self.assertEqual(d["provenance"], ["a", "b c"])
        self.assertEqual(d["version"], "1.0.0")

    def test_licence_classifier_reads_title_first(self):
        self.assertEqual(self.p.classify_licence(GPL3), "GPL")
        self.assertEqual(self.p.classify_licence(MPL2), "MPL-2.0")
        self.assertEqual(self.p.classify_licence(MIT), "MIT")
        self.assertEqual(self.p.classify_licence(ELV2), "ELv2")
        self.assertEqual(self.p.classify_licence("Copyright 2025 Someone. All rights reserved."), "proprietary")

    def test_licence_classifier_fails_closed_on_mixed_files(self):
        full_mit = MIT + " " + "terms " * 150 + "THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND."
        mit_plus_elastic = full_mit + ("\n\nFiles under the ee/ directory are licensed under the "
                                       "Elastic License 2.0; see ee/LICENSE.")
        preamble_mit_busl = ("Portions of this repository are licensed as follows:\n\n" + full_mit
                             + "\n\nThe skills/ directory is licensed under the Business Source License 1.1.")
        self.assertEqual(self.p.classify_licence(mit_plus_elastic), "mixed:MIT+ELv2")
        self.assertEqual(self.p.classify_licence(preamble_mit_busl), "mixed:MIT+BUSL")
        self.assertEqual(self.p.classify_licence(full_mit), "MIT")  # pure permissive stays clear

    def test_source_available_addenda_are_not_clear(self):
        full_mit = MIT + " " + "terms " * 150 + "THE SOFTWARE IS PROVIDED AS IS."
        apache = "Apache License Version 2.0, January 2004 " + "terms " * 150
        cases = {
            full_mit + ' "Commons Clause" License Condition v1.0. The Software is provided to you by the '
                       "Licensor under the License, as defined below, subject to the following condition.":
                "mixed:MIT+Commons-Clause",
            full_mit + " This component is licensed under the Server Side Public License v1.": "mixed:MIT+SSPL",
            apache + " Files in pro/ are under the PolyForm Noncommercial License 1.0.0.": "mixed:Apache-2.0+PolyForm",
            full_mit + " The ee/ folder is under the Functional Source License, Version 1.1.": "mixed:MIT+FSL",
            full_mit + " Enterprise files: Sustainable Use License.": "mixed:MIT+SUL",
            full_mit + " Some connectors: Confluent Community License Version 1.0.": "mixed:MIT+Confluent",
        }
        for text, label in cases.items():
            got = self.p.classify_licence(text)
            self.assertEqual(got, label)
            self.assertNotIn(got, self.p.PERMISSIVE)

    def test_bundled_gpl_text_gets_an_honest_mixed_label(self):
        # BSD code bundling a full GPLv3 text (which names the AGPL and LGPL in its body): not "AGPL"
        bsd = ("Copyright (c) 2005 Example Developers. Redistribution and use in source and binary forms, "
               "with or without modification, are permitted " + "terms " * 150)
        tail = " use the GNU Lesser General Public License instead of this License."
        label = self.p.classify_licence(bsd + " " + GPL3 + tail)
        self.assertEqual(label, "mixed:BSD+GPL-family")
        self.assertNotIn(label, self.p.PERMISSIVE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
