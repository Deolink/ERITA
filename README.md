# ERPT-BR — Elden Ring Dublagem PT-BR

Instalador para aplicar a dublagem em Português Brasileiro diretamente nos
arquivos de áudio do Elden Ring para PC.

Esta versão candidata tem como alvo técnico o **Elden Ring 1.17.1 (Steam build
25080141)** e abandona o executável próprio que causava alertas de antivírus.
O par patch/BuildID foi identificado, mas a publicação estável ainda depende do
teste descrito em [Validação pendente](#validação-pendente).

## O modo online continua funcionando?

O ERPT-BR **não usa Mod Engine 3**, não injeta DLL no jogo, não desativa o Easy
Anti-Cheat e não muda a forma de iniciar o jogo. Depois de instalar a dublagem,
abra o Elden Ring normalmente pela Steam.

O patcher só substitui áudio dentro dos arquivos `sd*.bdt` já usados pelo jogo.
Essa arquitetura preserva a inicialização online normal. Como o serviço online
e as regras de anti-cheat pertencem a terceiros e podem mudar, o projeto não
promete risco externo absolutamente zero. O patcher já foi validado contra os
arquivos reais do build alvo instalado; ainda falta o teste de abertura, login e
sessão online com o Easy Anti-Cheat.

## Novo método de instalação

O release do mod não contém `.exe` criado ou empacotado pelo projeto. Ele traz:

- todo o código-fonte Python visível;
- scripts `.cmd` incluídos como texto aberto para auditoria;
- dependências oficiais em wheels, com versões e SHA-256 travados;
- metadados fixos de URL, tamanho e SHA-256 para autenticar o pacote de áudio.

O usuário vê uma única entrada: `ERPT-BR.cmd`. No primeiro uso, ela verifica uma
instalação compatível, instala exatamente o Python 3.13.15 x64 no perfil do
usuário quando necessário, prepara o ambiente e abre o patcher. Nos próximos
usos, o mesmo arquivo valida rapidamente o ambiente e abre a interface sem
reinstalar tudo. Os dois scripts auxiliares ficam na pasta `interno` e não devem
ser executados diretamente.

O fluxo usa primeiro o pacote exato `Python.Python.3.13` do WinGet; somente se o
WinGet não estiver disponível, baixa o instalador oficial da Python Software
Foundation e valida tamanho, SHA-256, assinatura Authenticode e publicador antes
de executá-lo. Se o WinGet estiver presente mas falhar, o bootstrap para e mostra
o erro em vez de mudar silenciosamente de origem. Não solicita elevação, não
adiciona Python ao `PATH` e usa somente os wheels incluídos no ZIP. Se um Python
compatível já estiver instalado, ele é tratado como uma base confiada pelo
usuário. Em todos os casos, o `python.exe` não é produzido pelo mod.

Uma migração para C#, Rust ou outra linguagem não removeria os alertas por si
só: ela voltaria a criar um executável próprio sem reputação ou assinatura de
código. Por isso, a alternativa de um clique mantém o código do mod aberto e
delega apenas a instalação do interpretador a canais oficiais autenticados.

## Instalação no Windows

Se você já usou o `.exe` antigo, faça primeiro a [migração segura](MIGRACAO.md).

### Instalação e uso: um único arquivo

1. Baixe `ERPT-BR-v0.9.1-source-win64.zip` na página
   [Releases](https://github.com/lorepamplona/ERPT-BR/releases). Não use o ZIP
   automático “Source code”, pois ele não contém as dependências offline.
2. Extraia o ZIP inteiro para uma pasta normal.
3. Dê dois cliques em `ERPT-BR.cmd`. Se o Python correto estiver
   ausente, o script instala a versão oficial no seu perfil; depois prepara o
   ambiente e abre o patcher.
4. Selecione `ELDEN RING\Game` e instale.
5. Ao terminar, feche o patcher e abra o jogo normalmente pela Steam.

Para abrir ou reparar o ERPT-BR depois, use sempre o mesmo `ERPT-BR.cmd`.

Não execute o patcher como administrador. Se o Windows negar gravação, use uma
biblioteca Steam gravável pela sua conta ou ajuste somente a permissão da pasta
do jogo; o programa nunca tenta se elevar sozinho.

Na primeira aplicação, os dados de voz (aproximadamente 560 MiB) são baixados
do asset v0.8.1 e autenticados pelo tamanho e SHA-256 fixos
`d66bb45093e911202f80cebac44650063e27da2cba41a78760b10e4d82d81d0c`.
Depois da extração, cada caminho, tamanho e byte também participa do digest de
árvore `587533f29239d8dbe2131573e6e86a2452b272e76983f6cfef1a332d7b046417`.
Eles ficam em cache para as próximas instalações, mas o conteúdo é revalidado
criptograficamente antes do uso.
Se uma troca de cache for interrompida, árvores `.extract-*`/`.old-*` são
preservadas em quarentena em vez de apagadas recursivamente. Depois de confirmar
uma instalação correta, elas podem ser movidas para fora do cache e removidas
manualmente para recuperar espaço.

Da mesma forma, uma cópia de backup interrompida pode deixar uma pasta oculta
`.xxxxxxxxxxxx-xxxxxxxx` ao lado dos backups. O patcher registra o caminho exato
e a preserva; remova-a manualmente somente depois de confirmar que ela não é o
único backup útil.

## Backup e atualizações do jogo

Antes de trocar qualquer arquivo, o patcher:

1. valida o BHD instalado e todos os offsets contra o BDT atual;
2. exige que 100% dos 9.241 arquivos do payload encontrem slots compatíveis e
   valida o plano inteiro antes de escrever;
3. cria backup de **todos** os BDTs de áudio carregados, inclusive os que o
   payload atual ainda não altera;
4. aplica a dublagem em cópias temporárias;
5. relê e compara cada região;
6. registra um journal de recuperação e só então troca as cópias pelos arquivos
   ativos sem sobrescrever um arquivo que reapareça durante a operação;
7. calcula novamente o SHA-256 de cada BDT alterado antes de anunciar sucesso.

Reserve alguns GiB livres. O backup fica fora da pasta do jogo, em
`%LOCALAPPDATA%\ERPT-BR\backups`, e é vinculado ao fingerprint do build. Um
backup de versão antiga nunca é restaurado sobre um BHD novo.

Restaure o áudio original **antes de mover ou renomear a biblioteca Steam**. Se
a biblioteca já foi movida enquanto a dublagem estava aplicada, use a verificação
de integridade da Steam antes de instalar novamente; o patcher procura manifests
de caminhos anteriores e se recusa a transformar áudio dublado em novo baseline.
Use sempre a mesma conta do Windows para instalar, atualizar e restaurar o mod.
Os backups ficam no perfil dessa conta e não coordenam operações iniciadas por
outro usuário do mesmo computador.

Quando a Steam atualizar o Elden Ring, use **Propriedades > Arquivos instalados >
Verificar integridade dos arquivos** e aguarde uma versão do ERPT-BR que tenha o
novo BuildID como alvo. Se um backup seguro de outro build impedir a criação do
novo baseline, confirme primeiro o áudio original e mova aquela pasta de backup
específica para outro local; o patcher nunca a apaga automaticamente.
Se houver uma transação interrompida, a mensagem também lista os arquivos
privados `.rollback`/`.displaced` que devem ser preservados na mesma quarentena,
fora de `Game\sd`, para não deixar resíduos grandes nem perder evidência de recuperação.
Cópias `.erptbr-stage-*`/`.erptbr-restore-*` deixadas por uma interrupção também
são preservadas e têm o caminho registrado para limpeza manual segura.

## Limites desta atualização

O motor aceita dinamicamente os pares `sd.bhd`/`sd.bdt` e `sd_dlcNN.bhd`/
`sd_dlcNN.bdt`, mas o instalador público está deliberadamente limitado ao build
Steam 25080141. As falas novas do Tarnished Pack que ainda não façam parte do
payload permanecem no idioma original; o instalador não as anuncia como dubladas.

As cutscenes `.bk2` não são instaladas nesta candidata. O pacote opcional antigo
não possui um manifesto público que fixe caminhos, tamanhos e SHA-256; por isso,
arquivos `.bk2` diretamente nas pastas `movie` ou `movie_dlc` ao lado do
instalador são recusados antes de qualquer alteração. O recurso só deve voltar
depois da publicação e validação desse manifesto.

## Validação pendente

O motor, o rollback e o instalador distribuído em fonte têm testes automatizados. O
payload público real foi baixado e validado integralmente: 8.969 WEM + 272 BNK,
604.911.847 bytes. Nesta máquina, o bootstrap também foi executado sem Python
previamente instalado e o ZIP final passou pelo dry-run contra os BHD/BDT reais do
Steam build 25080141: os 9.241 arquivos foram autenticados e correspondem a 9.105
slots físicos únicos, sem arquivo sem destino. A aplicação completa também foi
executada em uma cópia temporária dos BHD/BDT reais: todos os slots foram relidos,
e a restauração final coincidiu byte a byte com o estado anterior, sem resíduos.
Ainda faltam os testes que alteram ou executam a instalação usada pela Steam:

- aplicação seguida de restauração na própria biblioteca Steam;
- abertura do jogo e conferência de falas;
- login, summon/invasão e encerramento de uma sessão online com o EAC normal.

Por isso, trate `v0.9.1` como candidata até esse smoke test ser concluído. O
patcher bloqueia outros BuildIDs e não altera executável, DLL, save, launcher ou
Easy Anti-Cheat.

## Desenvolvimento e testes

```text
python -m pip install --require-hashes --only-binary=:all: -r patcher/requirements-win64.lock
python -m unittest discover -s tests -v
```

O CI rejeita a volta do launcher dinâmico, de `exec(compile(...))`, de
`taskkill` e de builds PyInstaller/Nuitka. Releases são montados por lista
permitida e publicam um único ZIP próprio, com digest SHA-256 e atestado de
proveniência registrados pelo GitHub. Enquanto o smoke test real estiver
pendente, o workflow publica a versão como pre-release.

Relatos e código: [GitHub](https://github.com/lorepamplona/ERPT-BR)

Página do mod: [Nexus Mods](https://www.nexusmods.com/eldenring/mods/4295)

## Licença

[MIT](LICENSE)
