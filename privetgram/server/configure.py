#!/usr/bin/env python3
"""Write Privetgram settings into teamgram-server's docker configs (teamgramd/etc2/*.yaml).

  configure.py <teamgram-server dir> <env file>

Env file keys: MYSQL_PASSWORD, MINIO_ROOT_PASSWORD, INVITE_CODE, KEY_FINGERPRINT.
"""
import glob, os, re, sys


def load_env(path):
    env = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k] = v
    return env


def strip_block(text, key):
    """Remove a top-level YAML block (key + its indented lines)."""
    return re.sub(rf'(?m)^{key}:\n(?:[ \t]+.*\n|\n)*', '', text)


def main():
    src, env = sys.argv[1], load_env(sys.argv[2])
    etc = os.path.join(src, 'teamgramd', 'etc2')
    for path in glob.glob(os.path.join(etc, '*.yaml')):
        s = open(path).read()
        s = s.replace('teamgram:teamgram@tcp(mysql:3306)', f"teamgram:{env['MYSQL_PASSWORD']}@tcp(mysql:3306)")
        s = re.sub(r'(?m)^(\s*SecretAccessKey:).*$', rf"\1 {env['MINIO_ROOT_PASSWORD']}", s)
        s = re.sub(r'(?m)^(\s*AccessKeyID:).*$', r'\1 minio', s)
        s = re.sub(r'(?m)^(\s*KeyFingerprint:).*$', rf'\1 "{env["KEY_FINGERPRINT"]}"', s)
        s = strip_block(s, 'Telemetry')   # no jaeger in the slim stack
        if os.path.basename(path) == 'bff.yaml':
            s, n = re.subn(r'(?m)^(Code:\n(?:\s+.*\n)*?\s+Key:).*$', rf'\1 "{env["INVITE_CODE"]}"', s)
            if n != 1:
                sys.exit('bff.yaml: Code.Key not found')
        open(path, 'w').write(s)
    print('configured', etc)


if __name__ == '__main__':
    main()
