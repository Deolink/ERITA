## ERPT-BR 0.9.7 — Linux, Steam Deck e mitigação para a Sellen

Esta versão adiciona um pacote portátil para **Linux x86_64** e **Steam Deck no
Modo Desktop** e aplica uma mitigação conservadora ao bug relatado na sequência
da Pedra Brilhante Primordial de Sellen.

### Downloads

- Windows x64: **`ERPT-BR-v0.9.7-Windows.zip`**;
- Linux x86_64/Steam Deck: **`ERPT-BR-v0.9.7-Linux-x86_64.tar.gz`**.

Não use os arquivos automáticos **Source code** do GitHub: eles não contêm o
runtime, as dependências e o payload completos.

> [!IMPORTANT]
> No Windows e no Linux, extraia a 0.9.7 em uma **pasta nova e vazia**. Não
> extraia por cima de uma versão anterior: o WEM retirado poderia permanecer
> como sobra e o instalador recusaria corretamente a árvore incompleta.

### O que mudou

- novo launcher transparente `ERPT-BR.sh` para Linux x86_64;
- detecção de Steam nativa, Flatpak e Snap;
- leitura das bibliotecas adicionais registradas em `libraryfolders.vdf`;
- runtime portátil Astral `python-build-standalone` 20260924 com CPython 3.13.15
  fixado e autenticado;
- wheels Linux travados por versão e SHA-256, instalados localmente em modo
  offline;
- primeira execução sem Python do sistema, `sudo`, root ou acesso à rede;
- o efeito não verbal `553755359.wem`, que excedia a duração original durante a
  animação da Sellen, agora permanece no áudio vanilla;
- nenhuma fala dublada da Sellen foi removida.

### Instalação no Linux

1. Feche Elden Ring e Easy Anti-Cheat.
2. Extraia todo o `tar.gz` em uma pasta nova e vazia localizada em `ext4`; não
   extraia por cima de uma versão anterior.
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

O payload-base já teve sessão online bem-sucedida no Windows. A mitigação da
Sellen restaura um único efeito ao vanilla, mas ainda precisa de confirmação na
missão. O teste anterior também não comprova o novo ambiente Linux/Proton. O
pacote Linux precisa concluir a validação no CI e um teste físico reproduzível
antes que o projeto prometa funcionamento online nessa plataforma.

### Integridade do áudio

O payload possui 8.968 WEMs e 272 aliases BNK. O SHA-256 canônico da árvore é:

`e97467e8ebbd1da87be96a44e4a2ee5694cd41c0bf592159b0570258d0b8460e`
