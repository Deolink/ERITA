## 🚨 Hotfix de recuperação — instalação suspensa

Esta versão impede novas instalações do pacote incompatível com o Elden Ring
1.17.1 e mantém a restauração em um clique para quem instalou a 0.9.1/0.9.2.

- Bloqueia a instalação antes de baixar o payload ou alterar arquivos do jogo.
- Destaca **Corrigir áudio (restaurar)** como ação principal.
- Mostra o código explícito `ERPT-AUDIO-001` no diagnóstico.
- Mantém o backup transacional e a restauração byte a byte.
- Documenta a incompatibilidade encontrada em `cs_main.bnk` e `cs_m41.bnk`.
- Adiciona verificação dos hashes salted registrados nos índices BHD.

### Para quem já instalou

1. Não entre no modo online ainda.
2. Abra `ERPT-BR.cmd`.
3. Clique em **Corrigir áudio (restaurar)**.
4. Se não houver backup válido, use **Steam > Elden Ring > Propriedades >
   Arquivos instalados > Verificar integridade**.

Não use a versão 0.8.4 como alternativa: ela contém o mesmo pacote de áudio
antigo. A instalação só será reativada depois que os bancos forem reconstruídos
sobre a versão 1.17.1 e os testes de menu, falas, cutscenes e EAC forem concluídos.
