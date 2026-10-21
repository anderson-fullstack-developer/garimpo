# Relatório de consumo — Garimpo API (Railway)

Análise feita a 21/10/2026 sobre o código desta API (commit `a6c62ec`), com uma medição real de uma página da Vinted.
**Nenhum código foi alterado.**

---

## 1. Resposta curta

**Sim, é possível reduzir o consumo, e bastante.** A API não gasta por causa de uma falha grave. Gasta porque está a fazer muito trabalho repetido:

- descarrega e lê uma **página de 3,6 MB** da Vinted para cada país, para cada página de resultados e para cada ciclo;
- faz isto **de 10 em 10 ou de 15 em 15 segundos**;
- faz **uma busca extra a cada 20 segundos**, só para acertar o "relógio" dos anúncios;
- a busca manual ("Buscar") pode ficar **6 horas seguidas** a repetir buscas de 5 em 5 segundos, em paralelo com o monitor automático.

Só com mudanças de configuração e de código pequenas e seguras, a estimativa é cortar **cerca de 50% a 80% do trabalho de buscas** e **30% a 50% da memória**. Os números exatos dependem de quantos utilizadores e alertas estão ativos (ver secção 6).

> ⚠️ **Limite desta análise:** não tenho acesso à sua conta do Railway. Os custos em € são **estimativas** feitas a partir do código e de uma medição. Para confirmar, veja no Railway o separador **Metrics** do serviço (CPU, Memory, Network) e o **Usage** da conta.

---

## 2. Onde o Railway cobra

O Railway cobra pelo que o serviço usa, minuto a minuto:

| Recurso | Preço de referência | O que pesa no Garimpo |
|---|---|---|
| **Memória (RAM)** | ~10 $ por GB por mês | Python sempre ligado, páginas grandes em memória, várias threads |
| **CPU** | ~20 $ por vCPU por mês | Ler as páginas HTML da Vinted |
| **Rede (saída)** | Por GB | Pouco: respostas ao site e envios para o Telegram |

**A base de dados não está no Railway.** Está no Neon, que tem a sua própria conta. Por isso o trabalho na base de dados não pesa no Railway, mas pesa no Neon (ver secção 5.6).

---

## 3. O que foi medido

Descarreguei uma página real de pesquisa da Vinted (`vinted.pt`, "iphone") e corri o código de leitura do Garimpo (`parse_catalog_html`) sobre ela:

| Medida | Valor |
|---|---|
| Tamanho da página HTML | **3,6 MB** (0,52 MB comprimida na rede) |
| Anúncios na página | 96 |
| CPU para ler a página | **~104 ms** por página |
| Memória extra durante a leitura | **~37 MB** por página |

**Conclusão:** cada pedido à Vinted é pesado. O custo não está no número de anúncios, está no número de **páginas descarregadas**.

Também testei uma forma mais leve de ler a página (procurar a lista de anúncios diretamente no HTML). **O ganho foi praticamente zero** (101 ms contra 104 ms), porque a lista já aparece no início da página. Otimizar a leitura não compensa: o que compensa é **descarregar menos páginas**.

---

## 4. Quantas páginas a API descarrega

Cada ciclo de um alerta descarrega:

```
páginas por ciclo = número de países × páginas do alerta
```

| Opção do alerta | Países | Páginas (1 a 3) | Páginas por ciclo |
|---|---|---|---|
| Um país (ex.: Portugal) | 1 | 1 | **1** |
| Um país, 3 páginas | 1 | 3 | **3** |
| **"Europa"** | **21** | 2 | **42** |
| **"Europa", 3 páginas** | **21** | 3 | **63** |

Alertas iguais de utilizadores diferentes partilham a busca, o que já é bom.

**Intervalo mínimo entre ciclos por plano** (`app/entitlements.py`):

| Plano | Intervalo mínimo | Observação |
|---|---|---|
| FREE | 1 min | |
| **PRO** | **15 s** | É o plano por omissão (`default_plan = "PRO"`) e o do teste grátis |
| ELITE | 10 s | |

**Buscas extra:**
- **Relógio dos anúncios** (`idclock.py`): faz **mais uma busca a cada 20 s** sempre que há buscas a correr, para estimar há quanto tempo cada anúncio foi publicado. São **4 320 páginas por dia** só para isto.
- **"Buscar" contínuo** (`manual_search.py`): repete as buscas do utilizador **de 5 em 5 s, até 6 horas**, ao mesmo tempo que o monitor automático faz as mesmas buscas.

### Exemplos (1 utilizador PRO)

| Situação | Páginas por dia | CPU só para ler as páginas | Download por dia |
|---|---|---|---|
| 1 alerta em Portugal, 1 página | ~10 000 | ~17 min/dia | ~5 GB |
| 1 alerta "Europa", 2 páginas | ~50 000 | ~90 min/dia | ~26 GB |
| Igual, com "Buscar" ligado | Fica sempre no máximo | — | — |

O download (tráfego que entra) normalmente não é cobrado no Railway, mas é o que gera o trabalho de CPU e de memória.

### O "teto" escondido

Todas as buscas passam por um **cadeado único** com 1 segundo de pausa entre pedidos (`VintedClient.fetch`). Por isso a API nunca faz mais do que ~1 página por segundo, seja qual for o número de utilizadores.

- **Para o custo, é bom:** a CPU tem um limite.
- **Para o serviço, é mau:** um único alerta "Europa" ocupa a fila e **atrasa os avisos de todos os outros utilizadores**. Com intervalos de 10 a 15 s, a API fica praticamente **100% do tempo a buscar**, sem nunca descansar.

---

## 5. O que consome, por ordem de impacto

### 5.1 Alertas "Europa" (impacto: muito alto)
Um alerta "Europa" faz **21 vezes** o trabalho de um alerta de um país. O próprio código regista que **o mesmo anúncio aparece em vários países** (a deteção de repetidos em `run_alerts`). Muitas dessas 21 buscas trazem anúncios repetidos.

### 5.2 Intervalos muito curtos (impacto: alto)
Os 15 s do PRO e os 10 s do ELITE fazem a API trabalhar sem parar. Como a fila só faz ~1 página por segundo, um intervalo mais curto do que o tempo de um ciclo **não traz avisos mais rápidos**: só mantém a CPU e a memória sempre ocupadas.

### 5.3 Busca extra do relógio a cada 20 s (impacto: alto quando há pouco uso)
São 4 320 páginas por dia, mesmo que só haja um alerta pequeno. O relógio **já aproveita** os anúncios das buscas normais (`observe`), por isso pode ser acertado muito menos vezes, por exemplo de 5 em 5 minutos.

### 5.4 "Buscar" contínuo duplicado (impacto: alto enquanto está ligado)
Repete as buscas de 5 em 5 s durante até 6 h e **não partilha os resultados** com o monitor automático. O mesmo alerta é descarregado duas vezes.

### 5.5 Memória do Python (impacto: médio, mas é o que se paga mais)
- Cada página ocupa ~37 MB extra durante a leitura.
- Há várias threads (monitor, buscas manuais, 6 threads de tradução).
- Há 21 sessões do `cloudscraper` abertas, uma por país.

Num Linux, o Python com threads tende a **reter memória que já não usa** (fragmentação do `malloc`). O serviço pode ficar com centenas de MB ocupados mesmo parado. Há também uma pequena fuga de memória: a cache da pré-visualização (`_preview_cache`) nunca apaga entradas antigas.

### 5.6 Verificação da base de dados a cada 5 s (impacto: baixo no Railway, alto no Neon)
Com o monitor ligado, a API consulta o Neon de 5 em 5 segundos e grava uma linha `MonitorRun` por busca. No Railway isto custa pouco, mas **impede o Neon de "adormecer"**, o que gasta as horas de computação do Neon.

---

## 6. O que dá para fazer, e quanto se poupa

### Grupo A — Sem mexer no código (configuração no Railway)

| # | Mudança | Ganho esperado | Risco |
|---|---|---|---|
| A1 | Variável `MALLOC_ARENA_MAX=2` | **-30% a -50% de memória** (habitual em Python com threads) | Muito baixo |
| A2 | `MONITOR_TICK_SECONDS=15` (em vez de 5) | Menos consultas ao Neon, que pode adormecer | Baixo: os avisos podem atrasar até 15 s |
| A3 | Definir **limites de recursos** do serviço (ex.: 0,5 vCPU e 512 MB) | O custo fica com teto | Baixo: confirmar primeiro nas Metrics quanto o serviço usa |
| A4 | Ativar **Usage Limits** e alertas de gasto na conta do Railway | Evita surpresas na fatura | Nenhum |

### Grupo B — Mudanças pequenas no código

| # | Mudança | Ganho esperado | Risco |
|---|---|---|---|
| B1 | Acertar o relógio de 5 em 5 min (em vez de 20 s) | **-4 000 páginas por dia** | Baixo: o "publicado há X min" continua aproximado |
| B2 | Intervalo mínimo PRO 1 min e ELITE 30 s | **Até -75% das buscas** dos utilizadores PRO | Médio: é uma mudança de produto, que tem de ser comunicada |
| B3 | "Buscar": pausa igual ao intervalo do plano e máximo de 1 h (em vez de 6 h) | Corta a duplicação com o monitor | Baixo |
| B4 | Cache curta partilhada (resultado de cada busca reaproveitado durante ~30 s) entre monitor, "Buscar" e pré-visualização | Elimina buscas repetidas | Baixo |
| B5 | Limpar a cache da pré-visualização e libertar a página da memória logo após a leitura | Memória mais estável | Muito baixo |

### Grupo C — Mudanças de produto

| # | Mudança | Ganho esperado |
|---|---|---|
| C1 | "Europa" só no plano ELITE, ou "Europa" = 5–6 países principais em vez de 21 | **Até -70% a -95% das páginas** de quem usa "Europa" |
| C2 | Máximo de páginas por alerta: 1 no PRO, 2 no ELITE | Até -50% |

### Estimativa de poupança

Com **A1 + A2 + B1 + B3 + B5** (tudo de baixo risco e sem mudar o produto):
- **Memória:** -30% a -50%.
- **Buscas:** -40% a -60% em uso normal.

Juntando **B2 + C1** (mudanças de produto), as buscas descem **-80% ou mais**.

---

## 7. Estimativa de custo mensal (só a API, no Railway)

Valores de referência: ~10 $/GB de RAM e ~20 $/vCPU por mês. São estimativas.

| Cenário | RAM média | CPU média | Custo estimado |
|---|---|---|---|
| **Hoje**, com alguns alertas "Europa" | 0,4–0,8 GB | 0,1–0,2 vCPU | **~6–20 $/mês** |
| Depois do Grupo A + B | 0,2–0,4 GB | 0,05–0,1 vCPU | **~3–6 $/mês** |
| Num servidor próprio (Dokploy) | — | — | Preço fixo, dividido com outros projetos |

> Se a fatura real do Railway for **muito maior** do que isto, o problema está noutro lado. Pode haver outros serviços no mesmo projeto (por exemplo o `garimpo-web`, se também estiver lá), réplicas extra, ou uma fuga de memória. Nesse caso, o gráfico de **Memory** no Railway mostra-o como uma linha sempre a subir até ao reinício.

---

## 8. Próximo passo recomendado

1. **Ver as Metrics** do serviço no Railway (CPU, memória e rede dos últimos 7 dias), para confirmar onde está o gasto.
2. **Aplicar o Grupo A** (só variáveis e limites, sem código) e comparar uma semana depois.
3. **Aplicar o Grupo B** no código, com testes (o projeto já tem testes do monitor, do relógio e da Vinted).
4. **Decidir o Grupo C**, que depende do produto: o que cada plano oferece.
5. A médio prazo: mover a API para o servidor próprio com Dokploy, onde o custo fica fixo.

---

### Ficheiros analisados

`app/services/monitor.py`, `manual_search.py`, `vinted.py`, `pipeline.py`, `idclock.py`, `translate.py`, `currency.py`, `maintenance.py`, `app/entitlements.py`, `app/config.py`, `app/db.py`, `app/main.py`, `app/countries.py`, `Dockerfile`, `railway.json`.
