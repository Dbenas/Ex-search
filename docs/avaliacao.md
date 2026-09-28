# Avaliação nas vagas de teste

Gerada por `uv run curator evaluate` com `claude-opus-5` (effort `medium`). O relatório
completo, com todos os pareceres, está em `backend/reports/evaluation-claude-opus-5.json` e
na página **Avaliação do modelo** da interface.

## Resumo

| Métrica | Resultado |
|---|---|
| Candidato esperado em 1º (hit@1) | 2/2 |
| MRR | 1,00 |
| Evidências citadas encontradas no CV | 100% |
| Juiz: tom executivo | 4,5 / 5 |
| Juiz: utilidade para a decisão | 3,5 / 5 |
| Juiz: fidelidade aos currículos | 4,0 / 5 |
| Tempo por análise (4 candidatos, 6 chamadas) | 53 s |
| Tokens por análise (entrada / saída) | 17,3 mil / 6,8 mil |
| Custo por análise, preço de tabela | US$ 0,26 |

Com dois casos, as notas do juiz variam cerca de 0,5 ponto entre execuções. O 1º lugar e a
taxa de evidências ficaram estáveis em todas as rodadas; as posições de baixo, com notas
próximas entre si, às vezes trocam.

## Vaga 1 · CTO

| # | Candidato | Nota | Hard | Soft | Contexto | Recomendação |
|---|---|---|---|---|---|---|
| 1 | Carolina Mendes | 80 | 8 | 9 | 7 | avançar com ressalvas |
| 2 | Bruno Costa | 31 | 4 | 3 | 2 | não priorizar |
| 3 | Ana Silva | 25 | 1 | 4 | 3 | não priorizar |
| – | Diego Souza | 10 | | | | também avaliado |

Trecho do parecer:

> O shortlist é assimétrico: apenas Carolina Mendes responde ao núcleo do mandato — CTO de
> startup, IA e dados, hands-on, times formados do zero. Bruno Costa traz senioridade
> corporativa de TI, mas orientação a governança e estabilidade oposta ao contexto. […] A
> decisão real não é comparativa: é arbitrar se as lacunas de Carolina Mendes (arquitetura do
> zero, MLOps, cloud, B2B/SaaS) são sanáveis em entrevista ou exigem ampliação da busca.

**Leitura.** O modelo separou senioridade de aderência. Bruno tem o currículo mais "pesado"
(20 anos, CIO, cloud, 500 pessoas), mas o estilo declarado derruba soft skills e contexto. A
Carolina recebe "avançar com ressalvas", não "avançar": o CV diz que ela escala *times* do
zero, não *arquitetura*, e o parecer registra essa distinção.

## Vaga 2 · CFO

| # | Candidato | Nota | Hard | Soft | Contexto | Recomendação |
|---|---|---|---|---|---|---|
| 1 | Ana Silva | 71 | 8 | 5 | 8 | avançar com ressalvas |
| 2 | Diego Souza | 27 | 3 | 3 | 2 | não priorizar |
| 3 | Carolina Mendes | 25 | 1 | 4 | 3 | não priorizar |
| – | Bruno Costa | 16 | | | | também avaliado |

> A decisão real do sócio não é comparativa, e sim de suficiência: avançar com um shortlist
> de um nome, validando as lacunas de governança de board, construção de time e maturidade
> contábil de Ana Silva, ou reabrir a busca em paralelo.

**Leitura.** Esta vaga tem uma armadilha: o título fala em "Reestruturação", o que favorece
lexicalmente o Diego (CFO, compliance, auditoria). O modelo leu o conteúdo: captação
institucional, M&A e VC. O Diego, mesmo sendo CFO, fica 44 pontos atrás da Ana, com
contexto 2/10: governança de indústria pesada não é o desafio de uma scale-up pré-M&A. Em
rodadas anteriores ele chegou a ficar atrás da Carolina, que nem é de finanças; entre
perfis igualmente desalinhados, a ordem varia.

## Recuperação (antes do LLM)

`uv run curator retrieval-eval` indexa, em memória, os 4 currículos junto com 16
distratores fictícios parecidos com eles e roda 10 consultas: as duas vagas do desafio,
paráfrases que evitam o vocabulário dos CVs e consultas com armadilhas de palavras-chave.
Mede se o candidato esperado aparece no topo da busca, sem nenhuma chamada ao modelo.

| Método | Acerto do 1º | Recall@3 | MRR |
|---|---|---|---|
| Só vetorial (padrão) | 0,80 | 1,00 | 0,90 |
| Só BM25 | 0,60 | 0,70 | 0,63 |
| Híbrido, RRF k=60 | 0,60 | 0,70 | 0,69 |

O caso que decide: na paráfrase da vaga de controladoria industrial, a busca vetorial põe o
Diego em 1º; o BM25 não o encontra e casa palavras incidentais em outros perfis, e a fusão o
derruba para 13º. Testei peso do BM25 de 0,2 a 1,0, constante do RRF de 5 a 60 e corte do
BM25 nos 3 ou 5 primeiros: o melhor híbrido chegou a MRR 0,78. A busca semântica virou o
padrão (`LEXICAL_WEIGHT=0`).

Com 10 consultas, isso é um teste de regressão, e roda no CI com limite mínimo. A conclusão
vale para currículos curtos e vagas parafraseadas; numa base real, com nomes de sistemas e
certificações, o BM25 merece nova avaliação.

## Comparação entre modelos

O pipeline aceita Claude ou Gemini (`LLM_PROVIDER=gemini`) com os mesmos prompts, busca e
verificação, e `curator evaluate --provider gemini` gera um relatório comparável, sempre com
o mesmo juiz. A página de avaliação exibe os modelos lado a lado.

O benchmark com Gemini ainda não foi executado. O plano gratuito da API não inclui os
modelos Pro e limita o Flash a 5 requisições por minuto, com erros frequentes de sobrecarga
(503). Uma análise faz 6 chamadas. Além disso, no plano gratuito o Google pode usar o
conteúdo enviado para melhorar seus produtos, o que não seria aceitável com dados reais. A
comparação justa (Claude Opus 5 × Gemini 3.1 Pro) requer um projeto com faturamento ou o
Vertex AI.

## O que o juiz criticou e o que mudou

O juiz (mesmo modelo, rubrica de sócio sênior revisando o parecer antes do cliente) orientou
três iterações de prompt:

| Crítica | Ajuste |
|---|---|
| Parecer sem próximos passos acionáveis | Novo campo `next_steps`: o que verificar, com quem e o que muda a recomendação |
| Listas de lacunas longas (até 13 itens) | Máximo de 5 lacunas, apenas requisitos essenciais, por ordem de criticidade |
| "Executivo de tecnologia" referindo-se à Carolina | Instrução para evitar termos flexionados em gênero, já que o modelo vê só o pseudônimo |
| Premissas sobre a empresa que a vaga não sustenta ("restrição de capital") | Requisitos implícitos passam a ser sempre desejáveis; proibido presumir orçamento ou porte |
| "Sem relacionamento com fundos" para quem captou Series B/C | Distinção explícita entre ausência de evidência e evidência pouco detalhada |

Crítica que continua aberta: o juiz ainda aponta casos em que algo que merece *validação*
("especialista em M&A" sem detalhe de due diligence) aparece como *lacuna*. É um julgamento
fino, e o lugar certo para calibrá-lo é o feedback dos sócios, não mais iterações de prompt
contra dois exemplos.

## Limites desta avaliação

- Dois casos não têm poder estatístico. Esta avaliação funciona como teste de regressão
  (ranking correto, nenhuma citação inventada), não como medida de qualidade.
- O juiz é o mesmo modelo que gera o parecer, o que tende a inflar notas. Em produção: outro
  modelo como juiz, calibrado contra notas de sócios.
- A busca não é estressada: com 4 perfis, todos chegam à etapa de avaliação.
