# Guia do RPA Download

Bem-vindo! Este guia ensina, passo a passo, a usar o **RPA Download** — um programa
que **grava** as suas ações em um site e depois as **repete sozinho** para baixar
dados/relatórios automaticamente.

> Este mesmo guia está disponível dentro do programa (botão **📖 Guia**) e no
> GitHub. Ele é atualizado conforme o programa evolui.

---

## 1. Instalar (sem precisar de Python nem de administrador)

1. Baixe o **`RPA-DOWNLOAD.zip`** na página de *Releases* do projeto.
2. **Extraia** o `.zip` (clique direito → *Extrair tudo*). **Não** rode de dentro
   do zip.
3. Abra **`RPA Download.exe`** dentro da pasta extraída.
4. Na **primeira execução** o programa se **instala sozinho** em
   `%LOCALAPPDATA%\Programs\RPA Download`, cria um atalho na pasta **Documentos** e
   no **Menu Iniciar** (ficando **pesquisável** — é só digitar "RPA Download") e
   passa a rodar de lá. Você pode **apagar a pasta extraída** depois.

Na primeira vez que um robô rodar, o navegador (Chromium) é baixado
automaticamente — precisa de internet uma única vez.

> **Onde ficam os dados:** o programa cria sozinho a pasta
> `%LOCALAPPDATA%\RPA Download` (banco, robôs, downloads e sessões). Não é preciso
> escolher caminho.

---

## 2. Como o programa é organizado

A tela principal organiza tudo em três níveis, espelhados em pastas no Windows:

- **Telas** — abas no topo (ex.: "Geral").
- **Blocos** — grupos dentro de uma Tela (ex.: "Principal").
- **Robôs** — cada robô é uma automação que baixa um dado específico.

Use **arrastar e soltar** para reorganizar. O botão direito em cada item abre o
menu de ações (renomear, mover, excluir, etc.).

---

## 3. Criar um robô (gravar = "Aprender")

1. Adicione um robô no bloco desejado e escolha **Aprender / Gravar**.
2. O **navegador abre** (em tela cheia). **Faça login normalmente**, se o site
   pedir — o login **não** é gravado; ele é salvo de forma **criptografada** e
   reaproveitado nas próximas execuções.
3. **Navegue e faça as ações** que quer automatizar:
   - **Cliques** em botões, links e ícones são gravados.
   - **Preenchimento** de campos (texto, datas) é gravado.
   - A tecla **Enter** é gravada (útil para confirmar buscas/filtros).
   - O **download** do arquivo é capturado automaticamente.
4. Ao terminar, use o painel de gravação (canto da tela) para **Concluir**.

> Dica: clique no **elemento certo** (ex.: o botão "Baixar"). O programa identifica
> o elemento por características estáveis do site, não por posição na tela.

---

## 4. Revisar a gravação ("o que fazer com cada passo")

Depois de gravar, abre a tela de **revisão**, listando cada passo. Para cada um:

- **Nome**: dê um nome claro (ex.: "Clicar em Exportar").
- **O que fazer**:
  - **Repetir (normal)** — refaz a ação sempre.
  - **Clicar se aparecer (opcional)** — para **pop-ups/avisos** que às vezes
    aparecem; se não estiver na tela, o passo é **pulado sem erro**.
- Para campos preenchidos, escolha o **tipo de valor**:
  - **Fixo** — repete exatamente o que você digitou.
  - **Fórmula** — calcula o valor na hora (ex.: data de hoje). Ao escolher, abre o
    **editor de fórmula** (com prévia do resultado). Veja a seção 5.
  - **Manual** — o programa **pergunta o valor** toda vez que o robô roda. Ao
    escolher, abre a **configuração** do campo (tipo de dado). Reabra pelo botão
    **⚙ / ƒ** ao lado do valor.
- **Downloads**: defina se a cada execução o robô deve **Acumular** (mantém todos,
  com data/hora no nome) ou **Sobrescrever** (mantém só o mais recente).

Também há o **questionário de limites do site** (seção 7).

---

## 5. Fórmulas (valores que mudam, como datas e cálculos)

O **editor de fórmula** mostra o **resultado ao vivo** conforme você digita (verde =
ok; vermelho = erro) e tem uma **lista de funções pesquisável** (duplo-clique
insere o exemplo). O botão **ƒ Fórmulas disponíveis** também lista tudo, com busca.

As fórmulas podem ser **combinadas** e usar **aritmética**: `TODAY()+1`,
`WORKDAY(TODAY(); -1)`, `(2+3)*4`, `ROUND(10/3; 2)`.

Categorias disponíveis:
- **Datas**: `TODAY`, `NOW`, `DATE`, `WORKDAY`, `WORKDAYS`, `EOMONTH`, `SOMONTH`,
  `EDATE`, `YEAR`, `MONTH`, `DAY`, `WEEKDAY`, `WEEKNUM`, `QUARTER`, `HOUR/MINUTE/SECOND`.
- **Números**: `ROUND`, `ROUNDUP/DOWN`, `INT`, `TRUNC`, `ABS`, `MOD`, `POWER`,
  `SQRT`, `CEILING`, `FLOOR`, `MIN`, `MAX`, `SUM`, `AVERAGE` (e `+ - * /`).
- **Texto**: `CONCAT`, `UPPER`, `LOWER`, `TRIM`, `LEFT`, `RIGHT`, `MID`, `LEN`,
  `ZEROPAD` (zeros à esquerda, ex.: `6` → `06`), `SUBSTITUTE`, `VALUE`.
- **Lógica**: `IF(cond; a; b)`, `AND`, `OR`, `NOT` e comparações `= <> < > <= >=`.

Formato de saída com **TEXT**: datas (`TEXT(TODAY(); "yyyy-mm-dd")`) e números, com
**vírgula** decimal para sites BR (`TEXT(1234.5; "#.##0,00")` → `1.234,50`).

As fórmulas são calculadas com segurança (sem executar código arbitrário).

---

## 6. Executar um robô

1. Clique em **Executar** no robô (ou botão direito → Executar).
2. Por padrão o **navegador abre visível**, mostrando o passo a passo. Para rodar
   de forma invisível, desmarque **👁 Navegador visível** no topo.
3. Se a **sessão expirou**, o programa avisa e abre a janela para você **logar de
   novo**; clique em "Já fiz login, continuar" e ele retoma.
4. Se algum campo for **Manual**, abre uma janela (em tela cheia) para você
   **preencher os valores** daquela execução.
5. Os arquivos baixados vão para a pasta do robô. Acesse rápido pelo **botão
   direito → 📂 Abrir pasta de downloads**.

Cada execução gera um **log** (`.csv`) com o que aconteceu em cada passo — útil
para entender uma eventual falha.

---

## 7. Sites que limitam a quantidade por download

Se o site recusa baixar períodos muito grandes, marque, na revisão, que **o site
limita** os resultados. O programa então **divide o período por datas
automaticamente** (recursivamente) e baixa em partes até conseguir.

---

## 8. Manter atualizado

Clique em **🔄 Atualizar** no topo. O programa verifica a versão mais recente,
baixa o `.zip`, **troca a pasta inteira** sozinho (esperando ele fechar) e reabre.

---

## 9. Aparência e dicas

- **Tema**: alterne entre **claro** e **escuro** no botão **Modo claro / Modo
  escuro**, no topo.
- **Janelas em tela cheia**: a janela principal, o navegador de execução e a
  janela de valores abrem **maximizados**.
- **Antivírus/SmartScreen**: como o programa não é assinado digitalmente, pode
  haver um alerta de falso positivo. Em "Mais informações → Executar assim mesmo",
  ou adicione a pasta às exceções.

---

## 10. Problemas comuns

- **"Não baixou o arquivo"**: confirme que o passo de clique no botão de baixar foi
  gravado; regrave o robô se necessário. O log `.csv` mostra onde parou.
- **"Pediu login de novo"**: a sessão expirou; basta logar na janela quando o
  programa pedir — ele salva a nova sessão.
- **Primeira execução lenta**: é o download único do navegador (Chromium).

---

*Dúvidas ou sugestões? Abra uma issue no repositório do projeto.*
