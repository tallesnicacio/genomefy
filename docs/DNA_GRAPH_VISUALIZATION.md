# Visualização do grafo como DNA

## Visão

Representar a memória do Genomefy como DNA pode transformar uma estrutura técnica em algo imediatamente reconhecível: conhecimento organizado em loci, versões, relações e sinais regulatórios. A imagem seria marcante, mas precisa continuar honesta e útil.

A regra de produto é: **a visualização é uma projeção do grafo e da auditoria, nunca a fonte da verdade**. A ordem espacial da hélice é calculada para navegação e não deve ser confundida com uma sequência biológica real.

## Modelo visual

### Estrutura principal

- **Hélice dupla:** panorama da memória consultada ou de uma comunidade.
- **Espinha esquerda — conhecimento:** genes e seus resumos.
- **Espinha direita — evidência:** fonte, localização, versão e hash que sustentam cada gene.
- **Pares de bases:** ligação verificável entre um gene e sua evidência.
- **Trechos de hélice:** comunidades semânticas; cada trecho recebe cor, nome e padrão próprios.
- **Cromossomos:** agrupamentos maiores, como projetos, domínios ou coleções.

Esse mapeamento preserva uma distinção importante: o que o sistema acredita saber fica de um lado; o artefato que permite verificar fica do outro.

### Relações e regulação

| Elemento | Representação |
| --- | --- |
| Relação entre genes | arco externo entre loci, com seta quando a direção existe |
| Hiper-relação | anel envolvendo os loci participantes |
| Alelos | lâminas empilhadas no mesmo locus; a versão ativa fica em primeiro plano |
| Promotor | marcador triangular antes de um segmento ativado pela consulta |
| Repressor | trava ou barra transversal no candidato excluído |
| Marca de utilidade positiva | pequeno marcador acima do locus |
| Supressão explícita | marcador abaixo do locus, com motivo acessível |
| Contradição | ligação tracejada em zigue-zague entre os alelos conflitantes |
| Confiança | espessura da ligação mais rótulo textual |
| Trecho selecionado | brilho de alto contraste e inclusão na fita transcrita |

Cor nunca será o único canal. Forma, padrão, rótulo e espessura repetem as informações essenciais.

## A animação de transcrição

Ao executar uma consulta, o sistema pode mostrar o processo em quatro atos:

1. **Ativação:** promotores acendem os loci candidatos encontrados por busca exata, textual ou vetorial.
2. **Propagação:** relações relevantes iluminam caminhos curtos até evidências relacionadas.
3. **Regulação:** candidatos redundantes, obsoletos ou fora da tarefa recebem uma marca visível de exclusão.
4. **Transcrição:** os itens aprovados se destacam da hélice e formam uma fita linear de “RNA de contexto”, ordenada exatamente como será entregue à IA.

A fita final exibe o custo acumulado de tokens, as citações e o motivo de seleção de cada bloco. Alterar o orçamento atualiza a fita, permitindo enxergar o que se ganha ou perde com 400, 800 ou 1.200 tokens.

## Interação

- pesquisar um gene, fonte, comunidade ou identificador;
- fazer uma pergunta e acompanhar a ativação correspondente;
- aproximar, afastar, girar e selecionar trechos da hélice;
- clicar em um locus para abrir gene, alelos, fontes, relações e eventos;
- alternar entre visão “DNA”, grafo convencional e tabela;
- traçar o caminho entre dois genes;
- filtrar por tarefa, fonte, comunidade, versão, confiança ou estado;
- usar uma linha do tempo para reproduzir a memória até um evento específico;
- comparar dois transcritos e destacar diferenças de seleção e custo;
- copiar uma citação ou abrir a localização original quando permitido.

## Modo auditoria

O modo auditoria reduz os efeitos visuais e prioriza informação verificável. Ele deve apresentar:

- consulta, tarefa, orçamento e contador de tokens utilizado;
- estado e hash da memória no início da execução;
- ranking original e pontuação final dos candidatos;
- promotores, expansões, modificadores e repressões aplicados;
- motivo de inclusão ou exclusão de cada gene;
- fonte, localização, hash, versão e confiança da evidência;
- eventos de feedback que afetaram a seleção;
- verificação da cadeia de hashes;
- exportação do transcrito e da trilha em JSON.

Os níveis `EXTRAÍDO`, `INFERIDO` e `AMBÍGUO` aparecem por extenso, além dos ícones. Uma relação inferida jamais deve parecer tão definitiva quanto uma relação extraída diretamente da fonte.

## Ordenação da hélice

Grafos não possuem uma sequência natural única. Para não inventar uma falsa cronologia, a interface precisa declarar o método de ordenação em uso:

1. comunidade;
2. locus estável dentro da comunidade;
3. versão do alelo;
4. desempate por identificador determinístico.

Outros modos podem ordenar por relevância para a consulta, tempo ou caminho, mas devem ser nomeados na tela. A mudança de ordem é apenas uma projeção visual; identificadores e relações permanecem intactos.

## Acessibilidade

- modo 2D plano equivalente à hélice 3D;
- navegação completa por teclado;
- foco visível e ordem de tabulação previsível;
- painel em tabela com os mesmos dados do desenho;
- rótulos para leitores de tela e descrições textuais dos caminhos;
- contraste conforme WCAG 2.2 AA;
- padrões e formas além de cores;
- opção de movimento reduzido, sem rotação ou pulsação automática;
- tamanhos de fonte ajustáveis e interface utilizável em zoom de 200%;
- resumo textual automático da visualização atual.

## Desempenho e segurança visual

- aplicar níveis de detalhe: comunidades à distância, genes ao aproximar, evidências sob seleção;
- agregar grafos grandes antes de renderizar milhares de elementos;
- virtualizar painéis e carregar detalhes sob demanda;
- avisar antes de tentar uma visualização completa acima do limite seguro;
- nunca exibir conteúdo sensível ocultado durante a ingestão;
- sanitizar rótulos e metadados antes de inseri-los em HTML ou SVG.

## Fases recomendadas

### Fase 1 — DNA 2D navegável

Uma projeção SVG ou Canvas com comunidades, loci, alelos, evidências e relações. Inclui busca, seleção, painel lateral, filtros e visão tabular acessível. Usa um arquivo de grafo existente e não interfere no motor de recuperação.

**Critério de saída:** um usuário encontra a fonte de qualquer gene selecionado em até três interações e a representação permanece responsiva no corpus de teste.

### Fase 2 — Transcrição e auditoria

Conecta a visualização às consultas reais. Exibe ativação, exclusões, fita de contexto, orçamento de tokens, citações, replay de eventos e comparação de execuções.

**Critério de saída:** todos os itens do transcrito visual correspondem exatamente ao JSON auditável; nenhuma decisão é criada apenas no front-end.

### Fase 3 — Hélice 3D e exploração temporal

Adiciona WebGL, cromossomos, transições entre comunidades, linha do tempo rica e comparação visual de estados. O modo 2D continua disponível como alternativa funcional completa.

**Critério de saída:** a experiência 3D melhora uma tarefa observável de navegação ou compreensão em teste com usuários, sem reduzir acessibilidade ou precisão.

### Futuro — visão de ecossistema

Possíveis extensões incluem comparação de “genomas” entre projetos, recombinação visual de fontes, mapas de mutações entre versões e sobreposição de resultados de benchmark. Cada recurso deve nascer de uma pergunta real, não apenas do apelo estético.

## Métricas de validação

| Dimensão | Medida sugerida |
| --- | --- |
| Fidelidade | 100% dos elementos visuais rastreáveis ao JSON de origem |
| Auditoria | 100% das inclusões e exclusões visíveis sob demanda |
| Usabilidade | tempo e taxa de sucesso para localizar fonte, versão e contradição |
| Acessibilidade | fluxo principal completo por teclado e leitor de tela |
| Desempenho | tempo para primeira interação e quadros por segundo por faixa de tamanho |
| Compreensão | comparação controlada entre DNA, grafo convencional e tabela |

## Recomendação

Vale adotar a visualização em paralelo, desde que ela seja uma camada desacoplada sobre os formatos de grafo, transcrito e auditoria. Assim, o motor pode provar primeiro que reduz contexto com qualidade, enquanto a interface transforma esse comportamento em algo memorável e inspecionável.

O resultado desejado não é apenas “um grafo com formato de hélice”. É uma linguagem visual em que a pessoa vê a memória sendo ativada, regulada e transcrita — e consegue conferir cada decisão.
