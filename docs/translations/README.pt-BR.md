<p align="center">
  <img src="../logo.svg" width="420" alt="Genomefy — memória contextual auditável para IA">
</p>

<p align="center">
  <strong>Entregue menos contexto à IA — e guarde os recibos de cada escolha.</strong>
</p>

<p align="center">
  <a href="../../README.md">English</a> · <a href="README.pt-BR.md">Português (Brasil)</a>
</p>

Genomefy é uma camada local de memória contextual para assistentes de IA. Ela transforma o conhecimento de um projeto em unidades pequenas e versionadas, recupera somente as evidências necessárias para uma pergunta e registra por que cada unidade entrou ou ficou fora do contexto.

- **Local e sem API paga.** O núcleo usa Python, SQLite e FTS5. A recuperação não chama um LLM.
- **Toda unidade selecionada leva evidência.** Caminho, versão, hash SHA-256, confiança e motivos acompanham o contexto.
- **Toda consulta é reproduzível.** Execuções, feedback explícito e mudanças vivem em uma trilha append-only encadeada por hashes.

Genomefy usa termos da biologia — genes, loci, promotores, repressores, splicing e marcas epigenéticas — como modelo de interface. A implementação é software convencional executado em hardware binário comum.

<p align="center">
  <img src="../genomefy-hero.svg" width="920" alt="Genomefy transforma a memória do projeto em um contexto pequeno e citado">
</p>

## Comece em minutos

```bash
git clone https://github.com/tallesnicacio/genomefy.git
cd genomefy
python -m pip install -e .
```

Crie uma memória local no projeto e ingira Markdown ou texto:

```bash
genomefy --root /caminho/do/projeto init
genomefy --root /caminho/do/projeto ingest docs docs
genomefy --root /caminho/do/projeto query "Por que adotamos refresh tokens rotativos?" --budget 900
```

O resultado é um transcrito limitado por orçamento:

```text
[GENE gene:auth-decision] Decisão de autenticação
O sistema usa tokens de sessão curtos e rotaciona refresh tokens...
[CITATION architecture.md:12 | src:...:v2 | confidence=1.00]

[AUDIT run=run:1781... tokens=107/180 counter=regex-estimate-v1]
```

Inspecione a decisão completa:

```bash
genomefy --root /caminho/do/projeto audit run:1781...
genomefy --root /caminho/do/projeto audit verify
```

## O que ele promete

Genomefy foi desenhado para testar uma hipótese concreta:

> Uma memória estruturada e regulada pode enviar significativamente menos contexto à IA sem reduzir materialmente a cobertura da resposta, preservando citações e decisões auditáveis.

Os gates iniciais são definidos antes da avaliação:

| Métrica | Resultado exigido |
|---|---:|
| Redução de tokens de contexto | **≥ 25%** contra o baseline mais forte |
| Cobertura de fatos-chave | queda máxima de **2 pontos percentuais** |
| Correção das citações | **≥ 95%** |
| Amostra mínima para `PASS` | **30 questões** |

Uma suíte menor pode ser `INCONCLUSIVE` ou `FAIL`, nunca `PASS`.

## Evidência atual — honestidade faz parte do produto

O smoke test versionado informa:

| Questões | Comparador | Redução de contexto | Delta de qualidade | Citações válidas | Resultado |
|---:|---|---:|---:|---:|---|
| 8 | baseline local de grafo | **37,28%** | **0,00 pp** | **100%** | `INCONCLUSIVE` |

Os três gates numéricos foram atingidos, mas oito questões não comprovam vantagem geral. Por isso o resultado permanece `INCONCLUSIVE`. As próximas etapas são um subconjunto gratuito com 60 questões e uma suíte licenciada e rastreável com 300 questões.

Veja o [protocolo de benchmark](../BENCHMARK.md) e a [configuração legível por máquina](../../benchmarks/protocol.json).

## Como funciona

```text
documentos / JSONL / grafo Graphify opcional
                       │
                       ▼
        genes + loci + versões + relações
                       │
                pergunta + tarefa
                       │
                       ▼
 promotores exatos/FTS → expansão do grafo (≤2 saltos)
                       │
                       ▼
 tarefa + repressores + marcas limitadas de feedback
                       │
                       ▼
 splicing por orçamento → transcrito citado de contexto
                       │
                       ▼
          execução + evento encadeado por hash
```

| Metáfora biológica | Implementação concreta |
|---|---|
| Gene | Unidade pequena e endereçável de conhecimento |
| Locus | Identidade estável compartilhada por versões do mesmo assunto |
| Alelo | Versão da fonte; versões antigas continuam rastreáveis |
| Promotor | Busca exata e FTS5 combinadas com RRF |
| Repressor | Termos negativos, supressão explícita e filtros limitados |
| Splicing | Seleção determinística sob orçamento de tokens |
| Marca epigenética | Modificador limitado a ±10%, somente após feedback explícito |
| Transcrito | Contexto final citado entregue à IA |

## O que você recebe

| Capacidade | Entrega |
|---|---|
| **Memória versionada** | Fontes alteradas geram novas versões sem apagar o histórico |
| **Recuperação limitada** | Promotores exatos/FTS, RRF e expansão de no máximo dois saltos |
| **Compilador de contexto** | Seleção por relevância, novidade e orçamento, com motivos de inclusão e exclusão |
| **Aprendizado explícito** | Somente feedback aceito/rejeitado altera utilidade; silêncio não altera nada |
| **Integridade auditável** | SHA-256 de genes e transcritos mais cadeia append-only de eventos |
| **Entradas diferentes** | Markdown/texto, JSONL canônico e `graph.json` opcional do Graphify |
| **Interfaces diferentes** | Biblioteca Python, CLI, MCP local opcional e skill para Codex |
| **Mensuração** | Baselines, ablações e bootstrap pareado com 10.000 reamostragens |

## Graphify + Genomefy

[Graphify](https://github.com/Graphify-Labs/graphify) mapeia como o conhecimento está conectado. Genomefy decide qual parte deve virar contexto **agora**, respeitando orçamento, versões e histórico de feedback.

```bash
genomefy --root /caminho/do/projeto ingest graphify graphify-out/graph.json
```

O adaptador é opcional. Genomefy funciona sem Graphify instalado e o `graph_baseline` local não é apresentado como benchmark oficial do Graphify.

## Skill do Codex

```bash
genomefy skill install --global
```

Em uma nova sessão do Codex, invoque `$genomefy`. O fluxo padrão recupera contexto, responde com localizações de fonte e acrescenta um resumo de auditoria. Feedback nunca é inferido pelo silêncio.

## DNA Graph

A camada visual planejada representa a memória como hélice dupla: conhecimento em uma fita, evidência na outra e loci selecionados formando um “RNA de contexto”. A visão auditável 2D vem primeiro; 3D só será adotado se melhorar uma tarefa mensurável.

Leia a [especificação do DNA Graph](../DNA_GRAPH_VISUALIZATION.md).

## O que ele não promete

- Não torna o modelo mais inteligente por si só.
- Não torna verdadeiras as fontes ingeridas.
- Não oferece computação física infinita ou baseada em DNA.
- Não chama um smoke test pequeno de prova científica.
- Não esconde evidências inferidas, históricas ou excluídas atrás da metáfora visual.

## Estado atual

Genomefy `0.2.0` é uma versão experimental, mas funcional. Armazenamento, recuperação por facets, seleção temporal de alelos, replay, auditoria, benchmark e instalação da skill estão implementados e testados. A execução controlada original de 60 perguntas permanece `FAIL`; a regressão pós-correção na suíte conhecida é `PASS` com 100% de cobertura. Confirmação independente, embeddings locais, avaliação end-to-end, a suíte licenciada de 300 perguntas e a interface DNA Graph ainda são trabalhos futuros.

## Desenvolvimento e licença

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Consulte [CONTRIBUTING.md](../../CONTRIBUTING.md) e [SECURITY.md](../../SECURITY.md). Licença Apache-2.0.
