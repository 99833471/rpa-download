# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.
O formato segue, de forma simplificada, o [Keep a Changelog](https://keepachangelog.com/pt-BR/)
e o versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [1.3.0] - 2026-06-25

### Alterado

- **Renomeado para "RPA Download"**; a pasta de dados criada passa a se chamar
  **`RPA-DOWNLOAD`** (instalações novas; instalações existentes mantêm a pasta já
  configurada).

### Adicionado

- **Ícone próprio** do programa (janela, executável e **na pasta de dados** no
  Windows Explorer via desktop.ini).

### Mitigações de antivírus (falso positivo)

- Executável agora tem **metadados** (empresa/produto/versão), **ícone** e é
  compilado **sem UPX** — reduz a chance de o antivírus sinalizar.
- Observação: sem **assinatura digital (Authenticode)**, ainda pode haver alertas
  em alguns ambientes. Veja o README para como reportar falso positivo / liberar.

## [1.2.1] - 2026-06-25

### Corrigido

- **Painel de gravação** não é mais esticado/deformado pelo CSS do site: os
  estilos críticos (tamanho/posição) são aplicados com `!important` e reforçados
  periodicamente, mantendo o painel pequeno no canto inferior direito.
- **"Refazer caminho"** agora **descarta a sessão/cookies anteriores** daquele
  robô — o login (e similares) é refeito durante a nova gravação.

## [1.2.0] - 2026-06-25

### Adicionado

- **Log detalhado em CSV por execução** (`runs/run_<data>.csv`): uma linha por
  passo com data/hora, período, ação, campo, seletor, valor, **status** e **erro** —
  para analisar exatamente onde falhou. (separador `;`, abre no Excel BR)
- **"Redefinir campos"** no menu do robô (botão direito): altera **valor e tipo**
  (Fixo/Fórmula/Manual) dos campos capturados **sem regravar** o caminho.
- **Painel de gravação compacto** no canto inferior direito, mostrando em tempo
  real o **histórico de campos reconhecidos e valores**.

### Alterado / Corrigido

- O gravador agora reconhece **seletores de data e campos preenchidos via
  JavaScript** (captura por foco + saída do campo + snapshot ao concluir); antes
  esses campos podiam não ser reconhecidos.
- Todos os campos tocados viram campos editáveis (padrão **Fixo** = repete o valor).
- O navegador de gravação abre **maximizado e sem a margem cinza** (no_viewport).
- A execução tenta **digitar a data no campo** (fallback para campos readonly/JS).

## [1.1.1] - 2026-06-25

### Adicionado

- **Executável único (`.exe` onefile)** pronto para uso no release — basta baixar
  e abrir, sem extrair `.zip`. O `.zip` (modo pasta, abertura mais rápida)
  continua disponível como alternativa.
- `tools/build_app.py` agora também gera o `.exe` único (`build_onefile`).

## [1.1.0] - 2026-06-25

### Adicionado

- **Aplicativo standalone (`.exe`)**: o programa principal agora pode ser
  empacotado num executável que **não exige Python** no computador do usuário
  (distribuído como `.zip`, com `LEIAME.txt`). O navegador (Chromium) é baixado no
  primeiro uso.
- Scripts de build/validação: `tools/build_app.py`, `build_app.bat`,
  `tools/validate_app.py`.

### Alterado

- Subprocessos de execução/gravação agora funcionam no app congelado via um
  **despachante** no próprio executável (substitui `python -m ...`).
- `PLAYWRIGHT_BROWSERS_PATH` é fixado em um local estável; navegador baixado sob
  demanda também no app principal.

### Observações

- No app empacotado, a exportação de robô individual em `.exe` fica desabilitada
  (requer a versão por código, com PyInstaller).

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
