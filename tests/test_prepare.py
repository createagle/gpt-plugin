import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'plugins/browser-to-pages/skills/browser-to-pages/scripts/prepare.py'
spec = importlib.util.spec_from_file_location('prepare', SCRIPT)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def test_code_whitespace_and_html(self):
        code = 'const html = `<div>hello</div>`;\n\n    console.log(html);\n'
        fenced = prepare.code_block(code, 'javascript')
        self.assertEqual(fenced.split('\n', 1)[1][:-3], code)
        self.assertTrue(fenced.startswith('```javascript\n'))

    def test_nested_list_and_inline_code(self):
        html = '<h2>Heading</h2><ol start="3"><li>A<ul><li><code>x_y</code></li></ul></li><li>B</li></ol>'
        result = prepare.convert(prepare.Tree(html).root, 'https://example.test', [], [])
        self.assertIn('## Heading', result)
        self.assertIn('3. A', result)
        self.assertIn('   - `x_y`', result)
        self.assertIn('4. B', result)

    def test_unsupported_content_stops(self):
        for html in ('<iframe src="/x"></iframe>', '<table><tr><td>x</td></tr></table>'):
            with self.assertRaises(ValueError):
                prepare.convert(prepare.Tree(html).root, 'https://example.test', [], [])

    def test_cache_and_attachment_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = 'https://example.test/image.gif'
            cache = root / 'assets'; cache.mkdir()
            binary = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
            (cache / (prepare.digest(image.encode()) + '.gif')).write_bytes(binary)
            capture = {'title': 'Example', 'source_url': 'https://example.test/article', 'blocks': [
                {'tag': 'P', 'html': '<strong>Hello</strong>', 'images': []},
                {'tag': 'P', 'html': '<img src="' + image + '">', 'images': [{'src': image}]}
            ]}
            path = root / 'capture.json'; path.write_text(json.dumps(capture))
            job = prepare.prepare(path, root / 'job.json', cache_only=True)
            self.assertEqual(job['images'][0]['sha256'], prepare.digest(binary))
            self.assertEqual(job['units'][0], '**Hello**')
            job['page_id'] = 'example-page'
            key = job['images'][0]['sha256']
            job['uploads'][key] = {'page_id': 'other-page', 'file_access_confirmed': True,
                                   'markdown': '![image](library-file:synthetic)'}
            with self.assertRaises(ValueError): prepare.finalize(job)
            job['uploads'][key]['page_id'] = job['page_id']
            self.assertEqual(prepare.finalize(job)[1], '![image](library-file:synthetic)')
            job['state'] = 'complete'; prepare.save(root / 'job.json', job)
            resumed = prepare.prepare(path, root / 'job.json', cache_only=True)
            self.assertEqual(resumed['uploads'], job['uploads'])
            self.assertEqual(resumed['state'], 'complete')


if __name__ == '__main__': unittest.main()
