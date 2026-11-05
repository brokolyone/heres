#!/usr/bin/env python3
"""Turn a teamgram-android checkout into Privetgram.

  apply.py <teamgram-android dir> <server_pkcs1.pub> [--name Privetgram] [--package org.privetgram.messenger]

1. applies patches/*.patch (server address chosen in the app, see PrivetServer.java);
2. replaces the built-in server RSA key with yours (only your server can talk to the app);
3. renames the app and its package, draws the black & white glitch icon.
Run it on a clean checkout of the pinned commit (see build.sh).
"""
import argparse, glob, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'server'))
OLD_PACKAGE = 'org.chatengine.messenger'
OLD_NAME = 'Teamgram'


def fingerprint(pub_path):
    out = subprocess.run([sys.executable, os.path.join(HERE, '..', 'server', 'rsa_fingerprint.py'), pub_path],
                         check=True, capture_output=True, text=True).stdout
    return int(out.strip())


def sub_file(path, pattern, repl, count_expected=None, regex=False):
    s = open(path, encoding='utf-8').read()
    if regex:
        s2, n = re.subn(pattern, repl, s)
    else:
        n = s.count(pattern)
        s2 = s.replace(pattern, repl)
    if count_expected is not None and n != count_expected:
        sys.exit(f'{path}: expected {count_expected} matches of {pattern!r}, found {n}')
    open(path, 'w', encoding='utf-8').write(s2)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('pubkey')
    ap.add_argument('--name', default='Privetgram')
    ap.add_argument('--package', default='org.privetgram.messenger')
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    main_dir = os.path.join(src, 'TMessagesProj', 'src', 'main')

    # 1. code patches
    for p in sorted(glob.glob(os.path.join(HERE, 'patches', '*.patch'))):
        subprocess.run(['git', 'apply', '--whitespace=nowarn', p], cwd=src, check=True)
        print('patched', os.path.basename(p))

    # 2. server key
    pem = open(a.pubkey).read().strip()
    if 'BEGIN RSA PUBLIC KEY' not in pem:
        sys.exit('pubkey must be PKCS#1: openssl rsa -in server_pkcs1.key -RSAPublicKey_out')
    fp = fingerprint(a.pubkey)
    lines = pem.splitlines()
    c_literal = '\n'.join(
        ('"' if i == 0 else '                                                  "') + l + ('\\n"' if i < len(lines) - 1 else '"')
        for i, l in enumerate(lines))
    hs = os.path.join(src, 'TMessagesProj', 'jni', 'tgnet', 'Handshake.cpp')
    sub_file(hs, r'(?s)serverPublicKeys\.emplace_back\("-----BEGIN RSA PUBLIC KEY-----.*?-----END RSA PUBLIC KEY-----"\);\s*'
                 r'serverPublicKeysFingerprints\.push_back\(0x[0-9a-f]+\);',
             lambda m: f'serverPublicKeys.emplace_back({c_literal});\n'
                       f'                    serverPublicKeysFingerprints.push_back(0x{fp:016x});',
             count_expected=2, regex=True)
    print(f'server key fingerprint {fp} (0x{fp:016x})')

    # 3. name + package
    for f in glob.glob(os.path.join(main_dir, 'res', 'values*', 'strings.xml')):
        sub_file(f, OLD_NAME, a.name)
        # translations still say "Telegram"; keep links (t.me, telegram.org, @Telegram) and resource names intact
        sub_file(f, r'(?<![\w./@-])Telegram(?![\w.])', a.name, regex=True)
    for f in ['res/layout/call_notification.xml', 'res/layout/call_notification_rtl.xml']:
        sub_file(os.path.join(main_dir, f), OLD_NAME, a.name)
    java = subprocess.run(['grep', '-rl', '-e', OLD_NAME, '-e', OLD_PACKAGE, os.path.join(main_dir, 'java')],
                          capture_output=True, text=True).stdout.split()
    xml = [os.path.join(main_dir, 'AndroidManifest.xml')] + glob.glob(os.path.join(main_dir, 'res', 'xml', '*.xml'))
    for f in java + xml:
        sub_file(f, OLD_PACKAGE, a.package)
        if f.endswith('.java'):
            sub_file(f, OLD_NAME, a.name)
    # one universal APK for real phones (arm64 + armv7); x86 only matters for emulators
    gradle_app = os.path.join(src, 'TMessagesProj_App', 'build.gradle')
    s = open(gradle_app).read()
    i = s.index('        afat {')
    j = s.index('abiFilters', i)
    k = s.index('\n', j)
    s = s[:j] + 'abiFilters ' + os.environ.get('PRIVETGRAM_ABIS', '"armeabi-v7a", "arm64-v8a"') + s[k:]
    open(gradle_app, 'w').write(s)
    sub_file(os.path.join(src, 'gradle.properties'), f'APP_PACKAGE={OLD_PACKAGE}', f'APP_PACKAGE={a.package}', 1)
    # Firebase is not used by the private server, but the gradle plugin wants a matching entry.
    sub_file(os.path.join(src, 'TMessagesProj_App', 'google-services.json'), f'"{OLD_PACKAGE}', f'"{a.package}')

    # 4. icon: black background, glitched B/W plane
    res = os.path.join(main_dir, 'res')
    subprocess.run([sys.executable, os.path.join(HERE, 'branding', 'make_icon.py'), res], check=True)
    black = ('<?xml version="1.0" encoding="utf-8"?>\n'
             '<shape xmlns:android="http://schemas.android.com/apk/res/android">\n'
             '    <solid android:color="#0C0C0C" />\n</shape>\n')
    for f in ['icon_background.xml', 'icon_background_round.xml', 'icon_background_sa.xml']:
        open(os.path.join(res, 'drawable', f), 'w').write(black)
    print('done:', a.name, a.package)


if __name__ == '__main__':
    main()
