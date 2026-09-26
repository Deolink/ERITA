## ERPT-BR 0.9.6 — manifesto Steam opcional

Este hotfix corrige a instalação em cópias válidas do Elden Ring 1.17.1 que não
possuem `appmanifest_1245620.acf` na biblioteca detectada.

### O que mudou

- a compatibilidade agora é decidida pelos arquivos reais de áudio do jogo;
- manifesto ausente, ilegível, não vinculado ou com outro BuildID não bloqueia
  quando o perfil real 1.17.1 é reconhecido;
- quem já copiou o manifesto distribuído externamente pode deixá-lo no lugar e
  instalar normalmente;
- o manifesto nunca autoriza sozinho arquivos incompatíveis e não é copiado,
  baixado nem incluído pelo ERPT-BR;
- arquivos fora do perfil recebem o erro explícito `ERPT-FILES-001`, antes de
  qualquer alteração;
- a interface não usa o manifesto para prometer que Steam ou modo online estão
  confirmados.

O áudio não mudou: a 0.9.6 reutiliza exatamente o payload corrigido e
autenticado da 0.9.5, com 8.969 WEMs e 272 aliases BNK. O SHA-256 canônico da
árvore permanece
`8544e551832c929eecad0cf9898204fd673bd4a37a0a6f37433865afbb3556cb`.

### Download e instalação

Baixe somente **`ERPT-BR-v0.9.6-Windows.zip`**, extraia todo o conteúdo e dê
dois cliques em **`ERPT-BR.cmd`**. Não use os ZIPs automáticos **Source code** do
GitHub e não é necessário baixar nenhum ZIP de manifesto.

O pacote continua sem executável próprio do projeto, sem Mod Engine 3 e sem
desativar o Easy Anti-Cheat. Abra o jogo normalmente pela Steam e confirme que
ela reconhece e atualiza a instalação antes de jogar online.

### Limite desta versão

O hotfix remove a dependência do manifesto, não transforma arquivos antigos em
1.17.1. Os BHDs, os tamanhos dos BDTs e o baseline completo precisam
corresponder ao perfil homologado. Uma versão real diferente ainda precisa de
perfil e adaptação próprios; copiar um manifesto não altera os arquivos do jogo.
