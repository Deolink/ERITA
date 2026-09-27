# Política de segurança

## Modelo de distribuição

- O projeto não publica executável próprio.
- A versão 0.9.7 publica dois downloads destinados ao usuário:
  `ERPT-BR-v0.9.7-Windows.zip` para Windows x64 e
  `ERPT-BR-v0.9.7-Linux-x86_64.tar.gz` para Linux x86_64 e Steam Deck no Modo
  Desktop. Ambos contêm o código-fonte do patcher, launcher transparente,
  dependências travadas e o payload de áudio autenticado.
- Os arquivos automáticos **Source code** do GitHub não são instaladores e não
  contêm o pacote completo.
- O PyCryptodome inclui código nativo verificado, mas nada é copiado ou injetado
  como DLL no jogo.
- A etapa interna `interno/INSTALAR_AMBIENTE.cmd` prepara o ambiente usando
  somente os wheels incluídos e verificados. Não existe `exec`, `eval` ou
  download de código Python a partir de `main`.
- A única entrada pública, `ERPT-BR.cmd`, pode instalar exatamente o Python
  3.13.15 x64 oficial no perfil do usuário. Ela tenta primeiro o pacote
  `Python.Python.3.13`, versão `3.13.15`, fonte `winget`, escopo `user` e
  arquitetura `x64`, sem ignorar a verificação de hash do WinGet.
- Somente quando o WinGet está ausente, o bootstrap baixa o instalador oficial
  de `python.org`. Antes de executá-lo, exige 29.452.944 bytes, SHA-256
  `edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403`,
  assinatura Authenticode válida e o publicador Python Software Foundation.
- O Python é instalado no perfil atual, não é adicionado ao `PATH` e não há
  tentativa de autoelevação. O executável oficial não é incluído no ZIP do mod.
- No Linux, `ERPT-BR.sh` recusa root e prepara tudo dentro do perfil do usuário.
  O pacote inclui e autentica o runtime Astral `python-build-standalone`
  20260924, CPython 3.13.15 x86_64, sem free-threading, e wheels Linux fixados.
- A preparação Linux usa apenas o runtime, o lock e os wheels incluídos, com
  `pip --no-index --require-hashes --only-binary=:all:`. Ela não exige Python do
  sistema, `sudo` nem rede, inclusive na primeira execução.

## Integridade do payload de áudio

O payload foi reconstruído sobre os bancos originais do Elden Ring 1.17.1,
Steam BuildID `25080141`. O patcher valida antes do uso:

- formato distribuído desde a 0.9.5: pasta plana `patch_data`, sem arquivo compactado
  de áudio aninhado;
- SHA-256 canônico da árvore:
  `e97467e8ebbd1da87be96a44e4a2ee5694cd41c0bf592159b0570258d0b8460e`;
- inventário: 8.968 WEMs e 272 aliases BNK, total de 9.240 arquivos;
- tamanho descompactado: `605607009` bytes;
- maior arquivo: `74956066` bytes.

Qualquer diferença de tamanho, hash, estrutura, inventário ou caminho faz o
patcher recusar o payload antes de escrever no jogo.

O arquivo de origem usado para montar essa árvore permanece fixado em
588.370.781 bytes e SHA-256
`873a432f1f1a8a42fca0aa71610e019563b79da3772656c48280b31a80a858a6`.
Ele é apenas uma entrada autenticada do workflow e não é colocado dentro do ZIP
entregue ao usuário.

## Compatibilidade dos arquivos do jogo

O `appmanifest` da Steam não é uma autoridade de segurança e nunca autoriza ou
bloqueia sozinho uma instalação. O patcher usa os arquivos reais como
autoridade:

- exige os índices BHD e os pares BDT do perfil homologado;
- confere o SHA-256 dos BHDs e os tamanhos esperados dos BDTs na verificação
  rápida;
- antes da primeira gravação, confere o SHA-256 completo dos BDTs vanilla;
- em reinstalações e restaurações, aceita somente um baseline original
  previamente autenticado e o resultado registrado pelo próprio ERPT-BR.

Manifesto ausente, ilegível ou copiado não substitui nem invalida um perfil
local reconhecido. Nesses casos, a instalação da dublagem pode continuar, mas a
Steam e o modo online permanecem explicitamente não confirmados. Copiar um
manifesto externo não contorna nenhuma verificação dos arquivos reais.

## Easy Anti-Cheat e modo online

O patcher não usa Mod Engine 3, não inicia Elden Ring, não injeta bibliotecas,
não altera o Easy Anti-Cheat e não muda a forma de iniciar o jogo pela Steam. O
payload que serviu de base para a 0.9.7 foi validado no Windows em uma sessão real da 0.9.4
com EAC e conexão online ativos. A 0.9.5 alterou somente sua forma de
distribuição; a
0.9.6 altera somente a autoridade usada para reconhecer a compatibilidade,
mantendo o mesmo payload autenticado. A 0.9.7 porta o instalador para Linux e
mantém no vanilla um efeito não verbal da animação da Sellen; essa mitigação ainda
precisa de confirmação dentro da missão. A sessão Windows não comprova o
comportamento no Linux/Proton. O modo online no Linux só receberá afirmação de
suporte depois de validação no CI e teste físico reproduzível.

Os dados modificados nos BDTs não são acompanhados de regravação ou reassinatura
dos índices BHD. Consequentemente, os recursos modificados deixam de
corresponder aos hashes salted originais. No modo de produção, o patcher permite apenas essas
divergências quando elas pertencem exatamente aos slots do plano autenticado;
uma divergência fora desse escopo interrompe a instalação. O teste online não
transforma essa limitação em garantia de compatibilidade ou de ausência de risco.

Um teste bem-sucedido não equivale a garantia permanente de risco zero. Uma
atualização do jogo, do EAC ou das regras do serviço pode mudar o resultado. O
suporte é limitado ao perfil real dos arquivos e ao payload declarados no
release. O BuildID Steam, quando disponível, funciona como informação auxiliar
e não como prova do conteúdo instalado.

## Integridade do release

O release 0.9.7 publica um ZIP Windows e um `tar.gz` Linux próprios destinados ao
usuário. O GitHub registra o digest SHA-256 de cada asset e gera um atestado de
proveniência pelo GitHub Actions. Para verificar os pacotes com a CLI do GitHub:

```text
gh attestation verify ERPT-BR-v0.9.7-Windows.zip --repo lorepamplona/ERPT-BR
gh attestation verify ERPT-BR-v0.9.7-Linux-x86_64.tar.gz --repo lorepamplona/ERPT-BR
```

O workflow usa dependências travadas por SHA de commit e não deve sobrescrever
um asset de release existente. Os hashes finais são publicados somente depois
da montagem e verificação dos dois pacotes.

## Dados locais e privacidade

O programa não coleta telemetria nem envia arquivos do usuário. O payload de
áudio acompanha o pacote completo e é validado localmente. No Windows, o
bootstrap pode acessar WinGet ou `python.org` para instalar o Python oficial. No
Linux, o runtime e as dependências acompanham o `tar.gz` e a primeira execução
é offline.

Os botões **Detalhes** e **Abrir chamado** só pedem ao navegador padrão que abra
o GitHub depois de um clique explícito. O diagnóstico é processado localmente,
usa uma lista fechada de campos e remove padrões conhecidos de caminhos,
identidades, e-mails, SteamID e segredos. A geração do relatório não inicia uma
nova leitura dos arquivos do jogo nem inclui seus hashes; as verificações de
compatibilidade da operação são separadas. O usuário deve revisar e enviar o
conteúdo manualmente.

Backups, ambientes isolados e cache ficam no perfil local. No Linux, o suporte
inicial presume `ext4`; NTFS, exFAT e btrfs ainda não possuem promessa de
compatibilidade sem teste específico. Árvores abandonadas
ou transações interrompidas são preservadas e reportadas; o programa não tenta
exclusão recursiva por um caminho que possa ter sido trocado por junction ou
outro reparse point.

Esses controles partem de uma sessão normal do Windows ou Linux, sem outro
processo malicioso já executando como o mesmo usuário. Um processo com essa
autoridade já poderia alterar o fonte extraído, o ambiente local, os backups e
o jogo.

## Reportar vulnerabilidade

Não publique detalhes exploráveis em uma issue. Use **Security > Report a
vulnerability** no repositório quando disponível ou entre em contato
privadamente com o mantenedor listado no perfil do projeto.
