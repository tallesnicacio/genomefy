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
2. Subconjunto gratuito de 60 questões, com 12 repetidas três vezes.
3. Suite de 300 questões: 150 de repositórios, 100 de contexto longo e 50 temporais próprias.

Datasets externos não são empacotados. Importá-los exige licença, versão, hash e checagem de vazamento. O benchmark não pode ler fora do escopo configurado.
