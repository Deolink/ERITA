# Migração do instalador `.exe` antigo

O executável das versões 0.8.x foi descontinuado. Ele não deve ser usado para
instalar, atualizar nem restaurar a dublagem depois de uma atualização do jogo.

O backup antigo `sd.bdt.original` não registra de qual BHD/build veio e cobre
apenas `sd.bdt`, embora o instalador também pudesse alterar `sd_dlc02.bdt`.
Restaurá-lo sobre o patch 1.17.1 pode misturar arquivos incompatíveis.
Versões antigas também podiam deixar `*.bk2.original` nas pastas `movie` e
`movie_dlc`; esses sidecars não têm manifesto nem hash do build.

## Procedimento seguro

1. Feche Elden Ring e Easy Anti-Cheat.
2. Na Steam, abra **Biblioteca > Elden Ring > Propriedades > Arquivos
   instalados > Verificar integridade dos arquivos**.
3. Espere a Steam concluir e inicie o jogo uma vez para confirmar o áudio
   original. Feche o jogo novamente.
4. Só depois dessa verificação, remova os arquivos extras terminados em
   `.bdt.original` dentro de `ELDEN RING\Game\sd` e os `*.bk2.original` em
   `ELDEN RING\Game\movie`/`movie_dlc`. A Steam não costuma remover arquivos
   extras durante a verificação.
5. Instale a versão source seguindo o [README](README.md): extraia o ZIP inteiro
   e use sempre `ERPT-BR.cmd`. Ele instala no primeiro uso, abre nos seguintes e
   também repara automaticamente um ambiente incompleto.

O patcher novo bloqueia a instalação enquanto encontra um `.original` legado.
Ele o preserva e nunca tenta adivinhar se esse arquivo pertence ao build atual.

Se houver qualquer dúvida sobre o estado dos arquivos, repita a verificação da
Steam. Não crie uma exceção no Defender e não restaure manualmente o backup antigo.

Use a mesma conta do Windows para instalar e restaurar. Antes de mover ou renomear
a biblioteca Steam, restaure o áudio original; se ela já foi movida com a dublagem
aplicada, faça uma nova verificação de integridade pela Steam.

As cutscenes opcionais não são instaladas pela candidata 0.9.1, pois o pacote
antigo ainda não tem manifesto criptográfico público. Não copie pastas `movie`
ou `movie_dlc` para o novo instalador.
