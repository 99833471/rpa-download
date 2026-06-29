"""Detecção de páginas/URLs de login (SSO, Microsoft, etc.).

Usado para: (1) o gravador NÃO registrar ações feitas em páginas de login
(o login vira sessão/cookies, não passos); (2) o executor reconhecer que caiu
numa tela de login e acionar o fallback de login manual.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Trechos de host típicos de provedores de identidade / login SSO.
_AUTH_HOST_SUBSTRINGS = (
    "login.microsoftonline.com", "login.microsoft.com", "login.live.com",
    "login.windows.net", "msauth", "sts.", "adfs", ".okta.com", "okta.com",
    "onelogin.com", "pingidentity", "auth0.com", "accounts.google.com",
    "signin.aws", "fs.", "keycloak",
)
# Caminhos ESPECÍFICOS de fluxos de autenticação (evita falso-positivo: trechos
# genéricos como "/login", "/sso", "/signin" foram removidos porque podem existir
# em rotas legítimas do app e fariam o gravador/executor pular ações reais).
# Inclui Keycloak/OpenID Connect (/realms/.../protocol/openid-connect/...) e a
# página de escolha de provedor SSO (realm chooser).
_AUTH_PATH_SUBSTRINGS = ("/saml2", "/adfs/ls", "/oauth2/authorize",
                         "/oauth2/v2.0/authorize", "/openid/connect/authorize",
                         "/protocol/openid-connect/", "/realms/",
                         "/multiple-realms")


def is_auth_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if any(sub in host for sub in _AUTH_HOST_SUBSTRINGS):
        return True
    return any(sub in path for sub in _AUTH_PATH_SUBSTRINGS)
