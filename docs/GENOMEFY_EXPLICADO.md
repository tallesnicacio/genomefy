# Genomefy — memória de longo prazo que a IA consegue explicar

## A ideia em uma frase

Genomefy é um sistema local de memória para IA que transforma fontes dispersas em unidades versionadas de conhecimento e, a cada pergunta, “transcreve” apenas o contexto mais útil dentro de um orçamento de tokens — com fontes, decisões e alterações auditáveis.

Ele não tenta substituir o modelo de IA nem transformar computadores em organismos. Seu papel é preparar uma memória externa melhor: persistente, seletiva, verificável e econômica.

## O problema

Uma IA pode receber muito contexto, mas isso não significa que encontrará o que realmente importa. Enviar todo o histórico a cada consulta custa tokens, aumenta a latência e mistura informação relevante com ruído. A alternativa comum, a busca por similaridade, ajuda, porém pode perder relações, versões, contradições e o motivo pelo qual determinado trecho entrou na resposta.

O Genomefy parte de outra pergunta:

> E se a memória da IA funcionasse menos como uma pilha de documentos e mais como um sistema capaz de armazenar, regular e transcrever conhecimento sob demanda?

## A inspiração biológica — e seus limites

O vocabulário do DNA é uma metáfora de projeto. Ele ajuda a organizar responsabilidades técnicas, mas não é uma alegação de computação molecular.

| Conceito inspirado na biologia | Implementação real no Genomefy |
| --- | --- |
| Genoma | Base local que reúne unidades de conhecimento, relações, fontes e histórico |
| Gene | Unidade pequena e identificável de conhecimento |
| Locus | Identidade estável de um assunto ou fato ao longo do tempo |
| Alelo | Versão de um gene; versões antigas permanecem rastreáveis |
| Promotor | Mecanismo de recuperação que ativa candidatos relevantes para a pergunta |
| Repressor | Regra que evita contexto inadequado, redundante, obsoleto ou fora da tarefa |
| Splicing | Seleção e montagem das melhores evidências dentro do limite de tokens |
| Marca epigenética | Ajuste limitado de utilidade baseado em feedback explícito e auditado |
| Transcrito | Pacote final de contexto entregue à IA, acompanhado de citações e justificativas |

Na implementação inicial, tudo continua sendo software convencional executado em hardware binário. Não há DNA físico, quatro estados lógicos nativos ou promessa de ganho decorrente de biologia molecular. O possível avanço vem do desenho da memória e da seleção de contexto.

## Como funciona

O fluxo é simples de observar, embora cada etapa possa evoluir de forma independente:

```text
Documentos / JSONL / grafo existente
                │
                ▼
      genes + loci + alelos
                │
                ▼
 relações + fontes + evidências
                │
        pergunta e tarefa
                │
                ▼
 promotores → expansão do grafo → repressão
                │
                ▼
  splicing com orçamento de tokens
                │
                ▼
 contexto citado + transcrito + auditoria
```

1. **Ingestão:** o Genomefy lê documentos, registros JSONL ou um grafo compatível e cria genes ligados às suas fontes.
2. **Versionamento:** uma nova evidência não apaga silenciosamente a anterior; ela pode gerar um novo alelo no mesmo locus.
3. **Ativação:** busca exata, busca textual e, quando disponível, busca vetorial atuam como promotores. Seus resultados são combinados de forma determinística.
4. **Relações:** candidatos podem ativar vizinhos relevantes no grafo, respeitando direção, confiança e limite de profundidade.
5. **Regulação:** tarefa, filtros, versões e feedback explícito modificam a prioridade dentro de limites conhecidos.
6. **Transcrição:** um seletor monta o menor conjunto de evidências que oferece boa cobertura sem ultrapassar o orçamento.
7. **Auditoria:** o sistema registra o que entrou, o que ficou de fora, por quê, quanto contexto foi usado e de onde cada afirmação veio.

## Genomefy e Graphify

Os dois conceitos são complementares:

- O Graphify transforma um corpus em um mapa navegável de entidades, comunidades e relações.
- O Genomefy usa esse mapa — ou constrói sua própria memória a partir de documentos — para decidir o que deve ser ativado e transcrito em cada consulta.

Em uma frase: **Graphify mostra como o conhecimento está conectado; Genomefy seleciona qual parte desse conhecimento deve virar contexto agora.**

O adaptador de Graphify é opcional. O núcleo do Genomefy permanece independente, e preserva identificadores, comunidades, direção, origem e nível de confiança sempre que esses dados estiverem presentes.

## Um exemplo concreto

Imagine um projeto que possua três versões de uma decisão arquitetural, uma especificação atual e uma nota antiga que contradiz a especificação.

Ao perguntar “qual é o mecanismo atual de autenticação e por que foi escolhido?”, o Genomefy pode:

1. localizar o locus “autenticação”;
2. priorizar o alelo vigente sem apagar os anteriores;
3. percorrer relações até a decisão arquitetural e sua justificativa;
4. sinalizar a contradição histórica;
5. excluir trechos redundantes ou sem fonte;
6. montar um contexto de até 1.200 tokens;
7. retornar citações como `documento + seção + hash da versão`;
8. registrar uma explicação reproduzível da seleção.

Um resumo de auditoria pode ter este formato:

```text
Consulta: mecanismo atual de autenticação
Orçamento: 1.200 tokens
Selecionados: 6 genes / 842 tokens
Excluídos: 11 redundantes, 3 obsoletos, 2 fora da tarefa
Evidências citáveis: 6 de 6
Estado da memória: hash 9b7…
Evento final: 184, cadeia íntegra
```

Se alguém fornecer feedback de que uma evidência foi útil, o Genomefy não altera o passado. Ele acrescenta um evento à cadeia de auditoria e recalcula uma marca de utilidade limitada. Assim, é possível reproduzir o estado anterior e verificar quando e por que o comportamento mudou.

## O que torna a proposta diferente

O valor não está apenas em recuperar trechos. Está na combinação de cinco propriedades:

- **memória versionada:** fatos corrigidos não destroem o histórico;
- **relações explícitas:** a busca pode seguir conexões, não apenas semelhança textual;
- **contexto regulado:** tarefa, confiança, redundância e feedback participam da seleção;
- **orçamento como requisito:** o transcrito nasce com um limite mensurável de tokens;
- **auditoria de ponta a ponta:** fontes, decisões, eventos e integridade podem ser inspecionados.

## A promessa é mensurável

Genomefy deve ser julgado por resultados, não pela força da metáfora. O objetivo inicial é superar o melhor baseline disponível sob critérios previamente definidos:

| Métrica principal | Critério de sucesso |
| --- | --- |
| Tokens de contexto | redução de pelo menos 25% contra o baseline mais forte |
| Qualidade da resposta | queda máxima de 2 pontos percentuais |
| Correção das citações | pelo menos 95% |
| Integridade do histórico | 100% dos eventos válidos na verificação da cadeia |
| Reprodutibilidade | mesma entrada e mesmo estado produzem a mesma seleção |

Os comparativos incluem contexto completo, recuperação local convencional, recuperação por grafo e Genomefy. Também são executadas ablações — por exemplo, sem marcas epigenéticas ou sem splicing — para descobrir qual componente realmente produz ganho.

O relatório deve dizer **PASS**, **INCONCLUSIVO** ou **FAIL**. “Inconclusivo” é obrigatório quando a amostra não permite afirmar vantagem com segurança. Um protótipo funcional demonstra viabilidade de engenharia; somente o benchmark controlado demonstra avanço real.

## O que o Genomefy não promete

- não aumenta, por si só, a inteligência do modelo;
- não garante que toda fonte ingerida seja verdadeira;
- não transforma quatro letras em capacidade computacional infinita;
- não substitui avaliação humana em decisões críticas;
- não trata uma visualização bonita como evidência de eficiência.

Ele promete algo mais específico e testável: oferecer à IA uma memória local de longo prazo que selecione menos contexto, preserve mais história e explique melhor cada escolha.

## Texto curto para compartilhar

> **Genomefy é uma camada de memória auditável para IA inspirada na forma como o DNA organiza, regula e transcreve informação.** Ele converte documentos e grafos em unidades versionadas de conhecimento, ativa somente o que importa para cada pergunta e monta um contexto citado dentro de um orçamento de tokens. A biologia é a metáfora; a implementação é software local, determinístico e mensurável. A meta inicial é reduzir pelo menos 25% do contexto sem perder mais de 2 pontos percentuais de qualidade, mantendo no mínimo 95% de correção nas citações.
