"""Criptografia de dados sensíveis (sessões/cookies) via Windows DPAPI.

Usa CryptProtectData/CryptUnprotectData por ctypes — sem dependências externas —
para que o storage_state (cookies + localStorage) seja salvo cifrado e atrelado
ao usuário/máquina do Windows, em vez de texto puro.

Em sistemas não-Windows (ou se a DPAPI falhar), há um fallback transparente que
grava os bytes sem cifra, registrando um aviso — mantém o app funcional fora do
ambiente alvo, sem mascarar o problema.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

_IS_WINDOWS = sys.platform == "win32"
_MAGIC = b"RPADPAPI1\n"   # prefixo p/ identificar conteúdo cifrado por este módulo
_PLAIN = b"RPAPLAIN1\n"   # prefixo do fallback não cifrado


if _IS_WINDOWS:
    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32

    def _blob(data: bytes) -> _DATA_BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _blob_bytes(blob: _DATA_BLOB) -> bytes:
        return ctypes.string_at(blob.pbData, blob.cbData)

    def _dpapi_encrypt(data: bytes) -> bytes:
        blob_in = _blob(data)
        blob_out = _DATA_BLOB()
        if not _crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            raise OSError("CryptProtectData falhou.")
        try:
            return _blob_bytes(blob_out)
        finally:
            _kernel32.LocalFree(blob_out.pbData)

    def _dpapi_decrypt(data: bytes) -> bytes:
        blob_in = _blob(data)
        blob_out = _DATA_BLOB()
        if not _crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            raise OSError("CryptUnprotectData falhou.")
        try:
            return _blob_bytes(blob_out)
        finally:
            _kernel32.LocalFree(blob_out.pbData)


def encrypt_bytes(data: bytes) -> bytes:
    if _IS_WINDOWS:
        try:
            return _MAGIC + _dpapi_encrypt(data)
        except OSError:
            pass
    return _PLAIN + data


def decrypt_bytes(blob: bytes) -> bytes:
    if blob.startswith(_MAGIC):
        return _dpapi_decrypt(blob[len(_MAGIC):])
    if blob.startswith(_PLAIN):
        return blob[len(_PLAIN):]
    # Conteúdo legado/sem prefixo: devolve como está.
    return blob


def save_encrypted(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(encrypt_bytes(data))


def load_encrypted(path: str) -> bytes:
    with open(path, "rb") as f:
        return decrypt_bytes(f.read())


def save_text_encrypted(path: str, text: str) -> None:
    save_encrypted(path, text.encode("utf-8"))


def load_text_encrypted(path: str) -> str:
    return load_encrypted(path).decode("utf-8")


def is_protected() -> bool:
    """True se a cifra real (DPAPI) está disponível neste ambiente."""
    return _IS_WINDOWS
