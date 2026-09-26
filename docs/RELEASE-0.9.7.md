## ERPT-BR 0.9.7 — suporte inicial a Linux e Steam Deck

Esta versão adiciona um pacote portátil para **Linux x86_64** e **Steam Deck no
Modo Desktop**, sem alterar o payload de áudio corrigido da linha 0.9.x.

### Downloads

- Windows x64: **`ERPT-BR-v0.9.7-Windows.zip`**;
- Linux x86_64/Steam Deck: **`ERPT-BR-v0.9.7-Linux-x86_64.tar.gz`**.

Não use os arquivos automáticos **Source code** do GitHub: eles não contêm o
runtime, as dependências e o payload completos.

### O que mudou

- novo launcher transparente `ERPT-BR.sh` para Linux x86_64;
- detecção de Steam nativa, Flatpak e Snap;
- leitura das bibliotecas adicionais registradas em `libraryfolders.vdf`;
- runtime portátil Astral `python-build-standalone` 20260924 com CPython 3.13.15
  fixado e autenticado;
- wheels Linux travados por versão e SHA-256, instalados localmente em modo
  offline;
- primeira execução sem Python do sistema, `sudo`, root ou acesso à rede;
- os pacotes Windows e Linux mantêm o mesmo payload de áudio autenticado da
  0.9.6.

### Instalação no Linux

1. Feche Elden Ring e Easy Anti-Cheat.
2. Extraia todo o `tar.gz` em uma pasta localizada em `ext4`.
3. Execute `ERPT-BR.sh` sem `sudo`.
4. Confirme a pasta `ELDEN RING/Game` detectada ou selecione-a manualmente.
5. Instale a dublagem e abra o jogo normalmente pela mesma Steam.

No Steam Deck, faça o procedimento no **Modo Desktop**.

### Compatibilidade e manifesto Steam

O `appmanifest_1245620.acf` continua opcional. Sua ausência, divergência ou
presença por cópia externa não bloqueia um perfil real reconhecido, e quem já
possui esse arquivo pode deixá-lo no lugar. O manifesto também nunca autoriza
arquivos incompatíveis.

Os arquivos reais de áudio do Elden Ring 1.17.1 continuam sendo a autoridade.
Os BHDs, os tamanhos dos BDTs e o baseline completo precisam corresponder ao
perfil homologado; uma versão antiga não se torna compatível ao copiar um
manifesto.

### Escopo inicial do suporte Linux

O alvo desta versão é Linux x86_64 em `ext4`, incluindo Steam Deck no Modo
Desktop. NTFS, exFAT e btrfs ainda não possuem promessa de compatibilidade sem
testes específicos.

O payload já teve sessão online bem-sucedida no Windows, mas isso não comprova o
novo ambiente Linux/Proton. O pacote Linux precisa concluir a validação no CI e
um teste físico reproduzível antes que o projeto prometa funcionamento online
nessa plataforma.

### Integridade do áudio

O payload permanece com 8.969 WEMs e 272 aliases BNK. O SHA-256 canônico da
árvore continua:

`8544e551832c929eecad0cf9898204fd673bd4a37a0a6f37433865afbb3556cb`
