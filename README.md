# AUTOMATIZADOR DOWNLOAD DE DADOS

Aplicativo desktop (Python) que funciona como **orquestrador/dashboard** de robôs
de extração de dados em sites. O usuário cria, organiza e executa robôs em uma
interface visual cuja estrutura é **espelhada em pastas físicas no Windows**.

> Status atual: **todas as fases concluídas** — 1 (Fundação), 2 (Gravação),
> 3 (Execução), 4 (Limites adaptativos) e 5 (Exportação `.exe`).

---

## ⬇️ Usar o programa pronto (sem instalar Python)

Quem só quer **usar** não precisa de Python. Há duas formas (compartilhadas
internamente — OneDrive / rede / e-mail):

- **`AUTOMATIZADOR_DOWNLOAD_DE_DADOS.exe`** — arquivo **único, pronto para uso**:
  basta dar duplo-clique. (Abre um pouco mais devagar na 1ª vez de cada execução,
  pois se descompacta sozinho.)
- **`AUTOMATIZADOR_DOWNLOAD_DE_DADOS.zip`** — versão em pasta: **extraia** e abra o
  `AUTOMATIZADOR DOWNLOAD DE DADOS.exe` de dentro dela. Abre mais rápido.

Na primeira vez que um robô rodar, o navegador (Chromium) é baixado
automaticamente (precisa de internet uma vez).

**Atualizar:** substitua o `.exe`/pasta pela versão mais recente.

> O repositório é **privado**. Colaboradores com acesso podem baixar o `.zip` em
> [Releases](https://github.com/99833471/rpa-download/releases/latest); para
> **desenvolver pelo código**, veja *Instalação* abaixo.

---

## Stack

| Camada | Tecnologia | Motivo |
|---|---|---|
| Interface gráfica | **PySide6 (Qt)** | Drag-and-drop, movimentação livre de ícones, temas QSS, menus de contexto. |
| Persistência de metadados | **SQLite** | Ordem/descrição/posição que as pastas não guardam + fila de retry persistente. |
| Manifesto por robô | **JSON** | Portabilidade do robô (habilita exportação `.exe`). |
| Automação web | **Playwright** | Auto-waiting, `storage_state` para sessões, captura de downloads, gravador. |
| Sessões/login | **DPAPI (Windows)** | Cookies/localStorage salvos criptografados por usuário. |
| Empacotamento | **PyInstaller** | App standalone (`.exe`) e exportação de robô individual. |

---

## Instalação

Pré-requisitos: **Windows** + **Python 3.12+** + **Git** (ou GitHub Desktop).

```powershell
git clone https://github.com/99833471/rpa-download.git
cd rpa-download
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
```

## Como executar

```powershell
.venv\Scripts\python main.py
```

Ou simplesmente dê **duplo-clique em `run.bat`**.

Na **primeira execução** o programa pede um diretório raiz e cria dentro dele a
pasta `AUTOMATIZADOR DOWNLOAD DE DADOS`. A configuração (raiz escolhida + tema)
fica em `%LOCALAPPDATA%\RPADownload\config.json`. O banco fica em
`<raiz>\AUTOMATIZADOR DOWNLOAD DE DADOS\.rpa\app.db`.

## Manter sempre na versão mais recente

O projeto já inclui o **`atualizar.bat`**: dê **duplo-clique** nele para baixar a
versão mais recente do GitHub (`git pull`) e atualizar dependências e o navegador
automaticamente.

Se você ainda não tiver esse arquivo (ou quiser recriá-lo), crie um arquivo de
texto chamado **`atualizar.bat`** na pasta do projeto com o conteúdo abaixo — ele
**sempre busca a versão mais recente** sempre que for executado:

```bat
@echo off
cd /d "%~dp0"
git pull origin main
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -m playwright install chromium
pause
```

> Como criar pelo Bloco de Notas: abra o Bloco de Notas, cole o conteúdo, vá em
> *Arquivo → Salvar como*, escolha *Tipo: Todos os arquivos* e salve como
> `atualizar.bat` dentro da pasta do projeto. Pronto — é só dar duplo-clique
> sempre que quiser atualizar.

Fluxo recomendado no dia a dia: **`atualizar.bat`** (atualiza) → **`run.bat`** (abre).

---

## O que já funciona (Fase 1)

- **Espelhamento de pastas**: cada Tela/Bloco/Robô vira uma pasta física
  `…/AUTOMATIZADOR…/<Tela>/<Bloco>/<Robô>/`. Criar, renomear, mover e excluir na
  UI reflete no disco. Renomear uma Tela move toda a subárvore.
- **Higienização de nomes**: remove `< > : " / \ | ? *` e nomes reservados do
  Windows; deduplica colisões como o Explorer (` (2)`, ` (3)`).
- **Fila de retentativas (fallback de arquivos)**: se uma operação de pasta
  falhar por bloqueio do Windows (arquivo em uso), ela é registrada em
  `pending_ops` e repetida em background (`RetryWorker`) e na próxima
  inicialização — o programa **não trava**.
- **Dashboard com temas**: Light (azul/branco, Ambev) e Dark (preto/dourado,
  AB InBev), alternáveis no topo.
- **Telas (abas)**: criar, renomear, descrição, excluir e **reordenar por
  arrastar**. A Tela `Home` é especial (não pode ser excluída) e é o destino de
  robôs deletados antes da exclusão definitiva.
- **Blocos (landscape)**: altura mínima para 3 linhas de ícones; criar,
  renomear, descrição, excluir, **reordenar (arrastando pela alça ⠿ ou pelo
  menu)** e mover entre telas.
- **Robôs (ícones)**: ícones quadrados (grande/pequeno) com **drag-and-drop**
  entre blocos e telas; menu de contexto com Executar, Renomear, Adicionar
  descrição, Refazer caminho, Mover para…, Gerar `.exe` e Deletar
  (move para a Home; apagar de novo lá exclui em definitivo).

A ação Gerar `.exe` exibe aviso de que será habilitada na fase final.

## O que já funciona (Fase 2 — gravação)

- **Gravar caminho**: ao criar um robô (ou via “Refazer caminho”), o app abre o
  Chromium (Playwright) com um overlay de controle (✔ Concluir / ✕ Cancelar). As
  ações são mapeadas pelo **DOM** (nunca por coordenadas), com candidatos de
  seletor priorizados e únicos (`id → data-* → name/aria → texto → CSS → XPath`).
- **Login/sessão**: o `storage_state` (cookies + localStorage) é salvo
  **criptografado** (DPAPI do Windows) em `session.bin` na pasta do robô. Senhas
  digitadas **não** são gravadas no manifesto.
- **Revisão**: ao concluir, uma tela permite definir, por campo, o tipo
  **Fixo / Fórmula / Manual** e o questionário de **limites do site** (máx. de
  linhas + estratégia + quais passos são as datas).
- **Motor de fórmulas** (sem `eval`): `TODAY()`, `NOW()`, `DATE()`, `WORKDAY(…; -1)`
  (com feriados nacionais BR), `EOMONTH`, `EDATE`, `TEXT(…; "yyyy-mm-dd")`, etc.
- **Subprocesso isolado** (QProcess): o navegador roda em outro processo, sem
  congelar a UI nem conflitar com o loop do Qt.
- **Fail-safe**: cancelar no navegador, descartar na revisão ou erro **restaura
  integralmente** o robô anterior (manifesto + sessão).

## O que já funciona (Fase 3 — execução)

- **Executar** (menu do robô): roda o `robot.json` em Chromium **headless**
  ("execução invisível"), usando a sessão criptografada.
- **Smart waits**: espera o elemento ficar visível/clicável (sem `sleep` fixo).
- **Auto-retry com backoff exponencial**: até 3 tentativas por ação.
- **Evasão de pop-ups**: fecha banners de cookies/avisos ("Aceitar", "Fechar",
  "X", etc.) e refaz a ação interceptada.
- **Fallback de seletor**: tenta cada candidato até um funcionar.
- **Campos**: `Fixo` literal; `Fórmula` avaliada na hora (feriados BR); `Manual`
  perguntado por pop-up **antes** de iniciar.
- **Download**: captura, valida integridade (0 bytes/corrompido → refaz) e salva
  na subpasta do robô como `[timestamp] - [nome]` (mantém o original se já houver
  timestamp por regex).
- **Fallback de login (sessão expirada)**: se aparecer campo de senha, abre o
  navegador na tela para login manual, recaptura a sessão e retoma a execução.
- **Log por execução** em `runs/run_<timestamp>.log` na pasta do robô.

## O que já funciona (Fase 4 — limites adaptativos)

- Se o robô foi marcado com **limite do site** (estratégia "particionar por
  data"), a execução tenta o intervalo inteiro e, se o site **não liberar** o
  download, divide o período ao meio **recursivamente** até cada subintervalo
  liberar — baixando um arquivo por período. A detecção é genérica (ausência de
  download = recusa por limite), sem depender de mensagem específica do site.

## O que já funciona (Fase 5 — exportação .exe)

- Menu do robô → **Gerar executável (.exe)**: pergunta o nome e a pasta de
  destino e gera um `.exe` independente (PyInstaller) embutindo o `robot.json` e
  a sessão. Validado de ponta a ponta (o `.exe` roda e baixa o arquivo).
- **Runner leve**: o navegador não é embutido (exe ~47 MB). Na primeira execução
  em outra máquina, o Chromium é baixado automaticamente; se houver login e a
  sessão não valer naquela máquina, o login é solicitado e a nova sessão é salva
  ao lado do `.exe`.

---

## Estrutura do código

```
main.py                      Ponto de entrada (primeira execução, seed, worker)
app/
  config.py                  Config, primeira execução, tema
  sanitize.py                Higienização e unicidade de nomes de pasta
  models.py                  Dataclasses Screen/Block/Robot
  db.py                      Camada SQLite (CRUD + fila pending_ops)
  bootstrap.py               Seed da estrutura inicial (Home + exemplo)
  formula.py                 Motor de fórmulas seguro (sem eval)
  robot_manifest.py          Schema do robot.json (passos/campos/limites/sessão)
  services/
    folder_mirror.py         Espelhamento físico + merge seguro + fila
    retry_worker.py          QThread que esvazia a fila em background
    crypto.py                Criptografia de sessão via DPAPI (ctypes)
  recorder/
    recorder.js              Script injetado: captura + seletores + overlay
    recorder_core.py         RecordingSession (núcleo testável)
    recorder_process.py      Subprocesso do gravador (Playwright headed)
  executor/
    executor_core.py         ExecutionEngine (retry/backoff, pop-ups, download)
    executor_process.py      Subprocesso do executor + fallback de login
    partition.py             Particionamento recursivo de datas (limites)
  exporter/
    robot_runner.py          Entrada do .exe (runner leve; baixa navegador 1º uso)
    build_exe.py             Comando do PyInstaller (embute robot.json/sessão)
  ui/
    theme.py                 Paletas + QSS + geração de ícones
    dialogs.py               Diálogos auxiliares
    dashboard.py             Telas/Blocos/Robôs + todas as ações e DnD
    main_window.py           Janela + barra superior + alternância de tema
    recording_controller.py  Orquestra QProcess -> revisão -> robot.json + fail-safe
    recording_review.py      Diálogo de revisão (tipos de campo + limites)
    execution_controller.py  Resolve valores -> QProcess executor -> status/log
    export_controller.py     Gera o .exe (PyInstaller) em background
    widgets/
      robot_list.py          Grade de ícones de robôs (DnD)
      block_widget.py        Cartão de bloco (alça de arrasto)
      constants.py           Formatos MIME de DnD
tests/
  smoke_test.py              Sanitização + DB + pastas + UI (offscreen)
  worker_test.py             Fila de retry com bloqueio real + worker
  formula_test.py            Fórmulas + manifesto + criptografia
  recorder_capture_test.py   Captura de seletores (Playwright headless)
  recorder_session_test.py   Núcleo da gravação + subprocesso
  review_test.py             Diálogo de revisão -> RobotManifest (offscreen)
  executor_core_test.py      Retry/pop-up/fallback/download (headless)
  executor_process_test.py   Subprocesso executor de ponta a ponta
  partition_test.py          Particionamento (planner + site fake que limita)
  runner_test.py             Runner standalone do robô
  exe_build_test.py          Build do .exe + execução (LENTO; fora da suíte)
```

### Testes

```powershell
$env:QT_QPA_PLATFORM="offscreen"; $env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python tests\smoke_test.py
.venv\Scripts\python tests\worker_test.py
.venv\Scripts\python tests\formula_test.py
.venv\Scripts\python tests\recorder_capture_test.py
.venv\Scripts\python tests\recorder_session_test.py
.venv\Scripts\python tests\review_test.py
.venv\Scripts\python tests\executor_core_test.py
.venv\Scripts\python tests\executor_process_test.py
.venv\Scripts\python tests\partition_test.py
.venv\Scripts\python tests\runner_test.py
```

O `exe_build_test.py` é opcional e lento (constrói um `.exe` real); rode-o à
parte quando quiser validar a exportação.

---

## Status das fases

Todas as 5 fases estão implementadas e cobertas por testes:

1. ✅ Fundação (pastas espelhadas, fila de retry, dashboard, temas)
2. ✅ Gravação (Playwright, seletores, sessão, fórmulas, fail-safe)
3. ✅ Execução (smart waits, retry, pop-ups, login, download)
4. ✅ Limites adaptativos (particionamento recursivo de datas)
5. ✅ Exportação `.exe` (runner leve)

### Melhorias futuras possíveis

- Estratégia de **paginação** para limites (hoje o foco é particionar por data).
- Histórico de execuções com painel na UI (hoje há log por execução em `runs/`).
- Marcação de um "indicador de login" para detecção de sessão mais precisa.
