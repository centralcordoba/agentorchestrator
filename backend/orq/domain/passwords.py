"""Cifrado de contraseñas y de testigos de sesión.

Se usa **scrypt** (RFC 7914), que viene en la biblioteca estándar. Es una función de derivación
lenta y con coste de memoria: probar contraseñas a lo bruto sale caro aunque alguien se lleve la
tabla. Se eligió frente a argon2 o bcrypt por no añadir una dependencia nativa al proyecto; el
formato guardado lleva el algoritmo por delante (`scrypt$n$r$p$sal$hash`), así que cambiar a
argon2 más adelante es añadir un verificador, no migrar a ciegas.

Dos cosas que no son negociables aquí:

- **La comparación es en tiempo constante** (`hmac.compare_digest`). Comparar con `==` filtra por
  el tiempo de respuesta cuántos bytes coinciden.
- **Nada de esto se registra.** Ni la contraseña, ni el testigo, ni el hash.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

#: Parámetros de scrypt. `n` es el coste: subirlo endurece el hash y ralentiza el login.
#: 2**14 tarda del orden de decenas de milisegundos, que es el equilibrio habitual para un login.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32

#: Bytes del testigo de sesión que viaja en la cookie. 32 bytes = 256 bits.
TOKEN_BYTES = 32


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    relleno = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + relleno)


def hash_password(password: str) -> str:
    """Devuelve `scrypt$n$r$p$sal$hash`. Cada llamada usa una sal nueva."""
    salt = secrets.token_bytes(SALT_BYTES)
    derivada = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_BYTES
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(derivada)}"


def verify_password(password: str, stored: str) -> bool:
    """¿La contraseña corresponde al hash guardado? Nunca lanza por un hash mal formado."""
    try:
        algoritmo, n, r, p, salt, esperado = stored.split("$")
        if algoritmo != "scrypt":
            return False
        derivada = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(esperado)),
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(derivada, _unb64(esperado))


def needs_rehash(stored: str) -> bool:
    """¿El hash se hizo con parámetros más flojos que los de ahora?

    Se comprueba al entrar: si los parámetros subieron, se vuelve a cifrar con los nuevos
    aprovechando que en ese momento sí se tiene la contraseña en claro.
    """
    try:
        algoritmo, n, r, p, _, _ = stored.split("$")
    except ValueError:
        return True
    return algoritmo != "scrypt" or (int(n), int(r), int(p)) != (SCRYPT_N, SCRYPT_R, SCRYPT_P)


def new_session_token() -> str:
    """Testigo de sesión. Es lo único que viaja en la cookie."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> str:
    """Lo que se guarda en la base.

    Es un SHA-256 sin sal, y aquí sí es correcto: el testigo tiene 256 bits de entropía, así que
    no hay diccionario que lo adivine. Lo que se busca es que un volcado de la tabla no permita
    suplantar a nadie, y para eso basta. Es la diferencia con una contraseña, que la elige una
    persona y por eso necesita una función lenta.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
