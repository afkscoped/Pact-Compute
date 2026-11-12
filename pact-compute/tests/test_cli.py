import ast
import inspect
import re

import pytest

from pact import cli


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr('sys.argv', ['pact', *argv])
    cli.main()


def subcommands():
    return sorted(set(re.findall(r"sub\.add_parser\('([a-z-]+)'", inspect.getsource(cli.main))))


def test_import_subcommand_runs_against_the_bundled_dataset(monkeypatch, capsys):
    # Regression: a function-local `import_sources` import in another branch of main() made the name local to the whole
    # function, so `pact.cli import` (run by the deploy entrypoint) crashed with UnboundLocalError.
    run_cli(monkeypatch, 'import')
    assert re.match(r'^[0-9a-f]{64}: \d+ GPU pods and \d+ carbon intervals\.$', capsys.readouterr().out.strip())


def test_main_does_not_shadow_module_level_names():
    tree = ast.parse(inspect.getsource(cli))
    top = {a.asname or a.name.split('.')[0] for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    top |= {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    bound = [a.asname or a.name.split('.')[0] for n in ast.walk(main) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names]
    bound += [t.id for n in ast.walk(main) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)]
    assert not (set(bound) & top), set(bound) & top


def test_every_subcommand_parses_its_help(monkeypatch, capsys):
    names = subcommands()
    assert 'import' in names and 'scheduler-baselines' in names and len(names) >= 10
    for name in names:
        with pytest.raises(SystemExit) as stop:
            run_cli(monkeypatch, name, '--help')
        assert stop.value.code == 0, name
    capsys.readouterr()


def test_support_benchmark_subcommand_runs(monkeypatch, capsys):
    with pytest.raises(SystemExit) as stop:
        run_cli(monkeypatch, 'support-benchmark')
    assert stop.value.code == 0
    assert '50/50 support cases passed' in capsys.readouterr().out
