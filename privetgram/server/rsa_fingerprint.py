#!/usr/bin/env python3
"""Print the MTProto fingerprint of an RSA key (PKCS#1 PEM, private or public).

fingerprint = lower 64 bits of SHA1(TL bytes n + TL bytes e), as an unsigned decimal.
Needs the `openssl` command line tool.
"""
import hashlib, re, subprocess, sys

def tl_bytes(b: bytes) -> bytes:
    if len(b) < 254:
        out = bytes([len(b)]) + b
    else:
        out = b'\xfe' + len(b).to_bytes(3, 'little') + b
    return out + b'\x00' * (-len(out) % 4)

def main(path: str) -> None:
    pem = open(path).read()
    kind = 'rsa' if 'PRIVATE' in pem else 'rsa -RSAPublicKey_in'
    text = subprocess.run(f'openssl {kind} -in "{path}" -noout -text', shell=True,
                          check=True, capture_output=True, text=True).stdout
    mod = re.search(r'(?:modulus|Modulus):\s*\n((?:\s+[0-9a-f:]+\n)+)', text).group(1)
    n = int(re.sub(r'[\s:]', '', mod), 16)
    e = int(re.search(r'(?:publicExponent|Exponent): (\d+)', text).group(1))
    nb = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    eb = e.to_bytes((e.bit_length() + 7) // 8, 'big')
    digest = hashlib.sha1(tl_bytes(nb) + tl_bytes(eb)).digest()
    print(int.from_bytes(digest[-8:], 'little'))

if __name__ == '__main__':
    main(sys.argv[1])
