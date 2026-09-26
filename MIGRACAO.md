# Migração do instalador `.exe` antigo

> [!IMPORTANT]
> O incidente das versões 0.9.1 e 0.9.2 foi corrigido na **0.9.4** e a correção
> permanece na **0.9.7** para Elden Ring 1.17.1 (Steam BuildID auxiliar
> `25080141`). Não
> use 0.8.4, 0.9.1 ou 0.9.2 como
> alternativa: todas usam o pacote de bancos antigo.

> [!WARNING]
> Não é necessário baixar, copiar ou distribuir `appmanifest_1245620.acf`.
> Quem já colocou esse arquivo não será bloqueado por isso, mas ele contém apenas
> metadados locais da Steam e não atualiza o Elden Ring. A compatibilidade é
> decidida pelos arquivos reais; uma versão antiga não se torna 1.17.1 ao copiar
> o manifesto.

O executável das versões 0.8.x foi descontinuado. Ele não deve ser usado para
instalar, atualizar nem restaurar a dublagem depois de uma atualização do jogo.

O backup antigo `sd.bdt.original` não registra de qual BHD/build veio e cobre
apenas `sd.bdt`, embora o instalador também pudesse alterar `sd_dlc02.bdt`.
Restaurá-lo sobre o patch 1.17.1 pode misturar arquivos incompatíveis. Versões
antigas também podiam deixar `*.bk2.original` em `movie` e `movie_dlc`; esses
sidecars não possuem manifesto nem hash do build.

## Procedimento seguro

1. Feche Elden Ring e Easy Anti-Cheat.
2. No Windows, baixe `ERPT-BR-v0.9.7-Windows.zip` e extraia o ZIP inteiro. No
   Linux x86_64 ou Steam Deck em Modo Desktop, baixe
   `ERPT-BR-v0.9.7-Linux-x86_64.tar.gz` e extraia todo o arquivo em uma unidade
   `ext4`.
3. Abra `ERPT-BR.cmd` no Windows ou `ERPT-BR.sh` no Linux e clique em
   **Corrigir áudio (restaurar)** se houver um backup transacional válido das
   versões 0.9.x no mesmo sistema.
4. Se esse backup não existir ou a restauração falhar, na Steam abra **Biblioteca
   > Elden Ring > Propriedades > Arquivos instalados > Verificar integridade dos
   arquivos**.
5. Inicie o jogo uma vez e confirme que o áudio original funciona.
6. Abra novamente o launcher correspondente e clique em **Instalar dublagem**.

Somente depois de confirmar a recuperação, remova arquivos extras terminados em
`.bdt.original` dentro de `ELDEN RING\Game\sd` e `*.bk2.original` em
`ELDEN RING\Game\movie`/`movie_dlc`. A Steam pode preservar arquivos extras
durante a verificação.

O patcher atual bloqueia a instalação enquanto encontra um `.original` legado.
Ele preserva o arquivo e nunca tenta adivinhar se pertence ao build atual.

Não crie exceção no Defender, não restaure manualmente um backup antigo e não
execute o patcher como administrador, `sudo` ou root. Use a mesma conta do
sistema para instalar e restaurar. Antes de mover ou renomear a biblioteca
Steam, restaure o áudio original; se ela já foi movida com a dublagem aplicada,
verifique a integridade pela Steam.

O pacote 0.9.7 instala áudio WEM/BNK. Não copie para ele as pastas antigas
`movie` ou `movie_dlc`: o pacote opcional de cutscenes ainda não possui manifesto
criptográfico público e será recusado.

## Observações para Linux

O pacote Linux inclui CPython 3.13.15 portátil e dependências offline; não
instale Python nem execute o launcher com `sudo`. Ele procura a Steam nativa,
Flatpak e Snap, além das bibliotecas registradas em `libraryfolders.vdf`.

Backups não devem ser copiados manualmente entre Windows e Linux. O suporte
Linux da 0.9.7 é inicial, limitado a x86_64 e `ext4`; NTFS, exFAT e btrfs e o
modo online em Linux/Proton ainda precisam de testes específicos antes de serem
prometidos.
