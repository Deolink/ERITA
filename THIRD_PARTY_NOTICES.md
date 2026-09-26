# Componentes de terceiros

Os pacotes Windows e Linux incluem wheels originais, sem modificacao, obtidos
do PyPI e verificados por SHA-256 durante o build e durante a instalacao:

- CustomTkinter 5.2.2 — licença CC0-1.0;
- darkdetect 0.8.0 — licença BSD-3-Clause;
- packaging 26.3 — licenças Apache-2.0 ou BSD-2-Clause;
- PyCryptodome 3.23.0 — licenças BSD-2-Clause e domínio público.

Os textos de licença completos permanecem dentro dos respectivos wheels. As
origens e hashes aceitos estão em `patcher/requirements-win64.lock`,
`patcher/requirements-linux-x86_64.lock` e nos builders de release. O wheel do
PyCryptodome é específico de cada plataforma; os demais componentes mantêm as
mesmas versões travadas.

No Windows, o bootstrap opcional pode instalar o Python 3.13.15 x64 oficial,
distribuído pela Python Software Foundation sob a PSF License Agreement. O
instalador não é incluído no ZIP do ERPT-BR: ele é obtido pelo WinGet ou,
quando o WinGet está ausente, diretamente de `python.org` após validação de
tamanho, SHA-256, assinatura Authenticode e publicador.

O pacote Linux inclui o runtime portátil
`cpython-3.13.15+20260924-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`
do projeto Astral `python-build-standalone`. Ele contém CPython 3.13.15 e é
distribuído sob os termos aplicáveis do Python e dos componentes incorporados
ao runtime. O arquivo aceito possui 34.993.852 bytes e SHA-256
`d0b640eed27fbdd6f5f2bd33444aee53df2c8863f8b2a96f4094717411e3de9c`.

O runtime e os wheels Linux acompanham o `tar.gz` oficial do ERPT-BR. Nenhum
deles é baixado na primeira execução e nenhuma dependência é instalada no
sistema operacional.
