"""
=============================================================
 SISTEMA INTELIGENTE DE MONITORAMENTO DE MISSÃO ESPACIAL
 Global Solution 2026 - FIAP
=============================================================
 Equipe: [EDUARDO TITATO]
 Integrantes: [EDUARDO TITATO - RM: 572776
]
=============================================================
"""

import csv
import os
from collections import deque
from datetime import datetime

# ─────────────────────────────────────────────
#  CONSTANTES E LIMIARES DE SEGURANÇA
# ─────────────────────────────────────────────

LIMIAR_ENERGIA_ALERTA   = 40   # % de reserva
LIMIAR_ENERGIA_CRITICO  = 25   # %
LIMIAR_RADIACAO_ALERTA  = 80   # mSv
LIMIAR_RADIACAO_CRITICO = 100  # mSv
LIMIAR_TEMP_MAX         = 30   # °C interno
LIMIAR_TEMP_MIN         = 15   # °C interno
LIMIAR_SINAL_ALERTA     = 50   # % qualidade
LIMIAR_SINAL_CRITICO    = 20   # %

CAMINHO_DADOS = os.path.join(os.path.dirname(__file__), "..", "data", "dados.csv")


# ═══════════════════════════════════════════
#  1. LEITURA E INTERPRETAÇÃO DOS DADOS
# ═══════════════════════════════════════════

def carregar_dados(caminho: str) -> dict:
    """
    Lê o arquivo CSV de telemetria e organiza os dados em um dicionário
    estruturado por categoria. Retorna o dicionário completo da missão.
    """
    dados = {
        "modulos":    {},   # dicionário  -> acesso rápido por nome
        "energia":    {},   # dicionário de listas por variável
        "ambiente":   {},   # dicionário de listas por variável
        "log":        [],   # lista de eventos cronológicos
    }

    try:
        with open(caminho, newline="", encoding="utf-8") as f:
            leitor = csv.DictReader(f)
            for linha in leitor:
                tipo  = linha["tipo"]
                campo = linha["campo"]
                valor = linha["valor"]
                ts    = linha["timestamp"]

                # ── módulos binários ──────────────────────────────
                if tipo == "modulo":
                    # Armazena 0/1 convertido para bool
                    dados["modulos"][campo] = bool(int(valor))

                # ── séries de energia ─────────────────────────────
                elif tipo == "energia":
                    dados["energia"].setdefault(campo, [])
                    dados["energia"][campo].append((ts, float(valor)))

                # ── variáveis ambientais ──────────────────────────
                elif tipo == "ambiente":
                    dados["ambiente"].setdefault(campo, [])
                    dados["ambiente"][campo].append((ts, float(valor)))

                # ── log de eventos ────────────────────────────────
                # No CSV de log: campo=nome_evento, valor=descricao, unidade=nivel
                elif tipo == "log":
                    dados["log"].append({
                        "evento":    campo,
                        "descricao": valor,
                        "nivel":     linha["unidade"],
                        "timestamp": ts,
                    })

    except FileNotFoundError:
        print(f"[AVISO] Arquivo '{caminho}' não encontrado. Usando dados embutidos.")
        dados = _dados_embutidos()

    return dados


def _dados_embutidos() -> dict:
    """Dados de fallback caso o CSV não seja encontrado."""
    return {
        "modulos": {
            "suporte_vida":  True,
            "energia":       True,
            "comunicacao":   False,
            "habitat":       True,
            "laboratorio":   True,
            "armazenamento": True,
        },
        "energia": {
            "geracao": [
                ("T0", 28), ("T2", 32), ("T4", 45),
                ("T6", 41), ("T8", 25), ("T10", 20),
            ],
            "consumo": [
                ("T0", 55), ("T2", 58), ("T4", 60),
                ("T6", 72), ("T8", 78), ("T10", 80),
            ],
            "reserva": [
                ("T0", 65), ("T2", 58), ("T4", 50),
                ("T6", 43), ("T8", 32), ("T10", 22),
            ],
        },
        "ambiente": {
            "temperatura_interna": [("T0", 21), ("T4", 22), ("T8", 24)],
            "radiacao":            [("T0", 72), ("T4", 85), ("T8", 110)],
            "qualidade_comunicacao": [("T0", 82), ("T4", 45), ("T8", 12)],
        },
        "log": [
            {"evento": "BOOT_SISTEMA",        "descricao": "Sistema inicializado",           "nivel": "info",   "timestamp": "T0:00"},
            {"evento": "FALHA_COMUNICACAO",   "descricao": "Sinal degradado",                "nivel": "alerta", "timestamp": "T1:30"},
            {"evento": "ENERGIA_ALERTA",      "descricao": "Reserva abaixo de 60%",          "nivel": "alerta", "timestamp": "T3:45"},
            {"evento": "SENSOR_FALHA",        "descricao": "Leitura -120°C suspeita",        "nivel": "critico","timestamp": "T5:00"},
            {"evento": "REINICIALIZACAO",     "descricao": "Módulo de comun. reiniciado",    "nivel": "info",   "timestamp": "T5:15"},
            {"evento": "COMUNICACAO_CRITICA", "descricao": "Qualidade abaixo de 20%",        "nivel": "critico","timestamp": "T8:30"},
            {"evento": "ENERGIA_CRITICA",     "descricao": "Reserva abaixo de 25%",          "nivel": "critico","timestamp": "T9:00"},
            {"evento": "PRIORIDADE_ALTERADA", "descricao": "Laboratório desligado",          "nivel": "alerta", "timestamp": "T9:15"},
        ],
    }


# ═══════════════════════════════════════════
#  2. ORGANIZAÇÃO DAS ESTRUTURAS DE DADOS
# ═══════════════════════════════════════════

def organizar_estruturas(dados: dict) -> dict:
    """
    Constrói as estruturas especializadas a partir do dicionário bruto:
      - fila  : alertas pendentes (deque, FIFO)
      - pilha : últimos eventos críticos analisados (list, LIFO)
      - matriz: leituras de energia por horário x variável
      - árvore simplificada: hierarquia da missão (dict aninhado)
    """

    # ── FILA de alertas (FIFO) ────────────────────────────────────────
    fila_alertas: deque = deque()

    # ── PILHA de eventos críticos (LIFO) ─────────────────────────────
    pilha_criticos: list = []

    for evento in dados["log"]:
        if evento["nivel"] in ("alerta", "critico"):
            fila_alertas.append(evento)           # enfileira alertas
        if evento["nivel"] == "critico":
            pilha_criticos.append(evento)         # empilha críticos

    # ── MATRIZ de energia [horário][variável] ─────────────────────────
    # Estrutura: lista de listas  →  matriz[i][j]
    # Linhas = horários; Colunas = [ts, geracao, consumo, reserva]
    horarios = [ts for ts, _ in dados["energia"].get("geracao", [])]
    matriz_energia = []
    for i, ts in enumerate(horarios):
        linha = [
            ts,
            dados["energia"]["geracao"][i][1]  if i < len(dados["energia"].get("geracao", []))  else 0,
            dados["energia"]["consumo"][i][1]  if i < len(dados["energia"].get("consumo", []))  else 0,
            dados["energia"]["reserva"][i][1]  if i < len(dados["energia"].get("reserva", []))  else 0,
        ]
        matriz_energia.append(linha)

    # ── HIERARQUIA da missão (árvore como dict aninhado) ─────────────
    hierarquia = {
        "MISSAO_ESPACIAL": {
            "ENERGIA": {
                "solar":    "geracao solar",
                "baterias": "reserva energetica",
            },
            "HABITAT": {
                "oxigenio":    dados["modulos"].get("suporte_vida", False),
                "temperatura": dados["ambiente"].get("temperatura_interna", []),
                "comunicacao": dados["modulos"].get("comunicacao", False),
            },
            "OPERACOES": {
                "laboratorio":   dados["modulos"].get("laboratorio", False),
                "armazenamento": dados["modulos"].get("armazenamento", False),
            },
        }
    }

    return {
        "fila_alertas":   fila_alertas,
        "pilha_criticos": pilha_criticos,
        "matriz_energia": matriz_energia,
        "hierarquia":     hierarquia,
    }


# ═══════════════════════════════════════════
#  3. REGRAS LÓGICAS E DIAGNÓSTICO
# ═══════════════════════════════════════════

def diagnosticar(dados: dict) -> dict:
    """
    Aplica as regras lógicas booleanas para classificar o estado da missão.

    EXPRESSÃO BOOLEANA PRINCIPAL:
      estado_critico = (NOT suporte_vida) OR (NOT energia_modulo)
                        OR (reserva < LIMIAR_CRITICO AND NOT comunicacao)
                        OR (radiacao > LIMIAR_CRITICO)

      estado_alerta  = (NOT comunicacao)
                        OR (reserva < LIMIAR_ALERTA)
                        OR (radiacao > LIMIAR_ALERTA)
                        OR (qualidade_sinal < LIMIAR_SINAL_ALERTA)
    """

    modulos   = dados["modulos"]
    energia   = dados["energia"]
    ambiente  = dados["ambiente"]

    # Últimas leituras (valor mais recente de cada série)
    reserva_atual      = energia["reserva"][-1][1]       if energia.get("reserva")      else 100
    geracao_atual      = energia["geracao"][-1][1]       if energia.get("geracao")      else 0
    consumo_atual      = energia["consumo"][-1][1]       if energia.get("consumo")      else 0
    radiacao_atual     = ambiente["radiacao"][-1][1]     if ambiente.get("radiacao")    else 0
    temp_interna_atual = ambiente["temperatura_interna"][-1][1] if ambiente.get("temperatura_interna") else 22
    sinal_atual        = ambiente["qualidade_comunicacao"][-1][1] if ambiente.get("qualidade_comunicacao") else 100

    # Flags booleanas de módulos
    suporte_vida  = modulos.get("suporte_vida",  True)
    energia_ok    = modulos.get("energia",        True)
    comunicacao   = modulos.get("comunicacao",   False)
    habitat       = modulos.get("habitat",        True)
    laboratorio   = modulos.get("laboratorio",    True)
    armazenamento = modulos.get("armazenamento",  True)

    # ── Regras lógicas (AND / OR / NOT) ──────────────────────────────

    # Regra 1: energia crítica  (reserva baixa E consumo maior que geração)
    energia_critica = (reserva_atual < LIMIAR_ENERGIA_CRITICO) and (consumo_atual > geracao_atual)

    # Regra 2: comunicação comprometida  (módulo falhou OU sinal péssimo)
    comunicacao_comprometida = (not comunicacao) or (sinal_atual < LIMIAR_SINAL_CRITICO)

    # Regra 3: radiação perigosa
    radiacao_perigosa = radiacao_atual > LIMIAR_RADIACAO_CRITICO

    # Regra 4: vida em risco (suporte ou habitat falhou)
    vida_em_risco = (not suporte_vida) or (not habitat)

    # Regra 5: temperatura fora da faixa segura
    temp_anormal = (temp_interna_atual > LIMIAR_TEMP_MAX) or (temp_interna_atual < LIMIAR_TEMP_MIN)

    # Regra 6: alerta de energia (apenas alerta, não crítico ainda)
    energia_em_alerta = (reserva_atual < LIMIAR_ENERGIA_ALERTA) and not energia_critica

    # Regra 7: sinal em alerta
    sinal_em_alerta = (sinal_atual < LIMIAR_SINAL_ALERTA) and not comunicacao_comprometida

    # ── Expressão booleana principal ─────────────────────────────────
    estado_critico = vida_em_risco or energia_critica or (radiacao_perigosa and comunicacao_comprometida)
    estado_alerta  = (not estado_critico) and (
        energia_em_alerta or comunicacao_comprometida or
        sinal_em_alerta   or temp_anormal or
        (radiacao_atual > LIMIAR_RADIACAO_ALERTA)
    )
    estado_normal  = not estado_critico and not estado_alerta

    if estado_critico:
        status_geral = "CRITICO"
    elif estado_alerta:
        status_geral = "ALERTA"
    else:
        status_geral = "NORMAL"

    return {
        "status_geral":             status_geral,
        "reserva_atual":            reserva_atual,
        "geracao_atual":            geracao_atual,
        "consumo_atual":            consumo_atual,
        "radiacao_atual":           radiacao_atual,
        "temp_interna_atual":       temp_interna_atual,
        "sinal_atual":              sinal_atual,
        "energia_critica":          energia_critica,
        "comunicacao_comprometida": comunicacao_comprometida,
        "radiacao_perigosa":        radiacao_perigosa,
        "vida_em_risco":            vida_em_risco,
        "temp_anormal":             temp_anormal,
        "energia_em_alerta":        energia_em_alerta,
        "modulos":                  modulos,
    }


# ═══════════════════════════════════════════
#  4. ALERTAS AUTOMÁTICOS
# ═══════════════════════════════════════════

def gerar_alertas(diagnostico: dict) -> list:
    """
    Gera lista de alertas ordenados por severidade (crítico > alerta > normal).
    Cada alerta contém: nivel, mensagem, recomendacao.
    """
    alertas = []

    def add(nivel, mensagem, recomendacao):
        alertas.append({
            "nivel":        nivel,
            "mensagem":     mensagem,
            "recomendacao": recomendacao,
        })

    # ── Alertas críticos ─────────────────────────────────────────────
    if diagnostico["vida_em_risco"]:
        add("CRITICO",
            "Módulo de suporte à vida ou habitat com falha detectada.",
            "Acionar protocolo de emergência imediatamente. Verificar fornecimento de O₂.")

    if diagnostico["energia_critica"]:
        add("CRITICO",
            f"Reserva energética em {diagnostico['reserva_atual']:.0f}% – nível crítico.",
            "Desligar todos os sistemas não essenciais. Manter apenas suporte à vida e comunicação de emergência.")

    if diagnostico["comunicacao_comprometida"]:
        add("CRITICO",
            f"Comunicação comprometida – qualidade do sinal em {diagnostico['sinal_atual']:.0f}%.",
            "Ativar rádio de emergência de backup. Aguardar janela de comunicação.")

    if diagnostico["radiacao_perigosa"]:
        add("CRITICO",
            f"Nível de radiação em {diagnostico['radiacao_atual']:.0f} mSv – acima do limiar seguro.",
            "Recolher tripulação para área blindada. Suspender EVAs imediatamente.")

    # ── Alertas de atenção ───────────────────────────────────────────
    if diagnostico["energia_em_alerta"]:
        add("ALERTA",
            f"Reserva energética em {diagnostico['reserva_atual']:.0f}% – monitoramento intensificado.",
            "Reduzir consumo do laboratório e sistemas secundários. Maximizar captação solar.")

    if diagnostico["temp_anormal"]:
        add("ALERTA",
            f"Temperatura interna fora da faixa segura ({diagnostico['temp_interna_atual']:.1f}°C).",
            "Verificar sistema de climatização do habitat. Checar vedações externas.")

    modulos = diagnostico["modulos"]
    for nome, ativo in modulos.items():
        if not ativo and nome not in ("comunicacao",):   # comunicação já tratada acima
            add("ALERTA",
                f"Módulo '{nome}' reportando falha (status = 0).",
                f"Executar diagnóstico no módulo '{nome}'. Verificar conexões e reiniciar se possível.")

    # ── Status normal ────────────────────────────────────────────────
    if not alertas:
        add("NORMAL",
            "Todos os sistemas dentro dos parâmetros operacionais.",
            "Manter monitoramento de rotina. Nenhuma ação imediata necessária.")

    # Ordena: CRITICO primeiro, depois ALERTA, depois NORMAL
    ordem = {"CRITICO": 0, "ALERTA": 1, "NORMAL": 2}
    alertas.sort(key=lambda a: ordem[a["nivel"]])

    return alertas


# ═══════════════════════════════════════════
#  5. ANÁLISE E PREVISÃO (Regressão Linear)
# ═══════════════════════════════════════════

def regressao_linear(xs: list, ys: list) -> tuple:
    """
    Calcula coeficientes (a, b) da reta y = a*x + b
    usando mínimos quadrados – sem bibliotecas externas.
    Retorna (inclinacao, intercepto).
    """
    n = len(xs)
    soma_x  = sum(xs)
    soma_y  = sum(ys)
    soma_xy = sum(x * y for x, y in zip(xs, ys))
    soma_x2 = sum(x ** 2 for x in xs)

    denominador = n * soma_x2 - soma_x ** 2
    if denominador == 0:
        return 0, soma_y / n   # série constante

    a = (n * soma_xy - soma_x * soma_y) / denominador
    b = (soma_y - a * soma_x) / n
    return a, b


def prever_reserva(energia: dict, ciclos_futuros: int = 3) -> dict:
    """
    Aplica regressão linear sobre a série temporal de reserva energética
    para prever o valor nos próximos ciclos (cada ciclo = 2h).

    Retorna dict com: valores históricos, coeficientes, previsões e tendência.
    """
    serie = energia.get("reserva", [])
    if len(serie) < 2:
        return {"erro": "Dados insuficientes para previsão."}

    xs = list(range(len(serie)))              # índices 0,1,2,...
    ys = [v for _, v in serie]

    a, b = regressao_linear(xs, ys)

    ultimo_idx = xs[-1]
    previsoes = []
    for i in range(1, ciclos_futuros + 1):
        idx_futuro = ultimo_idx + i
        valor_previsto = a * idx_futuro + b
        valor_previsto = max(0, min(100, valor_previsto))   # limita [0, 100]
        previsoes.append((f"Ciclo +{i*2}h", round(valor_previsto, 1)))

    tendencia = "queda" if a < -0.5 else ("subida" if a > 0.5 else "estável")

    return {
        "historico":   [(ts, v) for ts, v in serie],
        "inclinacao":  round(a, 3),
        "intercepto":  round(b, 3),
        "previsoes":   previsoes,
        "tendencia":   tendencia,
    }


# ═══════════════════════════════════════════
#  6. VERIFICAÇÃO DE INCONSISTÊNCIAS
# ═══════════════════════════════════════════

def detectar_inconsistencias(dados: dict) -> list:
    """
    Analisa os dados em busca de leituras fora de faixa fisicamente plausível.
    A inconsistência proposital no CSV é a temperatura externa de -120°C
    registrada no log de sensor. Aqui verificamos valores aberrantes.
    """
    problemas = []
    ambiente = dados.get("ambiente", {})

    # Temperatura externa: na superfície de Marte esperado ~-130°C a +20°C
    for ts, val in ambiente.get("temperatura_externa", []):
        if val < -130 or val > 50:
            problemas.append(
                f"[INCONSISTÊNCIA] Temperatura externa {val}°C em {ts} "
                f"está fora da faixa plausível (esperado: -130°C a 50°C)."
            )

    # Radiação não pode ser negativa
    for ts, val in ambiente.get("radiacao", []):
        if val < 0:
            problemas.append(f"[INCONSISTÊNCIA] Radiação negativa ({val} mSv) em {ts} – sensor com defeito.")

    # Qualidade de sinal: deve ser [0, 100]
    for ts, val in ambiente.get("qualidade_comunicacao", []):
        if val < 0 or val > 100:
            problemas.append(f"[INCONSISTÊNCIA] Qualidade de sinal {val}% em {ts} – fora de [0, 100].")

    # Reserva de energia: deve ser [0, 100]
    for ts, val in dados.get("energia", {}).get("reserva", []):
        if val < 0 or val > 100:
            problemas.append(f"[INCONSISTÊNCIA] Reserva energética {val}% em {ts} – fora de [0, 100].")

    # Verifica inconsistência proposital no log
    for evento in dados.get("log", []):
        if "SENSOR_FALHA" in evento["evento"] or "-120" in evento["descricao"]:
            problemas.append(
                f"[INCONSISTÊNCIA NO LOG] {evento['timestamp']} – "
                f"{evento['descricao']} (temperatura -120°C fisicamente implausível)."
            )
            break

    return problemas


# ═══════════════════════════════════════════
#  7. EXIBIÇÃO DO RELATÓRIO
# ═══════════════════════════════════════════

SEPARADOR = "=" * 62

def exibir_cabecalho():
    print(SEPARADOR)
    print("  SISTEMA DE MONITORAMENTO – MISSÃO ESPACIAL EXPERIMENTAL")
    print(f"  Relatório gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEPARADOR)


def exibir_status_modulos(modulos: dict):
    print("\n[ STATUS DOS MÓDULOS CRÍTICOS ]")
    print("-" * 40)
    for nome, ativo in modulos.items():
        icone  = "✅ NORMAL"  if ativo else "❌ FALHA"
        estado = 1 if ativo else 0
        print(f"  {nome:<20} | bit={estado} | {icone}")


def exibir_matriz_energia(matriz: list):
    print("\n[ MATRIZ DE ENERGIA – kWh / % Reserva ]")
    print("-" * 62)
    print(f"  {'Horário':<22} | {'Geração':>8} | {'Consumo':>8} | {'Reserva(%)':>10}")
    print("-" * 62)
    for linha in matriz:
        ts, ger, cons, res = linha
        print(f"  {str(ts):<22} | {ger:>8.1f} | {cons:>8.1f} | {res:>10.1f}")


def exibir_diagnostico(diag: dict):
    nivel_str = {
        "CRITICO": "🔴 CRÍTICO",
        "ALERTA":  "🟡 ALERTA",
        "NORMAL":  "🟢 NORMAL",
    }
    print("\n[ DIAGNÓSTICO GERAL DA MISSÃO ]")
    print("-" * 40)
    print(f"  STATUS GERAL : {nivel_str[diag['status_geral']]}")
    print(f"  Reserva      : {diag['reserva_atual']:.0f}%")
    print(f"  Geração      : {diag['geracao_atual']:.1f} kWh")
    print(f"  Consumo      : {diag['consumo_atual']:.1f} kWh")
    print(f"  Radiação     : {diag['radiacao_atual']:.0f} mSv")
    print(f"  Temp. interna: {diag['temp_interna_atual']:.1f}°C")
    print(f"  Sinal comun. : {diag['sinal_atual']:.0f}%")


def exibir_alertas(alertas: list):
    print("\n[ ALERTAS AUTOMÁTICOS – PRIORIZADOS ]")
    print("-" * 62)
    icones = {"CRITICO": "🔴", "ALERTA": "🟡", "NORMAL": "🟢"}
    for i, alerta in enumerate(alertas, start=1):
        ic = icones[alerta["nivel"]]
        print(f"\n  {i}. {ic} [{alerta['nivel']}]")
        print(f"     Situação    : {alerta['mensagem']}")
        print(f"     Recomendação: {alerta['recomendacao']}")


def exibir_previsao(prev: dict):
    print("\n[ ANÁLISE E PREVISÃO – RESERVA ENERGÉTICA ]")
    print("-" * 62)
    if "erro" in prev:
        print(f"  {prev['erro']}")
        return

    print("  Método: Regressão Linear (mínimos quadrados) – sem libs externas")
    print(f"  Inclinação (a) : {prev['inclinacao']} %/ciclo")
    print(f"  Intercepto (b) : {prev['intercepto']} %")
    print(f"  Tendência      : {prev['tendencia'].upper()}")
    print("\n  Histórico:")
    for ts, v in prev["historico"]:
        barra = "█" * int(v / 5)
        print(f"    {str(ts):<22} | {v:>5.1f}% {barra}")
    print("\n  Previsão para próximos ciclos:")
    for ciclo, val in prev["previsoes"]:
        alerta = " ⚠️  CRÍTICO" if val < LIMIAR_ENERGIA_CRITICO else (
                 " ⚠️  ALERTA"  if val < LIMIAR_ENERGIA_ALERTA  else "")
        print(f"    {ciclo:<12} → {val:>5.1f}%{alerta}")


def exibir_inconsistencias(problemas: list):
    print("\n[ DETECÇÃO DE INCONSISTÊNCIAS NOS DADOS ]")
    print("-" * 62)
    if not problemas:
        print("  Nenhuma inconsistência detectada.")
    for p in problemas:
        print(f"  {p}")


def exibir_log(log: list, pilha_criticos: list):
    print("\n[ LOG DE EVENTOS – FILA DE ALERTAS PENDENTES ]")
    print("-" * 62)
    icones_nivel = {"info": "ℹ️ ", "alerta": "⚠️ ", "critico": "🔴"}
    for evento in log:
        nivel = evento["nivel"].lower()
        ic = icones_nivel.get(nivel, "  ")
        print(f"  {evento['timestamp']}  {ic} [{nivel.upper():<7}]  "
              f"{evento['evento']}: {evento['descricao']}")

    print("\n  PILHA – últimos eventos críticos (topo = mais recente):")
    for ev in reversed(pilha_criticos):
        print(f"    ↑ {ev['timestamp']}  {ev['evento']}")


# ═══════════════════════════════════════════
#  PONTO DE ENTRADA PRINCIPAL
# ═══════════════════════════════════════════

def main():
    exibir_cabecalho()

    # 1. Leitura
    dados = carregar_dados(CAMINHO_DADOS)

    # 2. Organização das estruturas
    estruturas = organizar_estruturas(dados)

    # 3. Diagnóstico lógico
    diagnostico = diagnosticar(dados)

    # 4. Alertas automáticos
    alertas = gerar_alertas(diagnostico)

    # 5. Previsão energética
    previsao = prever_reserva(dados["energia"], ciclos_futuros=3)

    # 6. Inconsistências
    inconsistencias = detectar_inconsistencias(dados)

    # ── Exibição completa ────────────────────────────────────────────
    exibir_status_modulos(dados["modulos"])
    exibir_matriz_energia(estruturas["matriz_energia"])
    exibir_diagnostico(diagnostico)
    exibir_alertas(alertas)
    exibir_previsao(previsao)
    exibir_inconsistencias(inconsistencias)
    exibir_log(dados["log"], estruturas["pilha_criticos"])

    print("\n" + SEPARADOR)
    print("  FIM DO RELATÓRIO DE MONITORAMENTO")
    print(SEPARADOR + "\n")


if __name__ == "__main__":
    main()
