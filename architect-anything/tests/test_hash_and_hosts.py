import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import install as installer
from aa_inventory import compare_inventory, inventory
from aa_model import digest, digest_matches, read_json, text_digest, validate
from aa_render import publish
from fixture_factory import create_source, sample_report


class TextDigest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.temp = self._temp.name
        self.addCleanup(self._temp.cleanup)

    def write(self, name, data):
        path = Path(self.temp)/name
        path.write_bytes(data)
        return path

    def test_crlf_and_lf_text_agree(self):
        lf = self.write("a.txt", b"one\ntwo\nthree\n")
        crlf = self.write("b.txt", b"one\r\ntwo\r\nthree\r\n")
        self.assertEqual(text_digest(lf), text_digest(crlf))
        self.assertEqual(text_digest(lf), digest(lf))  # LF files keep their historical hash
        self.assertNotEqual(digest(lf), digest(crlf))

    def test_crlf_split_across_the_read_block_boundary(self):
        size = 1024 * 1024
        lf = self.write("a.txt", b"x"*(size-1)+b"\n"+b"tail\n")
        crlf = self.write("b.txt", b"x"*(size-1)+b"\r\n"+b"tail\n")
        self.assertEqual(text_digest(lf), text_digest(crlf))

    def test_lone_cr_and_trailing_cr_are_preserved(self):
        self.assertNotEqual(text_digest(self.write("a", b"a\rb")), text_digest(self.write("b", b"a\nb")))
        self.assertNotEqual(text_digest(self.write("c", b"end\r")), text_digest(self.write("d", b"end")))

    def test_binary_and_empty_files_hash_byte_for_byte(self):
        binary = self.write("a.bin", b"\0\r\n\0data\r\n")
        self.assertEqual(text_digest(binary), digest(binary))
        empty = self.write("e", b"")
        self.assertEqual(text_digest(empty), digest(empty))

    def test_digest_matches_accepts_old_raw_and_new_normalized_hashes(self):
        crlf = self.write("b.txt", b"one\r\ntwo\r\n")
        self.assertTrue(digest_matches(crlf, digest(crlf)))
        self.assertTrue(digest_matches(crlf, text_digest(crlf)))
        self.assertFalse(digest_matches(crlf, "0"*64))

    def test_older_raw_hash_reports_still_validate_and_survive_a_line_ending_flip(self):
        source = create_source(Path(self.temp)/"src")
        report = sample_report(source, "run")
        self.assertTrue(validate(report, check_files=True)["valid"])
        for ev in report["evidence"]:  # stamped as an older release would: raw bytes
            if "path" in ev:
                ev["sha256"] = digest(source/ev["path"])
        self.assertTrue(validate(report, check_files=True)["valid"])
        for ev in report["evidence"]:  # a teammate's CRLF checkout of the same text
            if "path" in ev:
                path = source/ev["path"]
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
                ev["sha256"] = text_digest(path)
        self.assertTrue(validate(report, check_files=True)["valid"])

    def test_inventory_is_stable_across_line_ending_checkouts(self):
        a = create_source(Path(self.temp)/"a")
        b = create_source(Path(self.temp)/"b")
        for path in b.rglob("*.js"):
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        first, second = inventory(a), inventory(b)
        second["target"] = first["target"]  # same project, two checkouts
        delta = compare_inventory(first, second)
        self.assertEqual(delta["changed"], [])
        self.assertTrue(delta["unchanged"])


class SnapshotLineEndings(unittest.TestCase):
    def test_snapshot_files_use_lf_and_match_their_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            source = create_source(Path(temp)/"src")
            result = publish(sample_report(source, "run-lf"), Path(temp)/"out")
            snapshot = Path(result["snapshot"])
            manifest = read_json(snapshot/"manifest.json")
            self.assertTrue(manifest)
            for name, sha in manifest.items():
                data = (snapshot/name).read_bytes()
                self.assertNotIn(b"\r\n", data, name)  # a git checkout would rewrite CRLF and break the hash
                self.assertEqual(digest(snapshot/name), sha, name)


class HostDetection(unittest.TestCase):
    def home(self, *directories):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for directory in directories:
            (Path(temp.name)/directory).mkdir(parents=True)
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        for patch in (mock.patch.object(Path, "home", return_value=Path(temp.name)),
                      mock.patch.dict(os.environ, env, clear=True)):
            patch.start()
            self.addCleanup(patch.stop)
        return Path(temp.name)

    def test_detects_only_installed_agents(self):
        self.home(".claude", ".gemini")
        self.assertEqual(installer.detect_hosts(), ["claude", "antigravity"])

    def test_nothing_detected_is_an_error_not_a_silent_codex_install(self):
        home = self.home()
        with mock.patch("sys.argv", ["install.py"]), self.assertRaisesRegex(ValueError, "No supported agent found"):
            installer.main()
        self.assertFalse((home/".codex").exists())

    def test_main_installs_for_every_detected_agent(self):
        home = self.home(".claude", ".agents")
        with mock.patch("sys.argv", ["install.py"]), mock.patch("builtins.print") as out:
            installer.main()
        result = json.loads(out.call_args.args[0])
        self.assertEqual(result["detected"], ["claude", "agents"])
        self.assertTrue((home/".claude/skills/architect-anything/SKILL.md").is_file())
        self.assertTrue((home/".agents/skills/architect-anything/SKILL.md").is_file())
        self.assertFalse((home/".codex").exists())

    def test_explicit_host_still_installs_without_the_config_directory(self):
        home = self.home()
        with mock.patch("sys.argv", ["install.py", "--host", "claude"]), mock.patch("builtins.print"):
            installer.main()
        self.assertTrue((home/".claude/skills/architect-anything/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
