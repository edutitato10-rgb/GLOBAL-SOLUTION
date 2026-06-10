# 🚀 Sistema Inteligente de Gestão de Colônia Espacial

## Visão Geral

Sistema em Python que simula o gerenciamento inteligente de uma colônia espacial. Integra quatro módulos principais: organização de dados, decisão automática, previsão por regressão linear e análise de balanço energético.

---

## Como Executar

```bash
python sistema_colonia.py
```

Nenhuma biblioteca externa é necessária. Compatível com Python 3.7+.

---

## Estrutura do Código

| Função | Responsabilidade |
|---|---|
| `criar_dados_colonia()` | Define histórico (listas), estado atual (dict) e hierarquia de sistemas |
| `navegar_sistema()` | Percorre a hierarquia de sistemas por caminho de chaves |
| `tomar_decisao()` | Aplica regras de lógica e retorna ações priorizadas |
| `calcular_regressao()` | Calcula coeficientes da reta por mínimos quadrados |
| `prever_energia_eolica()` | Estima geração eólica dado vento futuro |
| `analisar_balanco()` | Compara geração, consumo e reserva, emitindo diagnóstico |

---

## Módulos e Exemplos

### 1. Organização de Dados

Dados históricos em listas, estado atual em dicionário chave-valor e sistemas em hierarquia aninhada:

```python
sistemas = {
    "sistema_energetico": {
        "solar":  { "paineis": 12, "status": "ativo" },
        "eolico": { "turbinas": 3, "status": "ativo" },
    },
    "sistema_suporte_vida": { ... },
    "sistema_nao_essencial": { ... },
}
```

### 2. Regras de Decisão

```
Entrada : energia = 40, consumo = 70, geração = 45
Regra   : energia < 50 E consumo > geração → modo economia
Saída   : "ALERTA: energia baixa E consumo maior que geração → ativar modo economia."
          "AÇÃO: desligar entretenimento e iluminação extra."
```

Prioridade das regras:
1. `energia < 20` → EMERGÊNCIA (encerra demais regras)
2. `energia < 50 E consumo > geração` → ALERTA + modo economia
3. `energia < 50` → ATENÇÃO
4. `geração > consumo × 1.5` → SUGESTÃO de armazenamento
5. Default → NORMAL

### 3. Previsão por Regressão Linear

```
Dados   : vento = [8, 10, 12, 9, 11, 13]  energia = [20, 25, 30, 22, 27, 33]
Modelo  : energia = 2.6 × vento + (−1.13)
Entrada : vento = 11 km/h
Saída   : energia ≈ 27.47 kW
```

### 4. Análise de Balanço Energético

```
Entrada : geração = 45, consumo = 70, reserva = 40
Saída   : "AVISO: consumo (70 kW) > geração (45 kW).
           Deficit de 25 kW sendo coberto pela reserva (40 kW)."
```

---

## Exemplo de Saída Completa

```
============================================================
  SISTEMA INTELIGENTE – COLÔNIA ESPACIAL
============================================================

[1] DADOS ATUAIS DA COLÔNIA
    Energia em bateria : 40 kW
    Consumo atual      : 70 kW
    Geração atual      : 45 kW

[2] NAVEGAÇÃO HIERÁRQUICA
    Painéis solares    : 12 unidades, 2.0 kW cada, status: ativo

[3] DECISÃO AUTOMÁTICA
    ALERTA: energia baixa E consumo maior que geração → ativar modo economia.
    AÇÃO: desligar entretenimento e iluminação extra.

[4] PREVISÃO DE ENERGIA EÓLICA (regressão linear)
    Modelo ajustado    : energia = 2.6 × vento + (-1.1333)
    Entrada            : vento = 11 km/h
    Saída (previsão)   : energia ≈ 27.47 kW

[5] ANÁLISE DE BALANÇO ENERGÉTICO
    AVISO: consumo (70 kW) > geração (45 kW). Deficit de 25 kW sendo coberto pela reserva (40 kW).
```

---

## Critérios Atendidos

- **Estrutura de dados**: listas, dicionários e hierarquia aninhada
- **Lógica de decisão**: regras com prioridade, condições simples e combinadas
- **Regressão linear**: implementada do zero com mínimos quadrados
- **Análise energética**: comparação geração × consumo × reserva com diagnóstico
- **Código em funções**: separação clara entre dados, lógica e decisões
