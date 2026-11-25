"""Publish the verified bundle using only the current repository's Actions token."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request


def publish(root, dist, repo, commit, request):
    root, dist = Path(root), Path(dist)
    manifest = json.loads((root / 'release-manifest.json').read_text())
    tag = 'v' + manifest['version']
    if not re.fullmatch(r'[0-9a-f]{40}', commit) or repo.lower() != 'ganbaba/chorotheia':
        raise ValueError('Unexpected repository or commit')
    expected = {}
    for line in (dist / 'SHA256SUMS.txt').read_text().splitlines():
        sha, name = line.split('  ', 1)
        if Path(name).name != name or hashlib.sha256((dist / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Artifact integrity mismatch')
        expected[name] = sha
    expected['SHA256SUMS.txt'] = hashlib.sha256((dist / 'SHA256SUMS.txt').read_bytes()).hexdigest()
    base = 'https://api.github.com/repos/' + repo
    ref = request('GET', base + '/git/ref/tags/' + tag, missing=True)
    if ref:
        obj = ref['object']
        if obj['type'] == 'tag':
            obj = request('GET', base + '/git/tags/' + obj['sha'])['object']
        if obj['type'] != 'commit' or obj['sha'] != commit:
            raise ValueError('Existing version tag points elsewhere; never overwrite a release tag')
    release = request('GET', base + '/releases/tags/' + tag, missing=True)
    if not release:
        release = request('POST', base + '/releases', payload={
            'tag_name': tag, 'target_commitish': commit,
            'name': 'Chorotheia ' + tag + ' — Memory beyond context.',
            'body': (root / 'RELEASE-NOTES.md').read_text(),
            'draft': False, 'prerelease': False, 'make_latest': 'true'})
    upload = release['upload_url'].split('{', 1)[0]
    if not upload.startswith('https://uploads.github.com/repos/' + repo + '/'):
        raise ValueError('Unexpected upload host or repository')
    existing = {a['name']: a for a in release.get('assets', [])}
    for name, sha in expected.items():
        if name in existing:
            if existing[name].get('digest') != 'sha256:' + sha:
                raise ValueError('Existing asset differs or cannot be verified; refusing overwrite: ' + name)
            continue
        content_type = 'application/zip' if name.endswith('.zip') else 'application/gzip' if name.endswith('.gz') else 'text/plain'
        asset = request('POST', upload + '?name=' + urllib.parse.quote(name),
                        raw=(dist / name).read_bytes(), content_type=content_type)
        if asset.get('digest') not in (None, 'sha256:' + sha):
            raise ValueError('Uploaded asset digest mismatch')
        print(json.dumps({'asset': name, 'url': asset['browser_download_url'], 'sha256': sha}))
    print(json.dumps({'release': release['html_url'], 'tag': tag, 'commit': commit}))
    return release


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY', '').lower() != args.repo.lower() or os.environ.get('GITHUB_SHA') != args.commit:
        raise ValueError('Publishing requires the matching repository Actions context')
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('Repository-scoped Actions token missing')
    def request(method, url, payload=None, raw=None, content_type='application/json', missing=False):
        if not url.startswith(('https://api.github.com/repos/', 'https://uploads.github.com/repos/')):
            raise ValueError('Unexpected API host')
        data = json.dumps(payload).encode() if payload is not None else raw
        req = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
            'Content-Type': content_type, 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'Chorotheia-release'})
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            raise RuntimeError('GitHub request failed with HTTP ' + str(error.code)) from None
    publish(Path(__file__).resolve().parents[1], args.dist, args.repo, args.commit, request)


if __name__ == '__main__':
    main()
