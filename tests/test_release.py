import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_release import build, sources
from chorotheia import __version__ as VERSION
from publish_release import publish


class ReleaseTests(unittest.TestCase):
    def test_archives_are_deterministic_and_private_state_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'a', Path(temp)/'b'
            self.assertEqual(build(ROOT, a), build(ROOT, b))
            with zipfile.ZipFile(a/f'chorotheia-{VERSION}-source.zip') as z:
                names = z.namelist()
                self.assertTrue(any(n.endswith('/chorotheia/core.py') for n in names))
                self.assertFalse(any('/.agent/' in n or '/backups/' in n for n in names))
                self.assertTrue(all('..' not in Path(n).parts for n in names))
            with tarfile.open(a/f'chorotheia-{VERSION}-source.tar.gz') as t:
                self.assertEqual(sorted(t.getnames()), sorted(names))

    def test_tampered_source_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source'
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('__pycache__'))
            (source/'chorotheia/core.py').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                sources(source)

    def test_source_and_standalone_skill_archives_carry_the_license(self):
        license_bytes = (ROOT/'LICENSE').read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            build(ROOT, output)
            with zipfile.ZipFile(output/f'chorotheia-{VERSION}-source.zip') as z:
                self.assertEqual(z.read(f'chorotheia-{VERSION}/LICENSE'), license_bytes)
            with tarfile.open(output/f'chorotheia-{VERSION}-source.tar.gz') as t:
                self.assertEqual(t.extractfile(f'chorotheia-{VERSION}/LICENSE').read(), license_bytes)
            with zipfile.ZipFile(output/f'chorotheia-skill-{VERSION}.zip') as z:
                self.assertEqual(z.read('chorotheia/LICENSE'), license_bytes)

    def test_manifest_traversal_and_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source'
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('__pycache__'))
            path=source/'release-manifest.json';m=json.loads(path.read_text());m['files'].append('../outside');path.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError, 'Unsafe release path'):
                sources(source)
            m['files'].remove('../outside');path.write_text(json.dumps(m))
            (source/'chorotheia/core.py').unlink();(source/'chorotheia/core.py').symlink_to(ROOT/'chorotheia/core.py')
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                sources(source)

    def test_existing_tag_cannot_be_retargeted(self):
        with tempfile.TemporaryDirectory() as temp:
            build(ROOT, temp)
            calls=[]
            def request(method,url,**kwargs):
                calls.append(method)
                return {'object':{'type':'commit','sha':'b'*40}}
            with self.assertRaisesRegex(ValueError, 'never overwrite'):
                publish(ROOT,temp,'ganbaba/chorotheia','a'*40,request)
            self.assertEqual(calls,['GET'])
