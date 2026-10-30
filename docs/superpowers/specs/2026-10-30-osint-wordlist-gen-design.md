# Gerador de OSINT + Wordlist Inteligente — design v1

Status: aprovado em conversa.

## Motivação / escopo

Ferramenta de segurança ofensiva (uso autorizado / pentest / estudo), mistura
dos itens #16 (pipeline de OSINT) e #17 (gerador de wordlist inteligente) de
uma lista de ideias de portfólio. Fluxo: consulta um perfil do Instagram
(reaproveitando a lógica do projeto [toutatis](https://github.com/megadose/toutatis)
— GPLv3, código adaptado diretamente, não dependido como lib), monta um
relatório OSINT a partir dos dados públicos do perfil, e gera uma wordlist
("estilo hashcat") a partir dessas informações.

**v1 cobre apenas um perfil do Instagram por execução.** Outras fontes de
OSINT (enumeração de username cross-platform, certificate transparency —
itens originais da ideia #16) ficam para iterações futuras.

**Processo de entrega (decisão do usuário):** este projeto prioriza
velocidade de implementação. Não há suíte de testes automatizados — a
validação é por revisão de código (múltiplas passadas + uma revisão
adversarial final), não por TDD. Validação funcional contra a API real do
Instagram acontece depois, numa operação real do usuário, que dá o feedback.

## Objetivos

- Buscar os dados públicos de um perfil do Instagram (username/ID +
  sessionid do operador)
- Montar um relatório OSINT estruturado a partir desses dados
- Extrair palavras-semente (nome, username, bio, domínio do site, categoria
  de negócio) e combiná-las com seeds extras que o operador fornecer (anos,
  palavras-chave)
- Gerar uma wordlist expandida (`.txt`) com regras de mutação estilo
  hashcat (leet, caixa, separadores, sufixos, anos)
- Gerar um arquivo de regras hashcat (`.rule`) equivalente, aplicável sobre
  uma wordlist-base não expandida
- Separar, tanto para e-mails quanto para wordlists, o que veio do OSINT
  automático do que o operador adicionou manualmente

## Fora de escopo (v1)

- Outras fontes de OSINT além do Instagram (enumeração cross-platform,
  certificate transparency)
- Checagem de vazamento (tipo Have I Been Pwned) — a classificação de um
  e-mail como "vazado" é inteiramente manual, alimentada pelo operador, não
  uma consulta automática do sistema
- Quebra de hash/dictionary attack local — a wordlist gerada é entregue
  como artefato; a quebra em si acontece no sistema separado do operador,
  que não faz parte deste projeto e não é acessado por ele

## Arquitetura

Pipeline: **perfil OSINT → extração de seeds → motor de mutação → wordlist
(.txt) + regras hashcat (.rule) → relatório.**

### Componentes

1. **`osint/instagram_profile.py`** — adaptado de `core.py` do toutatis
   (atribuição mantida, GPLv3): `get_user_id`, `get_profile`,
   `advanced_lookup` (a consulta que retorna e-mail/telefone ofuscados).
   Normaliza a resposta da API num dataclass `Profile` (username,
   full_name, biography, external_url, is_business, business_category,
   follower_count, public_email, obfuscated_email, obfuscated_phone,
   profile_pic_url).

2. **`seeds.py`** — extrai palavras-semente de um `Profile`: partes do
   `full_name`, `username`, palavras da `biography` (tokenizado, filtrando
   stopwords e tokens curtos), domínio de `external_url` (sem
   esquema/`www`/TLD), `business_category`. Combina com seeds extras que o
   operador passar via CLI (`--extra-seed`, `--years`).

3. **`mutation/rules.py`** — motor de mutação: a partir das seeds + anos,
   gera a wordlist expandida e dedupicada:
   - leetspeak: `a→4, e→3, i→1, o→0, s→5`
   - variações de caixa: original, minúsculo, MAIÚSCULO, Capitalizado
   - separadores entre partes do nome: `.`, `_`, `-`, nenhum
   - sufixos comuns: `123`, `!`, `@`, `00`–`99`
   - ano como prefixo e sufixo (anos fornecidos via `--years`)

4. **`mutation/hashcat_rules.py`** — gera o `.rule` equivalente (sintaxe
   hashcat: `c`/`u`/`l` para caixa, `$N` para sufixo de caractere, `soX`
   para substituição leet) aplicável sobre uma wordlist-base **não
   expandida** (só as seeds cruas) — uso: `hashcat base.txt -r regras.rule`.

5. **`report.py`** — monta o relatório final:
   ```
   profile:  {...dados normalizados do Profile...}
   emails:   { osint: [...achados no perfil...], user_added: [...] }
   wordlist: { generated: {path, count}, user_added: {path, count} | null }
   rules:    { path }
   ```
   Saída console (texto) + JSON, mesmo padrão visual dos outros dois
   projetos da sessão (ssrf-scanner, xss-contextual-scanner).

6. **`cli.py`** — entrypoint único:
   ```
   janus -u username -s sessionid
            [--years 1998,2010] [--extra-seed "Empresa X"]
            [--user-email ja_vazado@exemplo.com]
            [--user-wordlist minha-lista.txt]
            -o report.json --wordlist-out wl.txt --rules-out regras.rule
   ```

## Fluxo de dados

1. `instagram_profile.get_profile(username_ou_id, sessionid)` → `Profile`
2. `seeds.extract(profile, extra_seeds=[...], years=[...])` → lista de
   seeds
3. `mutation.rules.generate_wordlist(seeds, years)` → lista dedupicada →
   grava `.txt`
4. `mutation.hashcat_rules.generate_rule_file()` → grava `.rule` (regras
   fixas, independentes dos dados — aplicáveis sobre a wordlist-base de
   seeds crus, que também é gravada)
5. Se `--user-wordlist` informado: carregado e contabilizado separadamente
   no relatório (`wordlist.user_added`), nunca misturado com
   `wordlist.generated` no mesmo arquivo
6. Se `--user-email` informado: adicionado a `emails.user_added`; se o
   perfil tiver `public_email`, ele entra em `emails.osint`
7. `report.build(...)` → `report.print_report(...)` + `report.save_json(...)`

## Tratamento de erro

- Sessionid inválido/expirado: a API do Instagram responde com erro —
  propagar como mensagem clara na CLI, não traceback cru
- Perfil não encontrado (404): mensagem clara, exit code não-zero
- Rate limit da API: detectar (mesmo padrão que o toutatis já trata) e
  avisar o operador para aguardar
- Perfil sem bio/URL externa/categoria de negócio: seeds extraídas desses
  campos simplesmente ficam vazias, não é erro

## Estratégia de revisão (em vez de testes automatizados)

Por decisão do usuário, não há suíte de testes nem TDD nesta v1 — a
prioridade é velocidade de entrega. A validação acontece por:

- Múltiplas passadas de revisão de código durante a implementação
- Uma revisão adversarial final (mesmo processo usado no motor de XSS:
  um revisor fresco lendo o código inteiro contra esta spec e o plano)
- Validação funcional fica para uso real do operador contra a API do
  Instagram, fora desta sessão — o feedback dessa operação real retroalimenta
  versões futuras

## Licenciamento

Este projeto é **GPLv3** (herdado da adaptação de código do toutatis,
GPLv3). Diferente do ssrf-scanner e do motor de XSS (MIT), aqui a licença
copyleft é obrigatória por incorporar lógica de um projeto GPLv3.

## Estrutura de repositório

Repo novo e independente (`janus`), com atribuição clara ao
toutatis (nome, autor, link, licença) no README e no cabeçalho do módulo
adaptado.

## Decisões registradas (histórico da conversa)

| Decisão | Opção escolhida |
|---|---|
| Fonte de OSINT v1 | Só Instagram (via lógica adaptada do toutatis) |
| Integração com toutatis | Código adaptado/incorporado (não dependência externa) |
| Licença | GPLv3 |
| Quebra de hash/vazamento | Fora de escopo — classificação de e-mail vazado é manual, HIBP não é consultado |
| Cracking local | Fora de escopo — fica no sistema separado do usuário |
| Motor de mutação | Wordlist `.txt` expandida **e** arquivo de regras `.rule` (hashcat) |
| Processo de entrega | Sem testes automatizados; revisão de código em várias passadas |

## Próximos passos / trabalho futuro (fora da v1)

- Outras fontes de OSINT (username cross-platform, certificate
  transparency) — completando o escopo original do item #16
- Possível checagem de vazamento (HIBP) como opção explícita, se o usuário
  decidir incluir
