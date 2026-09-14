# Componentes de terceiros

O pacote Windows inclui wheels originais, sem modificacao, obtidos do PyPI e
verificados por SHA-256 durante o build e durante a instalacao:

- CustomTkinter 5.2.2 — licença CC0-1.0;
- darkdetect 0.8.0 — licença BSD-3-Clause;
- packaging 26.3 — licenças Apache-2.0 ou BSD-2-Clause;
- PyCryptodome 3.23.0 — licenças BSD-2-Clause e domínio público.

Os textos de licença completos permanecem dentro dos respectivos wheels. As
origens e hashes aceitos estão em `patcher/requirements-win64.lock` e
`tools/build_source_release.py`.

O bootstrap opcional pode instalar o Python 3.13.15 x64 oficial, distribuído
pela Python Software Foundation sob a PSF License Agreement. O instalador não é
incluído no ZIP do ERPT-BR: ele é obtido pelo WinGet ou, quando o WinGet está
ausente, diretamente de `python.org` após validação de tamanho, SHA-256,
assinatura Authenticode e publicador.
