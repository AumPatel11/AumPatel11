"""Pure-Python self-signed HTTPS certificate generator.

iPhones can't pip-install the usual crypto libraries, and Safari only allows
the microphone on https pages, so Lumora makes its own certificate with
nothing but the standard library (RSA-2048, SHA-256).
"""
import datetime
import hashlib
import ipaddress
import secrets

# ---------------------------------------------------------------- RSA

_SMALL_PRIMES = [p for p in range(3, 2000) if all(p % d for d in range(2, int(p ** 0.5) + 1))]


def _is_probable_prime(n, rounds=40):
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits):
    while True:
        n = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _is_probable_prime(n):
            return n


def rsa_keypair(bits=2048, e=65537):
    while True:
        p, q = _prime(bits // 2), _prime(bits // 2)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        try:
            d = pow(e, -1, phi)
        except ValueError:
            continue
        n = p * q
        if n.bit_length() == bits:
            return {"n": n, "e": e, "d": d, "p": p, "q": q}


# ---------------------------------------------------------------- DER

def _len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag, body):
    return bytes([tag]) + _len(len(body)) + body


def _int(v):
    b = v.to_bytes(max(1, (v.bit_length() + 8) // 8), "big")  # keeps a leading 0 when needed
    return _tlv(0x02, b)


def _seq(*items):
    return _tlv(0x30, b"".join(items))


def _set(*items):
    return _tlv(0x31, b"".join(items))


def _oid(dotted):
    parts = [int(x) for x in dotted.split(".")]
    body = bytes([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.append(0x80 | (p & 0x7F))
            p >>= 7
        body += bytes(reversed(chunk))
    return _tlv(0x06, body)


def _bitstring(b):
    return _tlv(0x03, b"\x00" + b)


def _octets(b):
    return _tlv(0x04, b)


def _utf8(s):
    return _tlv(0x0C, s.encode())


def _time(dt):
    return _tlv(0x17, dt.strftime("%y%m%d%H%M%SZ").encode())


NULL = b"\x05\x00"
SHA256_RSA = _seq(_oid("1.2.840.113549.1.1.11"), NULL)
RSA_ENC = _seq(_oid("1.2.840.113549.1.1.1"), NULL)


def _pem(label, der):
    import base64
    b = base64.b64encode(der).decode()
    lines = [b[i:i + 64] for i in range(0, len(b), 64)]
    return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----\n"


def make_self_signed(ips=("127.0.0.1",), dns=("localhost",), cn="Lumora", days=800):
    """Return (cert_pem, key_pem). Validity stays under Apple's 825-day limit."""
    k = rsa_keypair()
    name = _seq(_set(_seq(_oid("2.5.4.3"), _utf8(cn))))
    now = datetime.datetime.now(datetime.timezone.utc)
    validity = _seq(_time(now - datetime.timedelta(days=1)), _time(now + datetime.timedelta(days=days)))
    spki = _seq(RSA_ENC, _bitstring(_seq(_int(k["n"]), _int(k["e"]))))

    alt = b"".join(_tlv(0x82, d.encode()) for d in dns)
    alt += b"".join(_tlv(0x87, ipaddress.ip_address(i).packed) for i in ips)
    exts = _seq(
        _seq(_oid("2.5.29.17"), _octets(_seq(alt))),                                    # subjectAltName
        _seq(_oid("2.5.29.37"), _octets(_seq(_oid("1.3.6.1.5.5.7.3.1")))),             # serverAuth
        _seq(_oid("2.5.29.19"), _octets(_seq())),                                       # CA:false
    )
    tbs = _seq(
        _tlv(0xA0, _int(2)),
        _int(secrets.randbits(63) + 1),
        SHA256_RSA, name, validity, name, spki,
        _tlv(0xA3, exts),
    )
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(tbs).digest()
    klen = (k["n"].bit_length() + 7) // 8
    em = b"\x00\x01" + b"\xff" * (klen - len(digest_info) - 3) + b"\x00" + digest_info
    sig = pow(int.from_bytes(em, "big"), k["d"], k["n"]).to_bytes(klen, "big")
    cert = _seq(tbs, SHA256_RSA, _bitstring(sig))

    p, q, d = k["p"], k["q"], k["d"]
    key = _seq(_int(0), _int(k["n"]), _int(k["e"]), _int(d), _int(p), _int(q),
               _int(d % (p - 1)), _int(d % (q - 1)), _int(pow(q, -1, p)))
    return _pem("CERTIFICATE", cert), _pem("RSA PRIVATE KEY", key)
