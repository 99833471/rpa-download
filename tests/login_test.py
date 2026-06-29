"""Testa a detecção de URLs de login/SSO (usada para não gravar/automatizar login).

Uso:  python tests/login_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.login_detect import is_auth_url  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    print("== Detecção de URL de login ==")
    auth = [
        "https://login.microsoftonline.com/cef.../saml2?sso_reload=true",
        "https://login.live.com/oauth20_authorize.srf",
        "https://empresa.okta.com/app/x",
        "https://host.com/adfs/ls/",
        "https://site.com/oauth2/authorize?x=1",
        # Keycloak / OpenID Connect (ex.: SSO Ambev) e a escolha de provedor.
        "https://auth.ambevdevs.com.br/realms/Ambev/protocol/openid-connect/auth?x=1",
        "https://empresa.keycloak.cloud/auth/realms/x",
        "https://wms.exemplo.com.br/wmsnew/multiple-realms",
    ]
    # Detecção ESTRITA: trechos genéricos no caminho (login/sso/signin) NÃO contam
    # como login — senão o gravador/executor pularia ações reais do app.
    notauth = [
        "https://wms.exemplo.com.br/wmsnew#",
        "https://wms.exemplo.com.br/wmsnew/sso-config",
        "https://app.com/login-page",
        "https://app.com/relatorios/signin-history",
        "https://app.com/dados?ini=01/06/2026",
    ]
    for u in auth:
        check(f"login: {u[:48]}", is_auth_url(u) is True)
    for u in notauth:
        check(f"app:   {u[:48]}", is_auth_url(u) is False)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: detecção de login - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
