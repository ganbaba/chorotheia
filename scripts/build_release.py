"""Build deterministic, allowlisted source and Skill archives using the stdlib."""
import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sources(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'release-manifest.json').read_text())
    version = manifest['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid release version')
    files = manifest['files']
    if not isinstance(files, list) or len(files) != len(set(files)):
        raise ValueError('Invalid or duplicate release file list')
    result = {}
    for name in sorted(files):
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or str(p) != name or '\\' in name:
            raise ValueError('Unsafe release path')
        if any(x in {'.git', '.agent', '.chorotheia-agent', 'backups', 'local', '__pycache__', '.env'} for x in p.parts):
            raise ValueError('Private/runtime path in release')
        target = root
        for part in p.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError('Symlink in release source')
        if not target.is_file():
            raise ValueError('Missing release source: ' + name)
        result[name] = target.read_bytes()
    expected = {}
    for line in result['SOURCE-SHA256SUMS.txt'].decode().splitlines():
        digest, name = line.split('  ', 1)
        expected[name] = digest
    if set(expected) != set(result) - {'SOURCE-SHA256SUMS.txt'}:
        raise ValueError('Source checksum file does not cover the exact release file list')
    for name, digest in expected.items():
        if sha(result[name]) != digest:
            raise ValueError('Source checksum mismatch: ' + name)
    tree = ast.parse(result['chorotheia/__init__.py'])
    versions = [n.value.value for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets)
                and isinstance(n.value, ast.Constant)]
    if versions != [version]:
        raise ValueError('CLI version and release manifest differ')
    return manifest, result


def zip_bytes(files, prefix):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            item = zipfile.ZipInfo(prefix + name, date_time=(2026, 11, 25, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data)
    return out.getvalue()


def build(root, output):
    manifest, files = sources(root)
    version = manifest['version']
    prefix = 'chorotheia-' + version + '/'
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archives = {'chorotheia-' + version + '-source.zip': zip_bytes(files, prefix)}
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for name, data in sorted(files.items()):
            item = tarfile.TarInfo(prefix + name)
            item.size, item.mode, item.mtime = len(data), 0o644, 1795564800
            item.uid = item.gid = 0
            archive.addfile(item, io.BytesIO(data))
    compressed = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=compressed, mode='wb', compresslevel=9, mtime=0) as archive:
        archive.write(tar.getvalue())
    archives['chorotheia-' + version + '-source.tar.gz'] = compressed.getvalue()
    skill = {name[len('skills/chorotheia/'):]: data for name, data in files.items() if name.startswith('skills/chorotheia/')}
    skill['LICENSE'] = files['LICENSE']
    archives['chorotheia-skill-' + version + '.zip'] = zip_bytes(skill, 'chorotheia/')
    checksums = ''.join(sha(data) + '  ' + name + '\n' for name, data in sorted(archives.items()))
    archives['SHA256SUMS.txt'] = checksums.encode()
    for name, data in archives.items():
        path = output / name
        if path.is_symlink():
            raise ValueError('Symlink artifact destination refused')
        path.write_bytes(data)
    return {name: {'sha256': sha(data), 'size': len(data)} for name, data in sorted(archives.items())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], args.output), indent=2))
