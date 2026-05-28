import ast
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _setup_keyword(name):
    tree = ast.parse((ROOT / "setup.py").read_text())
    setup_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "setup"
    )
    return next(
        keyword.value
        for keyword in setup_call.keywords
        if keyword.arg == name
    )


class PythonVersionMetadataTest(unittest.TestCase):
    def test_packaging_metadata_allows_python_311(self):
        setup_python_requires = ast.literal_eval(_setup_keyword("python_requires"))
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

        self.assertEqual(setup_python_requires, ">=3.11")
        self.assertEqual(
            pyproject["tool"]["poetry"]["dependencies"]["python"],
            ">=3.11,<3.14",
        )

    def test_setup_classifiers_include_supported_python_versions(self):
        classifiers = ast.literal_eval(_setup_keyword("classifiers"))

        self.assertIn("Programming Language :: Python :: 3.11", classifiers)
        self.assertIn("Programming Language :: Python :: 3.12", classifiers)
        self.assertIn("Programming Language :: Python :: 3.13", classifiers)


if __name__ == "__main__":
    unittest.main()
