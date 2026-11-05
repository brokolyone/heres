#!/usr/bin/env python3
"""End-to-end check of a Privetgram server over real MTProto (Telethon).

  pip install telethon
  python3 smoke_test.py --host 1.2.3.4 --pubkey server_pkcs1.pub --invite <code>

Signs up two throw-away test numbers (+7 999 xxxxxxx), sends a message between them and
checks that the invite code is refused as a login code for an existing account.
"""
import argparse, asyncio, hashlib, os, random, sys

from telethon import TelegramClient, errors, functions, types
from telethon.crypto import AES, rsa
from telethon.sessions import MemorySession

API_ID, API_HASH = 4, '014b35b6184100b085b0d0572f9b5103'   # same as the Android app


def rsa_pad_encrypt(fingerprint, data, *, use_old=False):
    """RSA_PAD (what the Android app and teamgram-server use); Telethon only has the legacy scheme."""
    key, _ = rsa._server_keys.get(fingerprint, (None, None))
    if key is None or len(data) > 144:
        return None
    padded = data + os.urandom(192 - len(data))
    while True:
        temp_key = os.urandom(32)
        with_hash = padded[::-1] + hashlib.sha256(temp_key + padded).digest()
        aes = AES.encrypt_ige(with_hash, temp_key, bytes(32))
        xored = bytes(a ^ b for a, b in zip(temp_key, hashlib.sha256(aes).digest()))
        block = int.from_bytes(xored + aes, 'big')
        if block < key.n:
            return pow(block, key.e, key.n).to_bytes(256, 'big')


rsa.encrypt = rsa_pad_encrypt


class Client(TelegramClient):
    # Telethon calls get_me() before login to check the session; teamgram answers an
    # unauthorized key with AUTH_RESTART (not AUTH_KEY_UNREGISTERED), so Telethon would
    # retry forever. Until we have logged in, "who am I" is simply nobody.
    _logged_in = False

    async def get_me(self, *args, **kwargs):
        return await super().get_me(*args, **kwargs) if self._logged_in else None

    async def _on_login(self, user):
        self._logged_in = True
        return await super()._on_login(user)


def client(host, port):
    s = MemorySession()
    s.set_dc(1, host, port)
    return Client(s, API_ID, API_HASH, connection_retries=1, retry_delay=1, timeout=15,
                          device_model='smoke-test', system_version='1', app_version='1')


async def sign_up(host, port, phone, invite, name):
    """New number: auth.signIn with the invite code -> SIGN_UP_REQUIRED -> auth.signUp."""
    c = client(host, port)
    await c.connect()
    sent = await c.send_code_request(phone)
    try:
        await c.sign_in(phone, invite, phone_code_hash=sent.phone_code_hash)
        raise SystemExit(f'FAIL: {phone} is already registered')
    except errors.PhoneNumberUnoccupiedError:
        pass
    r = await c(functions.auth.SignUpRequest(phone, sent.phone_code_hash, name, ''))
    return c, await c._on_login(r.user)


def ok(msg):
    print('  OK ', msg)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', required=True)
    ap.add_argument('--port', type=int, default=10443)
    ap.add_argument('--pubkey', required=True, help='server_pkcs1.pub (the key built into the APK)')
    ap.add_argument('--invite', required=True)
    a = ap.parse_args()
    rsa._server_keys.clear()                       # trust only our server key
    rsa.add_key(open(a.pubkey).read(), old=False)

    tag = random.randint(100000, 999999)
    pa, pb = f'7999{tag}1', f'7999{tag}2'

    print('1. handshake + wrong invite code')
    c = client(a.host, a.port)
    await c.connect()
    ok('MTProto handshake with your key')
    await c.send_code_request(pa)
    try:
        await c.sign_in(pa, 'wrong-code')
        sys.exit('FAIL: wrong invite code accepted')
    except (errors.PhoneCodeInvalidError, errors.PhoneCodeExpiredError):
        ok('wrong invite code rejected')
    await c.disconnect()

    print('2. sign up two users with the invite code')
    ca, ua = await sign_up(a.host, a.port, pa, a.invite, 'Alice')
    cb, ub = await sign_up(a.host, a.port, pb, a.invite, 'Bob')
    ok(f'Alice id={ua.id}, Bob id={ub.id}')

    print('3. find each other: by phone number and by @username')
    res = await ca(functions.contacts.ImportContactsRequest([types.InputPhoneContact(0, '+' + pb, 'Bob', '')]))
    if not res.users or res.users[0].id != ub.id:
        sys.exit(f'FAIL: contacts.importContacts did not find Bob: {res}')
    bob = res.users[0]
    ok('Alice added Bob by phone number')
    uname = f'alice{tag}'
    await ca(functions.account.UpdateUsernameRequest(uname))
    found = await cb(functions.contacts.ResolveUsernameRequest(uname))
    if not found.users or found.users[0].id != ua.id:
        sys.exit(f'FAIL: @{uname} not found')
    ok(f'Bob found @{uname}')

    print('4. message Alice -> Bob')
    text = f'privet {tag}'
    await ca.send_message(bob, text)
    await asyncio.sleep(2)
    msgs = await cb.get_messages(ua.id, limit=1)
    if not msgs or msgs[0].message != text:
        sys.exit(f'FAIL: Bob did not get the message: {msgs}')
    ok(f'Bob received "{text}"')

    print('5. invite code must not log into an existing account')
    c = client(a.host, a.port)
    await c.connect()
    await c.send_code_request(pa)
    try:
        await c.sign_in(pa, a.invite)
        sys.exit('FAIL: invite code logged into an existing account')
    except (errors.PhoneCodeInvalidError, errors.PhoneCodeExpiredError):
        ok('refused; the real login code went to Alice\'s logged-in device')
    await c.disconnect()

    for x in (ca, cb):
        await x.disconnect()
    print('ALL OK')


if __name__ == '__main__':
    asyncio.run(main())
