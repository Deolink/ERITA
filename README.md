# ERPT-BR — Elden Ring Dublagem PT-BR

> [!CAUTION]
> **Instalação temporariamente suspensa no Elden Ring 1.17.1.** Identificamos
> que o pacote de áudio usado pelas versões 0.9.1 e 0.9.2 substitui bancos mais
> antigos que removem sons presentes no jogo atual, inclusive recursos curtos
> compatíveis com os cliques da interface. **Não instale essas versões.** Se já
> instalou, baixe a versão 0.9.3 e use **Corrigir áudio (restaurar)**. Se o botão não estiver
> disponível ou a restauração falhar, use **Steam > Propriedades > Arquivos
> instalados > Verificar integridade**. Não entre no modo online antes de
> restaurar. Consulte [o relatório do incidente](docs/INCIDENTE-0.9.1.md).

Projeto de dublagem em Português Brasileiro para Elden Ring no PC. A versão
0.9.3 é um **hotfix somente de recuperação** para o Elden Ring 1.17.1 (Steam
BuildID 25080141): ela abandona o executável próprio, impede novas instalações
do pacote afetado e restaura backups seguros criados pelas versões 0.9.x.

## O modo online continua funcionando?

Neste momento, **não use a dublagem no modo online**. A validação encontrou
incompatibilidades de bancos e de integridade no método direto das versões
0.9.1/0.9.2. Restaure primeiro os arquivos originais, confira o áudio original
no jogo e só então volte ao modo online.

O objetivo futuro continua sendo dispensar Mod Engine 3, injeção de DLL e
alterações no Easy Anti-Cheat. Isso não é uma promessa de compatibilidade para o
pacote atualmente suspenso. O projeto só voltará a anunciar suporte online após
um teste real de menu, falas, cutscenes e sessão com EAC no release corrigido.

## Novo método de instalação

O hotfix 0.9.3 não contém `.exe` criado ou empacotado pelo projeto. Ele traz:

- todo o código-fonte Python visível;
- scripts `.cmd` incluídos como texto aberto para auditoria;
- dependências oficiais em wheels, com versões e SHA-256 travados;
- o verificador e o restaurador transacional dos arquivos originais.

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

## Recuperação no Windows

Enquanto a instalação estiver suspensa, use somente a versão 0.9.3 para
recuperação. Ela bloqueia novas instalações antes de baixar o payload ou alterar
o jogo e destaca **Corrigir áudio (restaurar)**. Se não houver um backup válido,
faça a verificação de integridade da Steam. Não use as versões 0.8.4, 0.9.1 ou
0.9.2 como fallback: elas contêm o mesmo pacote de áudio antigo.

## Instalação no Windows (suspensa)

Se você já usou o `.exe` antigo, faça primeiro a [migração segura](MIGRACAO.md).

### Recuperação: um único arquivo

1. Para recuperar uma instalação afetada, baixe
   `ERPT-BR-v0.9.3-source-win64.zip` na página
   [Releases](https://github.com/lorepamplona/ERPT-BR/releases). Não use o ZIP
   automático “Source code”, pois ele não contém as dependências offline.
2. Extraia o ZIP inteiro para uma pasta normal.
3. Dê dois cliques em `ERPT-BR.cmd`. Se o Python correto estiver
   ausente, o script instala a versão oficial no seu perfil; depois prepara o
   ambiente e abre o patcher.
4. Selecione a pasta `ELDEN RING\Game` e clique em **Corrigir áudio
   (restaurar)**.
5. Aguarde a confirmação de que os BDTs originais foram restaurados e
   verificados. Se não houver backup válido ou ocorrer uma falha, use a
   verificação de integridade da Steam.
6. Abra o jogo primeiro para conferir os cliques e o áudio originais. Só depois
   dessa confirmação volte ao modo online.

Para abrir novamente o hotfix de recuperação, use sempre o mesmo `ERPT-BR.cmd`.

Não execute o patcher como administrador. Se o Windows negar gravação, use uma
biblioteca Steam gravável pela sua conta ou ajuste somente a permissão da pasta
do jogo; o programa nunca tenta se elevar sozinho.

O 0.9.3 para antes da aquisição do payload de voz. Ele não baixa nem aplica o
asset de áudio v0.8.1 suspenso.

Uma cópia de backup interrompida pode deixar uma pasta oculta
`.xxxxxxxxxxxx-xxxxxxxx` ao lado dos backups. O patcher registra o caminho exato
e a preserva; remova-a manualmente somente depois de confirmar que ela não é o
único backup útil.

## Diagnóstico de compatibilidade e travamentos

Uma versão do jogo fora do alvo, como a 1.17.0, não fica mais parecendo uma
instalação parada: o patcher mostra o BuildID encontrado, o BuildID suportado, a
etapa em que interrompeu e um código estável como `ERPT-COMPAT-001`. A recusa
acontece antes de carregar ou alterar os arquivos de áudio.

O botão **Diagnóstico** permanece disponível até durante uma operação. Ele gera
localmente um relatório JSON com versão do patcher, BuildID já identificado,
etapa, tempo nessa etapa, último progresso, sistema e registros recentes.
Quando há uma falha, a explicação aparece imediatamente enquanto esse relatório
é preparado em segundo plano.
O relatório não cria campos para nome do usuário, pasta completa, SteamID, saves
ou conteúdo do manifesto e remove padrões conhecidos desses dados nos textos de
erro. O diagnóstico também não abre nem calcula hash dos arquivos do jogo. Ainda
assim, revise o conteúdo antes de publicá-lo.

Nada é enviado automaticamente. Na janela do relatório, o usuário pode revisar,
copiar, salvar ou clicar em **Abrir chamado**. Esse último botão apenas copia o
diagnóstico e abre o
[formulário de compatibilidade](https://github.com/lorepamplona/ERPT-BR/issues/new?template=compatibilidade.yml);
o envio continua manual e a issue será pública. Não anexe saves nem arquivos do
jogo.

## Backup, restauração e atualizações do jogo

O 0.9.3 recusa qualquer nova aplicação. Para restaurar, ele vincula o backup ao
fingerprint do BHD/build, autentica o backup e o estado atual, prepara cópias
temporárias, registra um journal de recuperação e relê o resultado antes de
anunciar sucesso. Também valida os hashes salted do BHD antes que uma futura
aplicação possa criar backup ou trocar BDTs.

O backup existente fica fora da pasta do jogo, em
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

## Limites deste hotfix

O hotfix público está limitado ao Steam BuildID 25080141 e só recupera backups
0.9.x correspondentes a esse fingerprint. Ele não instala falas, BNKs, WEMs ou
cutscenes `.bk2`. Pastas `movie`/`movie_dlc` ao lado do instalador continuam
recusadas; o pacote opcional antigo não possui manifesto criptográfico público.

## Validação pendente

O bootstrap, o rollback e o instalador distribuído em fonte têm testes
automatizados. A auditoria na instalação real confirmou que o backup original é
íntegro e restaurável; também mostrou que o pacote antigo remove conteúdo do
`cs_main.bnk` atual e deixa 8.976 recursos fora dos hashes salted do BHD.

As versões `v0.9.1` e `v0.9.2` não devem ser tratadas como instaláveis. O próximo
release funcional só poderá ser promovido depois de reconstruir os bancos sobre
a versão 1.17.1 e concluir testes reais de menu, falas, cutscenes, restauração e
sessão online com EAC.

## Desenvolvimento e testes

```text
python -m pip install --require-hashes --only-binary=:all: -r patcher/requirements-win64.lock
python -m unittest discover -s tests -v
```

O CI rejeita a volta do launcher dinâmico, de `exec(compile(...))`, de
`taskkill` e de builds PyInstaller/Nuitka. Releases são montados por lista
permitida e publicam um único ZIP próprio, com digest SHA-256 e atestado de
proveniência registrados pelo GitHub. O 0.9.3 é publicado como Latest apenas por
ser a recuperação segura; releases funcionais continuam como pre-release até o
smoke test real ser concluído.

Relatos e código: [GitHub](https://github.com/lorepamplona/ERPT-BR)

Página do mod: [Nexus Mods](https://www.nexusmods.com/eldenring/mods/4295)

## Licença

[MIT](LICENSE)
