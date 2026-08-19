# Assinatura de código do executável — decisão e caminho (G1)

Status: **pesquisa concluída, ação pendente do dono do projeto.** Este documento
não representa uma capacidade já implementada — hoje o `.exe` continua sem
assinar (`codesign_identity=None` em `BI_Flow_Mapper.spec`) e o aviso do
SmartScreen no README segue válido até que os passos abaixo sejam executados.

## Por que isso importa

`dist/BI Flow Mapper.exe` é gerado sem assinatura Authenticode. No Windows,
isso dispara o aviso do SmartScreen ("Windows protected your PC") na primeira
execução, porque o binário não tem reputação de editor conhecida. Um
certificado de assinatura de código tradicional (OV/EV, comprado de uma CA)
custa tipicamente algumas centenas de dólares por ano — inviável para um
projeto OSS sem receita.

## Caminho recomendado: SignPath Foundation

[SignPath Foundation](https://signpath.org/) (operada via [signpath.io](https://about.signpath.io/))
assina digitalmente projetos open-source **sem custo**. Como funciona:

- O certificado é de nível **OV (Organization Validation)**.
- A **chave privada nunca é exposta ao projeto** — fica custodiada em HSM da
  SignPath. O mantenedor nunca manipula a chave diretamente, o que é uma boa
  postura de segurança (elimina o risco de vazamento de chave em CI/CD).
- O certificado é emitido em nome da **SignPath Foundation**, não do projeto
  ou de uma pessoa física — ou seja, o "Publisher" que aparece no SmartScreen
  passa a ser a Foundation, atuando como garantidora, não o autor individual.
- A assinatura entra no fluxo via CI/CD: um build é submetido à API da
  SignPath, que assina o artefato e devolve o binário assinado.

### Por que o BI Flow Mapper parece elegível

Critérios de elegibilidade da SignPath Foundation (resumo — confirmar na
aplicação, critérios podem mudar):

- Licença OSI-approved única, sem dual-licensing comercial.
- Sem malware/PUP (potentially unwanted program) conhecido ou comportamento
  enganoso.
- Repositório público, histórico de commits real.

O BI Flow Mapper é MIT (`LICENSE`, Fase 1 do backlog), licença única, sem
variante comercial paga — não há sinal de desqualificação óbvio. Isso é uma
leitura da documentação pública da SignPath, não uma pré-aprovação: a decisão
final é deles, caso a caso.

### Passos manuais que o dono do projeto precisa tomar

Nenhum destes passos pode ser feito por um agente — exigem identidade e
decisão do responsável pelo repositório:

1. **Aplicar** em https://signpath.io/apply-for-free-signing (ou fluxo
   equivalente vigente no site da SignPath — o formulário pode mudar).
2. **Aguardar análise** — a documentação pública da SignPath fala em alguns
   dias a algumas semanas, dependendo do volume de pedidos.
3. Se aprovado, a SignPath fornece credenciais/projeto configurado no painel
   deles. Nesse ponto:
   - Adicionar um **step novo no workflow do GitHub Actions**
     (`.github/workflows/tests.yml` ou um workflow dedicado de release),
     condicionado a **tag de release** (não a todo push/PR — assinatura
     consome quota e não faz sentido em builds de desenvolvimento).
   - Esse step chama a action/CLI oficial da SignPath
     (`signpath/github-action-submit-signing-request` ou equivalente vigente)
     apontando para o artefato `dist/BI Flow Mapper.exe` gerado pelo
     PyInstaller.
   - O binário assinado retornado substitui o artefato publicado no GitHub
     Release.
4. Só depois desse fluxo estar validado ponta a ponta, remover
   `codesign_identity=None` do `.spec` deixa de fazer sentido como comentário
   — a assinatura real acontece *depois* do PyInstaller, como um
   pós-processamento do artefato, não como parte do `EXE()` do `.spec`.
   `codesign_identity` no PyInstaller é usado no fluxo macOS (`codesign`);
   no Windows a assinatura Authenticode é tipicamente aplicada com
   `signtool` (ou, aqui, a action da SignPath) como etapa separada depois do
   build, não dentro do `.spec`.

### Atualizar o README quando avançar

Este documento é referência técnica interna. Quando a aplicação for
submetida/aprovada e o step de CI estiver funcionando, o aviso do
SmartScreen no README (seção "Security Notice") precisa ser revisado — isso
é responsabilidade de quem cuida da mensagem ao usuário final, não deste
documento.

## Alternativas, caso a aplicação gratuita não avance

- **Azure Trusted Signing** — ~US$9,99/mês (tier "Basic", conferir preço
  vigente no portal da Azure). Certificado gerenciado pela Microsoft,
  integra com GitHub Actions via
  `azure/trusted-signing-action`. Sensivelmente mais barato que um
  certificado OV tradicional comprado de uma CA, mas ainda é um custo
  recorrente que precisa de decisão orçamentária do dono do projeto.
- **OSSign** — outra opção gratuita para OSS, mencionada como alternativa à
  SignPath. Menos estabelecida/documentada publicamente; avaliar apenas se a
  SignPath Foundation recusar ou o prazo de aprovação for proibitivo.
- **Sigstore/Cosign** — descartado para este problema. Resolve assinatura de
  artefato / supply-chain (proveniência, verificação por hash), não gera
  reputação de editor no SmartScreen do Windows, que é assinatura
  Authenticode. Os dois problemas são independentes; Sigstore poderia
  complementar no futuro (proveniência do release), mas não substitui a
  necessidade de um certificado Authenticode para o SmartScreen.

## Não fazer

- Não setar `codesign_identity` no `.spec` para um valor fictício ou
  placeholder — isso quebraria o build silenciosamente ou daria falsa
  impressão de que existe assinatura configurada.
- Não assinar localmente com um certificado self-signed "só para remover o
  aviso" — um certificado self-signed não tem cadeia de confiança reconhecida
  pelo Windows e não resolve o SmartScreen; na prática só troca um aviso por
  outro.
