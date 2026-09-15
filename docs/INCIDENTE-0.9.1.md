# Incidente de áudio nas versões 0.9.1 e 0.9.2

## Estado

**Instalação suspensa.** Este aviso afeta as versões 0.9.1 e 0.9.2 no Elden
Ring 1.17.1 (Steam BuildID 25080141). A versão 0.8.4 não é um fallback seguro,
pois usa o mesmo pacote de áudio antigo.

## Sintoma

Foram relatados sons ausentes na interface, incluindo cliques do menu, depois da
instalação da dublagem.

## O que fazer agora

1. Não abra o modo online enquanto os arquivos modificados estiverem instalados.
2. Feche o Elden Ring e o Easy Anti-Cheat.
3. Baixe/abra o ERPT-BR 0.9.3 e clique em **Corrigir áudio (restaurar)**. Nas
   versões anteriores, o mesmo botão aparece como **Restaurar original**.
4. Se o backup não estiver disponível ou a restauração falhar, use **Steam >
   Elden Ring > Propriedades > Arquivos instalados > Verificar integridade dos
   arquivos**.
5. Abra o jogo primeiro para confirmar os cliques e os sons originais; só então
   volte ao modo online.

## Diagnóstico técnico

A instalação auditada não teve falha aleatória de cópia: os 9.105 slots gravados
coincidem exatamente com o plano do patcher e os bytes fora deles permanecem
iguais ao backup. O problema está no conteúdo e no método:

- as versões 0.9.1 e 0.9.2 reutilizam o pacote `v0.8.1`, anterior ao build atual;
- o `enus/cs_main.bnk` desse pacote remove três mídias e 234 objetos HIRC que
  existem no banco original do Elden Ring 1.17.1;
- o `enus/cs_m41.bnk` remove outras cinco mídias;
- 8.976 recursos alterados deixam de corresponder aos hashes salted registrados
  nos índices BHD originais.

O backup transacional da instalação auditada permaneceu íntegro. A correção será
construída sobre os bancos originais da versão 1.17.1, preservando as mídias e os
eventos adicionados pelo jogo. O release só deve voltar a ser instalável após
testes reais de clique de menu, falas, cutscenes do jogo base e DLC, restauração
e sessão online com o Easy Anti-Cheat.
