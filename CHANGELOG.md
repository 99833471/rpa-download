# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue, de forma simplificada, o [Keep a Changelog](https://keepachangelog.com/pt-BR/)
e o versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [1.0.0] - 2026-06-25

Primeira versão completa — todas as 5 fases implementadas e cobertas por testes.

### Adicionado

- **Fundação**
  - Estrutura visual (Telas → Blocos → Robôs) espelhada em pastas físicas no Windows.
  - Higienização de nomes inválidos e deduplicação automática.
  - Fila de retentativas para operações de pasta bloqueadas (arquivo em uso).
  - Dashboard em PySide6 com temas Light (Ambev) e Dark (AB InBev).
  - Drag-and-drop de Telas, Blocos e Robôs; Tela Home como destino pré-exclusão.
- **Gravação ("Aprender")**
  - Gravador baseado em Playwright (subprocesso) com mapeamento por DOM
    (seletores priorizados: id → data-* → name/aria → texto → CSS → XPath).
  - Sessão/login salvos criptografados (DPAPI do Windows).
  - Tipos de campo: Fixo, Fórmula e Manual.
  - Motor de fórmulas seguro (sem `eval`): `TODAY`, `WORKDAY` (feriados BR),
    `EOMONTH`, `EDATE`, `DATE`, `TEXT`, etc.
  - Revisão pós-gravação e fail-safe (não salva alterações se abandonado).
- **Execução**
  - Smart waits, auto-retry com backoff exponencial e evasão de pop-ups.
  - Fallback de seletor e fallback de login (sessão expirada → login manual).
  - Validação de integridade do download e nomeação `[timestamp] - [nome]`.
- **Limites do site**
  - Particionamento recursivo de datas até o site liberar o download.
- **Exportação**
  - Geração de `.exe` independente por robô (runner leve; baixa o navegador no
    primeiro uso).
- **Infra**
  - Suíte de testes automatizados (11 conjuntos) e documentação.

[1.0.0]: https://github.com/99833471/rpa-download/releases/tag/v1.0.0
