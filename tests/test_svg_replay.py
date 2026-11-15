"""Synthetic SVG and replay checks; no account, network or device is required."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'rightech-plugin/scripts'
EXAMPLES = ROOT/'rightech-plugin/examples/model-tools'
sys.path.insert(0, str(SCRIPTS))
from model_tools import InputError, DependencyUnavailable, load, lookup, MISSING
from validate_svg import validate as svg_validate
from draw_svg import draw
from render_svg import render, raster, paint
from replay_cases import run
from validate import validate_entity

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="2" y="2" width="12" height="12"/></svg>'
HAS_RASTER = all(importlib.util.find_spec(name) for name in ('PIL', 'cairosvg'))


def node(model, id):
    def find(n):
        if n['id'] == id:
            return n
        for child in n.get('children', []):
            match = find(child)
            if match is not None:
                return match
    return find(model['data'])


class SvgTests(unittest.TestCase):
    def test_portable_icon_and_legacy_fixed_color(self):
        self.assertFalse(svg_validate(SVG))
        colored = SVG.replace('<rect ', '<rect fill="#ffffff" ')
        self.assertTrue(any(f['severity'] == 'error' for f in svg_validate(colored)))
        self.assertTrue(all(f['severity'] == 'warning' for f in svg_validate(colored, legacy=True)))

    def test_active_content_and_resources_are_always_rejected(self):
        bad = [SVG.replace('</svg>', '<script>void 0</script></svg>'),
               SVG.replace('<rect ', '<rect onload="void 0" '),
               SVG.replace('</svg>', '<foreignObject/></svg>'),
               SVG.replace('</svg>', '<image href="file:///DO_NOT_FETCH"/></svg>'),
               '<!DOCTYPE svg [<!ENTITY x "test">]>'+SVG,
               '<?xml-stylesheet href="https://example.invalid/test.css"?>'+SVG]
        for icon in bad:
            for legacy in (False, True):
                with self.subTest(icon=icon[:50], legacy=legacy):
                    self.assertTrue(any(f['severity'] == 'error' for f in svg_validate(icon, legacy=legacy)))

    def test_embedded_icons_are_optional_but_checked_and_synchronized(self):
        model = load(EXAMPLES/'model.json')
        parameter = node(model, 'temperature')
        parameter.pop('display')
        self.assertFalse(validate_entity('models', model, 'new').errors)
        parameter['display'] = {'svg': SVG}
        parameter['levels'] = {'svg': SVG}
        self.assertFalse(validate_entity('models', model, 'new').errors)
        parameter['levels']['svg'] = SVG.replace('width="12"', 'width="10"')
        self.assertTrue(any('SVG_COPIES' in e for e in validate_entity('models', model, 'new').errors))
        parameter.pop('levels')
        parameter['display']['svg'] = SVG.replace('</svg>', '<script/></svg>')
        self.assertTrue(validate_entity('models', model, 'export').errors)

    def test_display_only_svg_warns_until_target_render_is_confirmed(self):
        model=load(EXAMPLES/'model.json');parameter=node(model,'temperature')
        parameter.pop('levels')
        report=validate_entity('models',model,'new')
        self.assertFalse(report.errors)
        self.assertTrue(any('SVG_DISPLAY_ONLY' in w for w in report.warnings))
        parameter['levels']={'svg':parameter['display']['svg']}
        self.assertFalse(any('SVG_DISPLAY_ONLY' in w for w in validate_entity('models',model,'new').warnings))

    def test_arbitrary_drawing_and_invalid_geometry_specification(self):
        spec = {'viewBox': [0, 0, 16, 16], 'elements': [{'tag': 'circle', 'attrs': {'cx': 8, 'cy': 8, 'r': 5}}]}
        self.assertFalse(svg_validate(draw(spec)))
        for field,value in [('viewBox', [0, 0, 0, 16]), ('elements', [{'tag': 'script', 'text': 'void 0'}])]:
            bad = {**spec, field:value}
            with self.subTest(field=field), self.assertRaises(InputError):
                draw(bad)

    @unittest.skipUnless(HAS_RASTER, 'optional CairoSVG/Pillow renderer unavailable')
    def test_actual_pixels_sizes_themes_and_state_colors(self):
        from PIL import Image
        files = sorted((EXAMPLES/'icons').glob('*.svg'))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'preview.png'
            report = render(files, output)
            self.assertEqual(report['status'], 'passed')
            self.assertFalse(report['ric_verified'])
            self.assertEqual(len(report['samples']), len(files)*18)
            self.assertEqual({s['size_px'] for s in report['samples']}, {16, 24, 32})
            self.assertEqual(len({s['background'] for s in report['samples']}), 2)
            self.assertTrue(all(s['visible_pixels_count']>0 and not s['boundary_ink'] for s in report['samples']))
            for color in ('#2a9d64', '#de4c55'):
                image = Image.open(io.BytesIO(raster(paint(SVG, color), 16))).convert('RGBA')
                self.assertEqual(image.size, (16,16))
                self.assertEqual(image.getpixel((8,8)), tuple(bytes.fromhex(color[1:]))+(255,))
            self.assertTrue(output.is_file())

    @unittest.skipUnless(HAS_RASTER, 'optional CairoSVG/Pillow renderer unavailable')
    def test_blank_and_clipped_icons_fail_pixel_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); icon=root/'icon.svg'
            for value in (SVG.replace('<rect ', '<rect fill="none" '), SVG.replace('x="2"','x="0"')):
                icon.write_text(value)
                self.assertEqual(render([icon], root/'preview.png')['status'], 'failed')

    def test_missing_renderer_keeps_html_without_passing_png(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); icons=root/'icons';icons.mkdir();(icons/'test.svg').write_text(SVG)
            result=subprocess.run([sys.executable, '-S', str(SCRIPTS/'render_svg.py'), str(icons),
                                   '-o', str(root/'preview.png')],capture_output=True,text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'not_tested')
            self.assertTrue((root/'preview.html').is_file())
            self.assertFalse((root/'preview.png').exists())

    def test_missing_native_cairo_is_an_unavailable_dependency(self):
        real_import=__import__
        def unavailable(name,*args,**kwargs):
            if name=='cairosvg':raise OSError('native library missing')
            return real_import(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=unavailable), self.assertRaises(DependencyUnavailable):
            raster(SVG,16)


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.model=load(EXAMPLES/'model.json');self.cases=load(EXAMPLES/'cases.json')

    def test_example_and_export_wrapper(self):
        before=copy.deepcopy((self.model,self.cases))
        result=run(self.model,self.cases)
        self.assertEqual((result['passed_count'],result['failed_count'],result['not_tested_count']),(4,0,0))
        self.assertFalse(result['ric_verified'])
        self.assertEqual((self.model,self.cases),before)
        exported={'version':1,'store':'models','data':self.model}
        self.assertEqual(run(exported,self.cases),result)

    def test_wrong_source_scale_and_expected_values_are_detected(self):
        for field,value in [('reference','telemetry.wrong'),('factor',1)]:
            changed=copy.deepcopy(self.model);node(changed,'temperature')[field]=value
            with self.subTest(field=field):
                self.assertGreater(run(changed,self.cases)['failed_count'],0)
        self.cases['cases'][0]['expected']['device_online']=0
        self.assertGreater(run(self.model,self.cases)['failed_count'],0)
        self.cases['cases'][0]['expected']['device_online']=False
        self.cases['cases'][0]['expected']['serial']=17
        self.assertGreater(run(self.model,self.cases)['failed_count'],0)

    def test_command_full_input_aliases_bounds_and_json(self):
        action=node(self.model,'set_target');action['children'][0]['id']='set_target.value'
        action['params']['payload']='{"target":{{value}}}'
        case=copy.deepcopy(self.cases['cases'][-1]);case['inputs']={'set_target.value':25}
        cases={**self.cases,'cases':[case]}
        self.assertEqual(run(self.model,cases)['passed_count'],1)
        for value in (101,False,None):
            case['inputs']={'value':value}
            self.assertEqual(run(self.model,cases)['failed_count'],1)
        case['inputs']={'value':25,'set_target.value':26}
        self.assertEqual(run(self.model,cases)['failed_count'],1)
        case['inputs']={'value':25}
        node(self.model,'set_target')['params']['payload']='{broken'
        self.assertEqual(run(self.model,cases)['failed_count'],1)

    def test_unsupported_behavior_is_not_passed_including_absence(self):
        for kind in ('handler','sequence','server-state'):
            changed=copy.deepcopy(self.cases);changed['cases'][0]['kind']=kind
            self.assertEqual(run(self.model,changed)['not_tested_count'],1)
        node(self.model,'telemetry')['parser']={'limit':0}
        case=copy.deepcopy(self.cases['cases'][0]);case['expected']={};case['absent']=['temperature']
        self.assertEqual(run(self.model,{**self.cases,'cases':[case]})['not_tested_count'],1)

    def test_unsupported_dependencies_do_not_depend_on_tree_order(self):
        container=node(self.model,'telemetry')
        derived=container['children'].pop(0)
        self.model['data']['children'].insert(1,derived)
        container['parser']={'limit':0}
        case=copy.deepcopy(self.cases['cases'][0]);case['expected']={};case['absent']=['temperature']
        self.assertEqual(run(self.model,{**self.cases,'cases':[case]})['not_tested_count'],1)

    def test_handler_output_extensions_and_mqtt_batches_are_not_emulated(self):
        node(self.model,'temperature').pop('reference')
        self.assertGreater(run(self.model,self.cases)['not_tested_count'],0)
        self.model=load(EXAMPLES/'model.json');self.model['removed']=['temperature']
        self.assertEqual(run(self.model,self.cases)['not_tested_count'],4)
        self.model.pop('removed')
        self.cases['cases'][0]['packet']['payload']='[{"temperature":0}]'
        self.assertEqual(run(self.model,self.cases)['not_tested_count'],1)

    def test_literal_keys_arrays_and_explicit_bits(self):
        self.assertEqual(lookup({'a.b':7,'a':{'b':9}},'a.b'),7)
        self.assertEqual(lookup({'array':[0,False]},'array.1'),False)
        self.assertIs(lookup({'array':[]},'array.0'),MISSING)
        self.assertTrue(lookup({'flags':5},'flags.2',bit_source=True))
        with self.assertRaises(NotImplementedError):lookup({'flags':5},'flags.2')

    def test_cases_need_real_assertions_and_known_parameters(self):
        case=copy.deepcopy(self.cases['cases'][0]);case['expected']={}
        self.assertEqual(run(self.model,{**self.cases,'cases':[case]})['failed_count'],1)
        case['absent']=['unknown_parameter']
        self.assertEqual(run(self.model,{**self.cases,'cases':[case]})['failed_count'],1)
        with self.assertRaises(InputError):run(self.model,{'schema_version':'1.0','cases':[]})

    def test_absence_needs_an_actual_packet(self):
        case={'name':'absence','kind':'mqtt','synthetic':True,'absent':['temperature'],'object':{'id':'sensor-01'}}
        for packet in ({},{'topic':'test'},{'payload':{}}):
            case['packet']=packet
            self.assertEqual(run(self.model,{**self.cases,'cases':[case]})['failed_count'],1)
        case['kind']='decoded';case['packet']={}
        self.assertEqual(run(self.model,{**self.cases,'cases':[case]})['failed_count'],1)
        case['packet']={'data':{}};case['object']={'id':'sensor-01'}
        self.assertEqual(run(self.model,{**self.cases,'cases':[case]})['passed_count'],1)

    def test_boolean_factor_is_not_a_numeric_identity(self):
        node(self.model,'device_online')['factor']=True
        self.assertGreater(run(self.model,self.cases)['failed_count'],0)

    def test_cli_exit_statuses_and_no_raw_input_in_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);model=root/'model.json';cases=root/'cases.json'
            model.write_text(json.dumps(self.model));cases.write_text(json.dumps(self.cases))
            cmd=[sys.executable,str(SCRIPTS/'replay_cases.py'),str(model),str(cases)]
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            self.cases['cases'][0]['packet']['payload']='{"temperature":0,"online":false,"serial":"DO_NOT_ECHO","channels":[0,2]}'
            cases.write_text(json.dumps(self.cases))
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertNotIn('DO_NOT_ECHO',result.stdout+result.stderr)
            self.cases['cases'][0]['kind']='handler';cases.write_text(json.dumps(self.cases))
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,1)
            cases.write_text('{"payload":"DO_NOT_ECHO",')
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertNotIn('DO_NOT_ECHO',result.stdout+result.stderr)
            self.assertNotIn('Traceback',result.stderr)

    def test_dependency_is_reported_instead_of_a_false_pass(self):
        cmd=[sys.executable,'-S',str(SCRIPTS/'replay_cases.py'),str(EXAMPLES/'model.json'),str(EXAMPLES/'cases.json')]
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)['status'],'not_tested')

    def test_isolated_skill_copy_has_its_runtime_and_schemas(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'skill'
            shutil.copytree(ROOT/'rightech-plugin/skills/rightech-output',root,ignore=shutil.ignore_patterns('__pycache__'))
            result=subprocess.run([sys.executable,str(root/'scripts/replay_cases.py'),
                                   str(root/'examples/model-tools/model.json'),str(root/'examples/model-tools/cases.json')],
                                  capture_output=True,text=True,cwd=temp)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['passed_count'],4)

    def test_base_validator_stays_dependency_free(self):
        result=subprocess.run([sys.executable,'-S',str(SCRIPTS/'validate.py'),str(ROOT/'import-ready'),'--quiet'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':
    unittest.main()
