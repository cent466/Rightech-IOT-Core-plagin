"""Public model checks using synthetic fixtures, without account exports."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rightech-plugin/scripts'))
import validate
import make_import_file


def model():
    return {'base': 'mqtt', 'name': 'Тестовый датчик', 'description': 'Синтетический пример',
            'data': {'id': 'root', 'name': 'Датчик', 'type': 'subsystem', 'active': True,
                     'children': [
                         {'id': 'external-software-modules', 'name': 'Внешние модули',
                          'type': 'subsystem', 'active': True, 'copy': True, 'children': []},
                         {'id': 'temperature', 'name': 'Температура', 'description': 'Показание датчика',
                          'type': 'argument', 'active': True, 'source': 'state', 'dataType': 'number',
                          'reference': 'test/temperature', 'unit': 'temperature-celsius'}]}}


class ModelContractTests(unittest.TestCase):
    def report(self, entity):
        return validate.validate_entity('models', entity, 'new')

    def test_valid_model_and_boolean_active(self):
        entity = model()
        self.assertFalse(self.report(entity).errors)
        entity['data']['children'][1]['active'] = 'true'
        self.assertTrue(self.report(entity).errors)

    def test_malformed_field_types_return_diagnostics(self):
        for key in ('type', 'dataType'):
            entity = model(); entity['data']['children'][1][key] = []
            with self.subTest(key=key):
                self.assertTrue(self.report(entity).errors)
        entity = model(); entity['data']['children'][1]['source'] = []
        self.assertTrue(self.report(entity).warnings)

    def test_publish_requires_string_topic_and_payload(self):
        entity = model()
        action = {'id': 'set_target', 'name': 'Установить порог', 'description': 'Команда теста',
                  'type': 'action', 'active': True, 'service': 'ric-gate', 'source': 'state',
                  'command': 'publish', 'params': {'topic': 'test/command', 'payload': '1'}}
        entity['data']['children'].append(action)
        self.assertFalse(self.report(entity).errors)
        for key in ('topic', 'payload'):
            for value in (None, 1, False):
                with self.subTest(key=key, value=value):
                    broken = copy.deepcopy(entity)
                    broken['data']['children'][-1]['params'][key] = value
                    self.assertTrue(self.report(broken).errors)
            broken = copy.deepcopy(entity)
            del broken['data']['children'][-1]['params'][key]
            self.assertTrue(self.report(broken).errors)

    def test_arrays_and_documented_event_are_supported(self):
        entity = model()
        for dtype in ('number[]', 'string[]', 'boolean[]'):
            entity['data']['children'][1]['dataType'] = dtype
            self.assertFalse(self.report(entity).errors)
        entity['data']['children'].append({'id': 'alarm_event', 'name': 'Авария',
                                          'type': 'event', 'active': True})
        self.assertFalse(self.report(entity).errors)
        entity['data']['children'][-1]['type'] = 'invented-type'
        self.assertTrue(self.report(entity).errors)

    def test_computed_reference_is_optional_and_config_is_not_state(self):
        entity = model()
        parameter = entity['data']['children'][1]
        parameter.pop('reference')
        self.assertFalse(any('reference' in w for w in self.report(entity).warnings))
        parameter['source'] = 'config'
        self.assertFalse(any('source=' in w for w in self.report(entity).warnings))

    def test_form_scope_and_command_variables(self):
        entity = model()
        action = {'id': 'set_target', 'name': 'Установить порог', 'description': 'Команда теста',
                  'type': 'action', 'active': True, 'service': 'ric-gate', 'source': 'state',
                  'command': 'publish', 'params': {'topic': 'test/{{object.id}}', 'payload': '{{temperature}}'},
                  'children': [{'id': 'temperature', 'name': 'Порог', 'description': 'Вход формы',
                                'type': 'argument', 'active': True, 'source': 'config', 'dataType': 'number'}]}
        entity['data']['children'].append(action)
        self.assertFalse(self.report(entity).errors)
        action['params']['payload'] = '{{missing_input}}'
        self.assertTrue(self.report(entity).errors)
        action['params']['payload'] = '{{temperature}}'
        action['children'].append(copy.deepcopy(action['children'][0]))
        self.assertTrue(self.report(entity).errors)

    def test_output_identifier_is_validated(self):
        self.assertRegex(make_import_file.build_envelope('models', model())['data']['_id'], r'^[0-9a-f]{24}$')
        for value in ('bad', 'z' * 24, True, 'f' * 25):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_import_file.build_envelope('models', model(), entity_id=value)

    def test_cli_rejects_bad_id_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); source = directory/'model.json'; target = directory/'out'
            source.write_text(json.dumps(model()), encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT/'rightech-plugin/scripts/make_import_file.py'),
                                     str(source), '--store', 'models', '--id', 'bad', '--out-dir', str(target)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(list(target.glob('*')))

    def test_distributed_script_copies_match(self):
        for name in ('validate.py', 'make_import_file.py'):
            self.assertEqual((ROOT/'rightech-plugin/scripts'/name).read_bytes(),
                             (ROOT/'rightech-plugin/skills/rightech-output/scripts'/name).read_bytes())

    def test_archive_matches_tracked_plugin_resources(self):
        tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--', 'rightech-plugin'],
                                 check=True, capture_output=True).stdout
        names = {name.decode('utf-8') for name in tracked.split(b'\0') if name}
        with ZipFile(ROOT/'rightech-plugin-claude.zip') as archive:
            self.assertEqual(set(archive.namelist()), names)
            for name in names:
                self.assertEqual(archive.read(name), (ROOT/name).read_bytes(), name)

    def test_required_manifest_versions_agree(self):
        versions = [json.loads((ROOT/'rightech-plugin'/folder/'plugin.json').read_text())['version']
                    for folder in ('.claude-plugin', '.codex-plugin')]
        self.assertEqual(versions[0], versions[1])


if __name__ == '__main__':
    unittest.main()
