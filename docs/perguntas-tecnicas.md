# Perguntas técnicas e de negócio

Respostas às questões da parte falada do desafio, ancoradas no que foi implementado.

## 1. Arquitetura em nuvem para produção

Detalhada em [architecture.md](architecture.md). Em resumo:

- **Cloud Run** para API e frontend: escala a zero e cobra por uso, adequado a um volume
  baixo e irregular de buscas.
- **Claude via Vertex AI**, dentro do projeto GCP e do perímetro VPC Service Controls.
- **Vertex AI Vector Search** com busca híbrida no lugar do Chroma.
- **Cloud SQL** para identidades, separado do índice.
- **Sensitive Data Protection (DLP)** na ingestão.
- **IAP** para login corporativo, **Secret Manager** para chaves e **BigQuery** para
  feedback e métricas.
- Infraestrutura como código em `infra/terraform`. Deploy por GitHub Actions com Workload
  Identity Federation, sem chave de serviço armazenada.

## 2. Como evitar que o LLM "alucine" habilidades

Quatro camadas, da mais forte para a mais fraca:

1. **Verificação determinística.** O modelo é obrigado a citar o trecho literal do CV para
   cada afirmação. O código confere com fuzzy matching (`rapidfuzz`, limiar 85). Citação não
   encontrada é marcada, sai do parecer final e reduz a nota do candidato em até 25%. A
   interface mostra as citações rejeitadas.
2. **O parecer só vê fatos confirmados.** A etapa de síntese recebe apenas as evidências
   verificadas, não o currículo inteiro.
3. **Saída estruturada.** `messages.parse` com schemas Pydantic. Não há texto livre para
   interpretar e cada campo tem uma instrução de preenchimento.
4. **Prompt orientado a lacunas.** O que não tem evidência vai para `gaps`, com instrução
   explícita de não preencher com o que é "típico do cargo".

Sobre medir: a taxa de evidências confirmadas é métrica de avaliação. Nas duas vagas de
teste, 100% das citações foram encontradas nos currículos.

## 3. Chunking e embeddings

- **Chunking por sentença, com offsets.** Os chunks nunca quebram frases e têm sobreposição
  de uma sentença, o que preserva enumerações como "M&A, reestruturação e captação". Os
  offsets permitem destacar a evidência no CV original.
- **Parent-document retrieval.** A busca é feita nos chunks e agregada por candidato (melhor
  trecho por consulta). Um CV longo não é penalizado por diluir o sinal.
- **Múltiplas consultas.** O LLM primeiro decompõe a vaga em mandato e consultas curtas
  escritas "como apareceriam num currículo". Isso resolve a assimetria vaga × CV: a vaga
  descreve um desafio, o CV descreve uma trajetória.
- **Busca híbrida com RRF.** Embeddings capturam intenção ("construir do zero" ≈ "escala
  times do zero"). BM25 protege termos exatos que embeddings borram (M&A, SAP, Series B).
  Reciprocal Rank Fusion combina os rankings sem calibrar escalas diferentes.
- **Embeddings locais `multilingual-e5-large`.** São multilíngues, bons em português e
  assimétricos (prefixos `query:` e `passage:`). Rodam em ONNX dentro do container, então
  os CVs não são enviados a terceiros só para vetorização.
- **Para CVs longos e reais:** chunking por seção (experiência, formação, resultados) com
  metadados de período. Assim a busca pode priorizar experiências recentes.

## 4. Como medir a "assertividade" de algo subjetivo

Três camadas, implementadas em `curator evaluate` e visíveis na página de avaliação:

| Camada | Métrica | Hoje |
|---|---|---|
| Ranking | hit@1, MRR contra o esperado pelos sócios | 100% / 1,00 |
| Fidelidade | % de evidências confirmadas no CV | 100% |
| Qualidade do parecer | LLM-as-judge com rubrica de sócio (tom, utilidade, fidelidade) | 4–5 / 5 |

Em produção, a métrica que importa é a **concordância com os sócios**:

- **Offline:** montar um golden set com mandatos passados e os shortlists que os sócios de
  fato apresentaram. Medir precision@3 e NDCG.
- **Online:** registrar o feedback "concordo / discordo" (já implementado) e acompanhar os
  resultados finais do funil: o candidato indicado chegou à entrevista com o cliente? Foi
  contratado?
- **Calibração:** mandatos com vários sócios permitem medir a concordância entre humanos
  (kappa). O modelo não precisa passar disso, precisa chegar perto.
- **O juiz é sinal de regressão, não verdade.** Ele tem viés, e usamos o mesmo modelo como
  juiz no protótipo. Em produção, usar um modelo diferente e calibrá-lo contra notas humanas.

## 5. Proteção e anonimização de PII

Implementado no protótipo:

- **Separação identidade × conteúdo.** Nomes e contatos ficam num repositório à parte. O
  índice vetorial e o LLM recebem só o texto profissional com pseudônimos (`CANDIDATO_01`).
  Nomes voltam apenas na camada de apresentação.
- **Redação de texto livre.** E-mail, telefone, CPF/CNPJ e URLs são removidos da vaga e dos
  comentários de feedback.
- **Logs sem PII.** Um processador do structlog aplica a mesma redação em todo log. A
  telemetria do Chroma está desligada.
- **Testado.** `test_llm_never_sees_pii` captura todos os prompts e confirma que nenhum
  nome, e-mail ou telefone chegou ao modelo.
- **Menor exposição.** A API não devolve contatos. A chave da API fica no servidor do
  Next.js, nunca no navegador.
- **Prompt injection.** O conteúdo do CV entra em tags XML marcadas como dado, não como
  instrução.

Em produção:

- DLP com NER para nomes no corpo do CV e tokenização reversível com chave no KMS.
- CMEK nos armazenamentos, VPC-SC, IAP e Audit Logs.
- Política de retenção alinhada à LGPD, com base legal e direito de exclusão: apagar do
  Cloud SQL invalida o pseudônimo.

Um ponto a discutir: **quase-identificadores**. "Ex-CFO de fintech unicórnio, Poli-USP e
MBA em Stanford" pode identificar alguém mesmo sem o nome. Removê-los destruiria o sinal de
match. Por isso a proteção vem do perímetro, dos termos do Vertex (dados não treinam
modelos) e do controle de acesso, não só da anonimização.

### Viés

A pseudonimização também é o principal controle de viés: se o modelo não vê o nome, a nota
não pode depender dele. Isso não é pressuposto, é testado: `curator bias-audit` troca nome e
contato por outros de gênero oposto e compara o prompt resultante, byte a byte. Ele revelou
um limite real: em português a concordância entrega o gênero ("acostumada"). A correção foi
neutralizar essas formas no texto que o modelo lê, e o mesmo teste passou a cobri-las.

Os limites continuam existindo. A lista de marcas é heurística, e outros sinais indiretos
(instituições, trajetória) podem correlacionar com gênero ou origem. Para isso existe o teste
contrafactual empírico e, em produção, o acompanhamento da taxa de indicação por grupo
demográfico, com dados declarados voluntariamente e nunca enviados ao modelo.

## 6. Como vender para um sócio 100% manual e intuitivo

- **Posicionar como analista, não como substituto.** O agente faz o trabalho de primeira
  leitura (varrer a base, montar um shortlist fundamentado) e o sócio decide. A interface
  reforça isso: recomendação com ressalvas, pontos para entrevista e próximos passos.
- **Confiança por transparência.** Cada afirmação aponta o trecho do CV. O sócio confere em
  segundos, em vez de confiar numa nota opaca.
- **Começar lado a lado.** Em 2 ou 3 mandatos reais, o sócio faz o shortlist como sempre e
  compara com o do agente. As divergências viram conversa, e às vezes revelam um nome que
  ele não tinha lembrado.
- **Falar do ganho que importa para ele:** tempo de resposta ao cliente e cobertura da base.
  A intuição do sócio é forte nos nomes que ele conhece; o agente cobre os que ele não
  lembra.
- **Capturar o julgamento dele.** O feedback "concordo / discordo" transforma a intuição do
  sócio em dado para calibrar o sistema. O modelo passa a refletir o critério da casa.
