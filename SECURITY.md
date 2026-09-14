# Política de segurança

## Modelo de distribuição

- O projeto não publica executável próprio.
- O release Windows contém o fonte do patcher, scripts `.cmd` transparentes e
  wheels fixados. O PyCryptodome inclui código nativo verificado, mas nada é
  copiado ou injetado como DLL no jogo.
- A etapa interna `interno/INSTALAR_AMBIENTE.cmd` prepara o ambiente sem baixar
  código: o código do projeto e as dependências do mod vêm somente do ZIP
  publicado. O intérprete e a biblioteca padrão vêm de uma instalação compatível
  preexistente, que é parte da base confiada pelo usuário. Não existe `exec`,
  `eval` ou download de código Python a partir de `main`.
- A única entrada pública, `ERPT-BR.cmd`, pode instalar exatamente o Python
  3.13.15 x64 no perfil do usuário. Ele tenta primeiro o pacote exato
  `Python.Python.3.13`, versão `3.13.15`, fonte `winget`, escopo `user` e
  arquitetura `x64`, sem ignorar a verificação de hash do WinGet. Somente quando
  o WinGet está ausente, ele baixa
  `https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe`.
- Antes de executar esse instalador oficial, o bootstrap exige exatamente
  29.452.944 bytes, SHA-256
  `edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403`,
  assinatura Authenticode válida e o publicador
  `CN=Python Software Foundation, O=Python Software Foundation, L=Beaverton, S=Oregon, C=US`.
  Ele instala somente no perfil atual, não adiciona Python ao `PATH` e não tenta
  autoelevação. O executável oficial não é incluído no ZIP do mod.
- O download de dados em runtime é `patch_data_v081.zip`, tratado como dado e
  validado por HTTPS, tamanho, SHA-256, estrutura ZIP e um digest canônico de
  todos os caminhos, tamanhos e bytes extraídos.
- Quando o ambiente Python está ausente ou inválido, o instalador o recria usando
  apenas os wheels locais verificados. Um ambiente íntegro é reutilizado; o fluxo
  não encerra processos, não se autoeleva e não se autoatualiza.
- O patcher não usa Mod Engine 3, não inicia Elden Ring, não injeta bibliotecas,
  não altera o EAC e não muda a forma de iniciar o jogo pela Steam.
- O pacote opcional de cutscenes antigo é recusado: ele ainda não possui um
  manifesto público com caminhos, tamanhos e SHA-256 fixados.

## Integridade de release

Cada release source desta nova linha publica um único ZIP próprio. O GitHub
registra o digest SHA-256 do asset e gera um atestado de proveniência pelo GitHub
Actions. Para verificar um artefato com a CLI do GitHub:

```text
gh attestation verify ERPT-BR-v0.9.2-source-win64.zip --repo lorepamplona/ERPT-BR
```

O workflow usa dependências travadas por SHA de commit e nunca sobrescreve um
asset de release existente.

Esses controles partem de uma sessão normal do Windows, sem outro processo
malicioso já executando como o mesmo usuário. Um processo com essa autoridade já
poderia alterar o fonte extraído, o ambiente local, os backups e os arquivos do
jogo; o instalador não tenta substituir as proteções da conta ou do sistema.

## Dados locais

O programa não coleta telemetria nem envia arquivos do usuário. Em segundo plano,
o patcher acessa a rede somente quando precisa baixar o payload de áudio fixado.
O bootstrap de um clique também pode acessar WinGet ou `python.org` para instalar
o Python oficial, conforme descrito acima. Os botões **Projeto** e **Abrir chamado**
só pedem ao navegador padrão que abra o GitHub depois de um clique explícito; o
relatório não é anexado à URL. Backups de áudio, ambientes isolados e cache ficam
no perfil local do usuário.
Árvores de cache abandonadas são preservadas com nomes `.extract-*`/`.old-*`;
o programa não tenta exclusão recursiva por um caminho que possa ter sido trocado
por junction. A interface registra o caminho exato para limpeza manual posterior.
Pastas de staging de backups interrompidos seguem a mesma regra: são preservadas
e reportadas, nunca removidas recursivamente de forma automática.

O diagnóstico de suporte é processado localmente; somente o compartilhamento é
opcional. Ele usa uma lista fechada de campos e remove padrões conhecidos de
caminhos, identidades, e-mails, SteamID e segredos dos textos. Para evitar que
uma troca concorrente de junction faça o diagnóstico acessar outro destino, o
relatório não abre, enumera nem calcula hash dos arquivos do jogo. O botão
**Abrir chamado** copia o relatório e abre um formulário
público no GitHub, mas nunca faz upload ou publicação automática. O usuário deve
revisar e enviar o conteúdo manualmente.

## Reportar vulnerabilidade

Não publique detalhes exploráveis em uma issue. Use o recurso **Security >
Report a vulnerability** do repositório quando estiver habilitado ou entre em
contato privadamente com o mantenedor listado no perfil do projeto.
