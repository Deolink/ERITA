# ERPT-BR — Elden Ring Dublagem PT-BR

Projeto de dublagem em Português Brasileiro para Elden Ring no PC.

> [!IMPORTANT]
> A versão **0.9.7** instala a dublagem no Elden Ring **1.17.1**
> (Steam BuildID `25080141`). Os bancos de áudio foram reconstruídos sobre os
> bancos originais dessa versão para preservar sons adicionados pelo jogo,
> inclusive os cliques da interface que desapareciam nas versões 0.9.1 e 0.9.2.
> A 0.9.7 mantém exatamente esse áudio corrigido e a regra da 0.9.6 que torna o
> `appmanifest` da Steam opcional. Esta versão também adiciona um pacote portátil
> inicial para Linux x86_64 e Steam Deck no Modo Desktop.

## Download correto

Na página [Releases](https://github.com/lorepamplona/ERPT-BR/releases), baixe o
pacote correspondente ao seu sistema:

- Windows x64: `ERPT-BR-v0.9.7-Windows.zip`;
- Linux x86_64/Steam Deck: `ERPT-BR-v0.9.7-Linux-x86_64.tar.gz`.

Os dois são pacotes completos para o usuário: instalador em código-fonte,
dependências verificadas e payload de áudio. Não baixe os arquivos automáticos
**Source code** do GitHub e não tente executar separadamente arquivos internos
do payload.

## Instalação no Windows

1. Feche Elden Ring e Easy Anti-Cheat.
2. Extraia **todo** o conteúdo de `ERPT-BR-v0.9.7-Windows.zip` para uma pasta
   normal.
3. Dê dois cliques em `ERPT-BR.cmd`.
4. Confirme a pasta `ELDEN RING\Game` detectada pela Steam ou selecione-a.
5. Clique em **Instalar dublagem** e aguarde a confirmação final.
6. Abra o jogo normalmente pela Steam. Como um `appmanifest` pode ter sido
   copiado, ele nunca é usado para prometer disponibilidade online: confirme
   que a Steam reconhece e atualiza essa instalação antes de jogar online.

O usuário vê uma única entrada: `ERPT-BR.cmd`. No primeiro uso, ela verifica o
pacote e prepara um ambiente isolado. Se necessário, instala o CPython 3.13.15
x64 oficial no perfil do usuário. Nos próximos usos, o mesmo arquivo abre a
interface sem refazer uma instalação válida.

Não execute o patcher como administrador. Se o Windows negar gravação, feche o
jogo e o EAC e use uma biblioteca Steam gravável pela sua conta ou ajuste
somente a permissão da pasta do jogo.

## Instalação no Linux e Steam Deck

O suporte da 0.9.7 é inicial e destinado a **Linux x86_64**. No Steam Deck, use
o **Modo Desktop**.

1. Feche Elden Ring e Easy Anti-Cheat.
2. Extraia todo o conteúdo de `ERPT-BR-v0.9.7-Linux-x86_64.tar.gz` para uma
   pasta em uma unidade Linux `ext4`.
3. Execute `ERPT-BR.sh` pelo gerenciador de arquivos ou, em um terminal aberto
   na pasta extraída, use `./ERPT-BR.sh`.
4. Confirme a pasta `ELDEN RING/Game` detectada ou selecione-a manualmente.
5. Clique em **Instalar dublagem** e aguarde a confirmação final.
6. Abra o jogo normalmente pela mesma instalação da Steam.

O detector procura instalações da Steam nativa, Flatpak e Snap e também segue
as bibliotecas registradas em `libraryfolders.vdf`. O pacote inclui o runtime
portátil Astral `python-build-standalone` 20260924 com CPython 3.13.15 e todas
as dependências travadas. Portanto, a primeira execução não exige Python do
sistema, `sudo` nem acesso à rede. **Não execute como root.**

Esta primeira versão Linux precisa concluir a validação no CI e testes em
hardware real antes de receber promessa de funcionamento online. O suporte
inicial de sistema de arquivos é `ext4`; instalações do jogo ou do patcher em
NTFS, exFAT ou btrfs ainda não são prometidas sem testes específicos.

## Modo online

O payload de áudio mantido pela 0.9.7 foi testado no Windows em uma sessão real
na 0.9.4, iniciada normalmente pela Steam, com Easy Anti-Cheat e conexão online
ativos. O teste concluiu com sucesso e os sons de clique permaneceram
funcionando. As versões 0.9.5, 0.9.6 e 0.9.7 não alteram esse áudio. O patcher
não desativa nem modifica o EAC, não injeta bibliotecas e não muda a forma de
iniciar o jogo. Esse teste não valida automaticamente o novo ambiente
Linux/Proton; nele, o modo online continua sem promessa até haver teste físico
reproduzível.

O método direto altera dados dentro dos BDTs, mas não regrava nem reassina os
índices BHD. Assim, 8.973 recursos modificados não correspondem mais aos hashes
salted originais. O instalador aceita somente as divergências exatas do plano e
do payload autenticados; qualquer diferença adicional é recusada. A sessão
online bem-sucedida não remove essa limitação técnica.

Esse resultado comprova a versão e a sessão testadas; ele não representa
garantia de risco zero nem de compatibilidade com futuras atualizações do jogo,
do EAC ou das regras do serviço. Se a Steam atualizar o Elden Ring, restaure ou
verifique os arquivos e aguarde uma versão que reconheça o novo perfil real dos
arquivos.

Reconhecer o perfil local dos arquivos sem um manifesto válido confirma a
compatibilidade do áudio, mas não confirma que a instalação esteja registrada
na Steam nem que o modo online esteja disponível naquele ambiente. A ausência
do manifesto, por si só, **não bloqueia a instalação da dublagem**.

## O que mudou na 0.9.7

- novo pacote portátil para Linux x86_64 e Steam Deck no Modo Desktop;
- detecção da Steam nativa, Flatpak e Snap, incluindo bibliotecas adicionais
  registradas em `libraryfolders.vdf`;
- runtime Astral `python-build-standalone` 20260924 com CPython 3.13.15 fixado;
- dependências Linux incluídas e instaladas localmente em modo offline;
- nenhuma exigência de Python do sistema, `sudo` ou rede na primeira execução;
- mesmas validações do perfil real 1.17.1 e o mesmo payload autenticado da
  0.9.6.

## O que mudou na 0.9.6

- o `appmanifest_1245620.acf` deixou de ser obrigatório para instalar;
- manifesto ausente, ilegível, divergente ou copiado não bloqueia um perfil
  real de arquivos reconhecido;
- um manifesto copiado também nunca autoriza arquivos incompatíveis;
- a interface explica quando Steam e modo online não podem ser confirmados;
- os BHDs, os tamanhos dos BDTs e o baseline completo continuam autenticados
  antes da gravação;
- o payload de áudio é exatamente o mesmo pacote corrigido da 0.9.5.

## O que mudou na 0.9.5

- o áudio agora fica diretamente na pasta `patch_data` do pacote extraído;
- não existe mais um ZIP grande de áudio dentro do ZIP de download;
- a interface e o método de instalação permanecem os mesmos;
- o pacote continua sendo um único download e uma única entrada,
  `ERPT-BR.cmd`;
- o conteúdo de áudio é validado pelo mesmo inventário e SHA-256 canônico da
  árvore antes de qualquer gravação no jogo.

## Correção de áudio mantida desde a 0.9.4

- bancos Wwise reconstruídos usando a estrutura original do Elden Ring 1.17.1;
- mídias e eventos novos do jogo preservados durante a incorporação das falas;
- cliques de menu e demais sons originais ausentes no pacote antigo restaurados;
- instalação, reinstalação idempotente e restauração verificadas;
- validação do jogo repetida imediatamente antes de qualquer gravação;
- instalação de um clique sem executável próprio do projeto.

O payload autenticado contém 9.241 arquivos: 8.969 WEMs e 272 aliases BNK,
correspondentes a 136 bancos físicos reconstruídos. A árvore descompactada
possui 605.706.607 bytes e SHA-256 canônico
`8544e551832c929eecad0cf9898204fd673bd4a37a0a6f37433865afbb3556cb`.

## Quem usou 0.9.1 ou 0.9.2

Essas versões substituíam bancos atuais por bancos antigos e podiam remover
cliques do menu e sons de cutscenes. A versão 0.8.4 usa o mesmo payload antigo e
não é um fallback seguro.

Antes de instalar a 0.9.7:

1. Abra o pacote atual e use **Corrigir áudio (restaurar)** se existir um backup
   transacional válido.
2. Se a restauração não estiver disponível ou falhar, use **Steam > Elden Ring >
   Propriedades > Arquivos instalados > Verificar integridade**.
3. Confirme o áudio original e então instale a 0.9.7.

Consulte também a [migração do executável antigo](MIGRACAO.md) e o
[relatório do incidente](docs/INCIDENTE-0.9.1.md).

## Diagnóstico de compatibilidade e travamentos

A compatibilidade é decidida pelos arquivos de áudio instalados, não pelo
`appmanifest` da Steam. Na verificação rápida, o patcher confere o conjunto e o
SHA-256 dos índices BHD e os tamanhos dos BDTs. Antes de qualquer gravação, ele
também autentica o SHA-256 completo dos BDTs originais ou um backup previamente
autenticado.

O `appmanifest_1245620.acf` é somente uma informação auxiliar. Se estiver
ausente, ilegível ou indicar outro BuildID, mas o perfil real dos arquivos for
reconhecido, a instalação continua permitida e a interface informa que Steam e
modo online não foram confirmados. Isso também mantém o funcionamento para quem
já colocou um manifesto externo na biblioteca.

Não é necessário baixar, copiar nem distribuir esse manifesto. Ele não atualiza
nenhum arquivo do Elden Ring e nunca autoriza sozinho uma instalação. Uma versão
antiga só pode receber suporte completo por uma análise estrutural segura ou por
um perfil e payload próprios; fingir o BuildID da 1.17.1 não muda seus arquivos.

Arquivos incompatíveis usam o código `ERPT-FILES-001` e interrompem a operação
antes de alterar o jogo, com uma explicação que pode ser copiada no diagnóstico.

O botão **Diagnóstico** gera localmente um relatório JSON com versão do patcher,
BuildID informado, etapa, tempo, progresso, sistema e registros recentes. A
geração do relatório não inicia uma nova leitura dos arquivos do jogo e não
inclui hashes individuais, conteúdo do manifesto, saves, nome do usuário, pasta
completa ou SteamID. Ainda assim, revise o conteúdo antes de publicá-lo.

Nada é enviado automaticamente. O botão **Abrir chamado** apenas copia o
diagnóstico e abre o
[formulário de compatibilidade](https://github.com/lorepamplona/ERPT-BR/issues/new?template=compatibilidade.yml);
o envio continua manual e a issue será pública.

## Backup, restauração e atualizações

O backup fica em `%LOCALAPPDATA%\ERPT-BR\backups` no Windows. No Linux, fica em
`$XDG_STATE_HOME/ERPT-BR/backups` quando essa variável está definida, ou em
`~/.local/state/ERPT-BR/backups` por padrão. Ele é vinculado à instalação
selecionada e ao perfil real dos arquivos de áudio. O patcher
autentica os BHDs, os tamanhos dos BDTs e o SHA-256 completo dos BDTs originais,
prepara cópias temporárias, registra um journal transacional e relê o resultado
antes de anunciar sucesso. Um backup fora desse perfil nunca é restaurado sobre
o jogo atual.

Restaure o áudio original antes de mover ou renomear a biblioteca Steam. Use a
mesma conta do sistema para instalar e restaurar. Em caso de atualização do
jogo, faça a verificação de integridade da Steam e aguarde uma versão do ERPT-BR
que reconheça o novo perfil real dos arquivos.

Arquivos de transação interrompida são preservados para diagnóstico; o programa
não apaga recursivamente um caminho que possa ter sido substituído por link ou
junction.

## Limites atuais

- Windows x64;
- suporte inicial a Linux x86_64 e Steam Deck no Modo Desktop, com Steam
  nativa, Flatpak ou Snap;
- `ext4` é o sistema de arquivos Linux inicialmente suportado; NTFS, exFAT e
  btrfs ainda precisam de validação específica;
- Elden Ring 1.17.1, com BuildID Steam auxiliar correspondente `25080141`;
- áudio WEM/BNK; o pacote opcional antigo de cutscenes `.bk2` continua recusado
  por não possuir manifesto criptográfico público;
- futuras versões do jogo precisam de validação e release específicos.

## Desenvolvimento e testes

```text
python -m pip install --require-hashes --only-binary=:all: -r patcher/requirements-win64.lock
python -m unittest discover -s tests -v
```

O pacote Linux usa `patcher/requirements-linux-x86_64.lock` e o runtime
portátil fixado; o pacote de release é testado separadamente no CI antes da
publicação.

O CI rejeita launcher dinâmico, `exec(compile(...))`, `taskkill` e builds
PyInstaller/Nuitka. Releases são montados por lista permitida, com SHA-256 e
atestado de proveniência registrados pelo GitHub.

Relatos e código: [GitHub](https://github.com/lorepamplona/ERPT-BR)

Página do mod: [Nexus Mods](https://www.nexusmods.com/eldenring/mods/4295)

## Licença

[MIT](LICENSE)
