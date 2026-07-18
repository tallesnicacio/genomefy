# Protocolo de mensuração do Genomefy

## Hipótese primária

Genomefy reduz o contexto em pelo menos 25% contra o baseline mais forte, mantendo cobertura de fatos-chave dentro de 2 pontos percentuais e acurácia de citações de pelo menos 95%.

## Gates oficiais

- economia de tokens de contexto: pelo menos 25% contra o baseline mais forte;
- qualidade: cobertura de fatos-chave não inferior por mais de 2 pontos percentuais;
- citações: pelo menos 95% das evidências selecionadas com citação válida;
- tamanho mínimo para `PASS`: 30 questões. Uma suíte menor que satisfaça os três gates é `INCONCLUSIVE`, não `PASS`.

## Métodos

- `full_context`: todos os genes ativos;
- `local_rag`: recuperação lexical local, sem grafo;
- `graph_baseline`: expansão determinística do grafo sem epigenética, repressão ou splicing; não é uma execução oficial do Graphify;
- `genomefy`: pipeline completo;
- ablações: sem epigenética, sem repressão, sem splicing e somente promotores.

São medidos recall, precisão, F1, MRR, nDCG, cobertura, citações e tokens. Usa-se `o200k_base` quando disponível; caso contrário o relatório identifica `regex-estimate-v1`. O comparador é o baseline com maior cobertura média, desempatado pelo menor contexto. Deltas pareados recebem bootstrap de 10.000 reamostragens.

- `PASS`: todos os gates e pelo menos 30 questões;
- `INCONCLUSIVE`: gates satisfeitos com amostra menor;
- `FAIL`: algum gate não atingido.

## Escala planejada

1. Smoke local versionado, sem alegação científica.
2. Avaliação controlada de recuperação com 60 questões em cinco categorias, sendo 12 repetidas três vezes para estabilidade: concluída em 2026-07-18 com resultado `FAIL`.
3. Suite de 300 questões: 150 de repositórios, 100 de contexto longo e 50 temporais próprias.

Datasets externos não são empacotados. Importá-los exige licença, versão, hash e checagem de vazamento. O benchmark não pode ler fora do escopo configurado.

### Gates adicionais do estágio 2

Antes da primeira execução, o estágio de 60 questões acrescenta duas proteções: nenhuma categoria pode regredir mais de 10 pontos percentuais contra o comparador selecionado e as 12 questões de estabilidade devem produzir seleção, contexto e contagem de tokens idênticos nas três repetições.

Este estágio mede recuperação de evidências. Ele não deve ser descrito como avaliação end-to-end da resposta textual de um modelo. Consulte [`benchmarks/stage2/README.md`](../benchmarks/stage2/README.md).

### Resultado congelado do estágio 2

A primeira execução oficial usou `o200k_base` e reduziu o contexto em 92,54%, com 100% de integridade referencial das citações e 100% de estabilidade determinística. O resultado permaneceu `FAIL` porque a cobertura de fatos-chave ficou 4,17 pontos percentuais abaixo do contexto completo e a categoria multifatorial regrediu 16,67 pontos percentuais. Os limites eram, respectivamente, 2 e 10 pontos percentuais.

O artefato completo e a análise das seis perguntas com perda de cobertura estão em [`benchmarks/results/STAGE2_REPORT.md`](../benchmarks/results/STAGE2_REPORT.md).

### Evolução pós-correção

O resultado congelado não foi sobrescrito. Após o diagnóstico, o commit `73f3677` introduziu recuperação por facets, normalização lexical, dominância temporal por locus, expansão multipath e seleção orientada à cobertura. Ele atingiu `PASS` com 98,33% de cobertura e 92,96% de economia. O commit `22b491b` passou a preservar toda evidência que corresponda ao núcleo de uma facet antes do corte de expressão e atingiu 100% de cobertura com 92,50% de economia.

Essas medições usam a mesma suíte já conhecida e, portanto, demonstram correção de engenharia e regressão, não confirmação independente. A próxima alegação independente exige uma nova suíte congelada antes da execução. Consulte [`benchmarks/results/STAGE2_POSTFIX_REPORT.md`](../benchmarks/results/STAGE2_POSTFIX_REPORT.md).
