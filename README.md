# PDF2MD

Conversor de PDFs didáticos para Markdown, com foco em separar o conteúdo em arquivos por tema e gerar documentos prontos para uso em Obsidian ou outros editores Markdown.

O projeto nasceu para converter materiais como `FILOSOFIA GERA - PROBLEMAS METAFÍSICOS - AULA 1.pdf` em notas separadas por `TEMA`, mantendo texto, imagens, links e relatório de integridade.

## Funcionalidades

- Converte PDF para Markdown usando `pdfplumber`.
- Separa o conteúdo em arquivos diferentes por marcador explícito `TEMA + número`.
- Evita confundir listas numeradas internas com novos temas.
- Corrige hifenização comum em quebras de linha de PDF.
- Recompõe quebras de linha artificiais para formar parágrafos mais legíveis.
- Remove rodapé repetido `CCDD – Centro de Criação e Desenvolvimento Dialógico`.
- Extrai imagens de conteúdo para a pasta `imagens/`.
- Insere links Markdown para as imagens no ponto aproximado em que aparecem no PDF.
- Ignora imagens de cabeçalho repetidas no topo das páginas.
- Cria embeds para links do YouTube usando `iframe`.
- Gera títulos principais em Markdown com maiúsculas e negrito.
- Gera nomes de arquivos em maiúsculas.
- Cria um relatório de integridade da conversão.
- Possui opção para limpar a saída antiga antes de converter novamente.

## Requisitos

- Python 3.10 ou superior.
- `pdfplumber`.
- `Pillow`.

Instale as dependências com:

```bash
python -m pip install pdfplumber pillow
```

Observação: algumas imagens especiais podem exigir suporte gráfico disponível no ambiente usado pelo `pdfplumber` ao renderizar recortes de página. Se houver falhas em imagens com codificação incomum, verifique a instalação de bibliotecas de renderização de PDF do sistema.

## Uso

Execute:

```bash
python pdf2md.py "arquivo.pdf"
```

Por padrão, a saída será criada em:

```text
saida_md/
```

Para escolher outra pasta de saída:

```bash
python pdf2md.py "arquivo.pdf" -o "minha_saida"
```

Para limpar arquivos Markdown e imagens antigas da pasta daquele PDF antes de gerar novamente:

```bash
python pdf2md.py "arquivo.pdf" --clean-output
```

Exemplo:

```bash
python pdf2md.py "FILOSOFIA GERA - PROBLEMAS METAFÍSICOS - AULA 2.pdf" --clean-output
```

## Estrutura De Saída

Para um PDF chamado:

```text
FILOSOFIA GERA - PROBLEMAS METAFÍSICOS - AULA 2.pdf
```

A saída fica semelhante a:

```text
saida_md/
└── FILOSOFIA GERA - PROBLEMAS METAFISICOS - AULA 2/
    ├── _RELATORIO DE INTEGRIDADE.md
    ├── FILOSOFIA GERA - PROBLEMAS METAFISICOS - AULA 2 - TEMA 1 - APLICACAO DAS QUATRO CAUSAS.md
    ├── FILOSOFIA GERA - PROBLEMAS METAFISICOS - AULA 2 - TEMA 2 - ATO POTENCIA E CATARSE.md
    ├── FILOSOFIA GERA - PROBLEMAS METAFISICOS - AULA 2 - TEMA 3 - TEORIA DOS CINCO ELEMENTOS.md
    └── imagens/
        ├── pagina-005-imagem-02.png
        └── pagina-018-imagem-02.png
```

## Regra De Separação Por Tema

A separação é feita somente quando uma linha contém explicitamente a palavra `TEMA` seguida de um número.

São reconhecidos exemplos como:

```text
TEMA 1
TEMA 1 – Origens e Aspectos Históricos
TEMA 2: Conceito de ser
TEMA 3 - Substância, essência e existência
```

Não são tratados como novos temas:

```text
1. De Platão e Aristóteles...
2. De Kant até Husserl...
SUBSTÂNCIA
ESCOLA JÔNICA
CAPÍTULO 2
UNIDADE 3
```

Isso evita que listas, subtítulos internos ou blocos numerados dentro de um tema sejam quebrados em arquivos separados.

## Formatação Markdown

Cada arquivo de tema começa com frontmatter padrão para Obsidian:

```yaml
---
Date: "2026-03-08"
tags:
  - filosofia
aliases:
List:
Tipo: Permanente
Categoria: Filosofia
Link:
---
```

Depois, o título principal é gerado em maiúsculas e negrito:

```markdown
# **FILOSOFIA GERA - PROBLEMAS METAFÍSICOS - AULA 1 - TEMA 2 - CONCEITO DE SER**
```

## Imagens

O script extrai imagens de conteúdo do PDF e salva em uma subpasta `imagens/`.

As imagens são referenciadas no Markdown assim:

```markdown
![Imagem da página 19](imagens/pagina-019-imagem-02.png)
```

O script tenta ignorar cabeçalhos visuais repetidos no topo das páginas. Para imagens com codificação especial, ele usa uma estratégia alternativa baseada em recorte da página.

## YouTube

Quando encontra links do YouTube, o script mantém o link original e adiciona um player incorporado logo abaixo.

Exemplo:

```markdown
https://www.youtube.com/watch?v=J5bgB2hXhtQ

<iframe width="560" height="315" src="https://www.youtube.com/embed/J5bgB2hXhtQ" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
```

Em ambientes que não renderizam HTML dentro do Markdown, o link original continua disponível.

## Relatório De Integridade

A cada conversão é criado o arquivo:

```text
_RELATORIO DE INTEGRIDADE.md
```

Ele registra:

- documento de origem;
- nome-base do PDF;
- aula identificada;
- quantidade de imagens extraídas;
- temas convertidos;
- verificações e transformações aplicadas.

## Limitações Conhecidas

- A extração depende da qualidade do texto embutido no PDF.
- PDFs escaneados como imagem podem exigir OCR antes da conversão.
- A posição dos links de imagem é aproximada, baseada na posição vertical da imagem na página.
- A detecção de cabeçalho repetido usa uma heurística simples: imagens no topo da página são ignoradas.
- O frontmatter ainda é fixo no código.
- O script é otimizado para PDFs estruturados com marcadores `TEMA N`.

## Desenvolvimento

Para verificar se o script está sintaticamente correto:

```bash
python -m py_compile pdf2md.py
```

Para converter uma aula de teste:

```bash
python pdf2md.py "FILOSOFIA GERA - PROBLEMAS METAFÍSICOS - AULA 1.pdf" --clean-output
```

## Licença

Este projeto está licenciado sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).
