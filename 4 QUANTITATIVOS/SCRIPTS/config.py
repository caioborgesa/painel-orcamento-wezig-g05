# =============================================================
# CONFIGURACAO DA ETAPA 4 — QUANTITATIVOS
# =============================================================
#
# Tudo o que muda de uma rodada para outra fica AQUI:
#   - onde esta a EAP + Servicos
#   - qual arquivo IFC vale para cada disciplina
#   - como cada modelo chama os pavimentos
#
# Os caminhos sao montados a partir da pasta do TFM, descoberta sozinha
# pela posicao deste arquivo. Assim, se a pasta do TFM mudar de lugar no
# computador, nada aqui precisa ser editado (foi o que quebrou o script
# antigo quando a pasta saiu de "2 AREAS").
# =============================================================

from pathlib import Path

# Pasta deste arquivo: ...\ZIGURAT TFM\06 ORCAMENTO\4 QUANTITATIVOS\SCRIPTS
PASTA_SCRIPTS = Path(__file__).resolve().parent
PASTA_QUANTITATIVOS = PASTA_SCRIPTS.parent
PASTA_ORCAMENTO = PASTA_QUANTITATIVOS.parent
PASTA_TFM = PASTA_ORCAMENTO.parent

# MODO ONLINE — o painel publicado na internet (so consulta)
#   No computador do Caio, o "02 RECEBIDO CDE" fica ao lado do 06 ORCAMENTO.
#   No servidor so sobe o 06 ORCAMENTO, entao essa pasta nao existe la.
#   Sem ela nao ha IFC para conferir: o painel funciona so para consulta.
MODO_ONLINE = not (PASTA_TFM / "02 RECEBIDO CDE").exists()

# As pastas da etapa 4, na ordem em que sao usadas:
#   1 REGRAS      as regras que valem (uma por origem)
#   2 PROPOSTAS   regras aguardando revisao, e o quantitativo de teste delas
#   3 RESULTADOS  o quantitativo mais recente e as verificacoes do app
#   _ARQUIVO      o que saiu de circulacao (nada e apagado)
PASTA_REGRAS = PASTA_QUANTITATIVOS / "1 REGRAS"
PASTA_PROPOSTAS = PASTA_QUANTITATIVOS / "2 PROPOSTAS"
PASTA_SAIDA = PASTA_QUANTITATIVOS / "3 RESULTADOS"
PASTA_ARQUIVO = PASTA_QUANTITATIVOS / "_ARQUIVO"

# A etapa 5 (custo) fica ao lado. O painel le o orcamento mais recente
# daqui para mostrar o custo junto da quantidade.
PASTA_ORCAMENTO_RESULTADOS = PASTA_ORCAMENTO / "5 ORCAMENTO" / "3 RESULTADOS"


# -------------------------------------------------------------
# EAP + SERVICOS (etapa 3)
#
# Na etapa 3, o oficial e o arquivo de CARIMBO MAIS RECENTE
# ("EAP + SERVICOS WEZIG AAAA-MM-DD HHMM.xlsx"). O carimbo ordena sozinho
# por nome. A copia sem carimbo e so para visualizacao e nao e lida.
# -------------------------------------------------------------
PASTA_ETAPA_3 = PASTA_ORCAMENTO / "3 EAP + SERVICOS"
_EAP_SERVICOS_COM_CARIMBO = sorted(PASTA_ETAPA_3.glob("EAP + SERVICOS WEZIG *.xlsx"))
if _EAP_SERVICOS_COM_CARIMBO:
    EAP_SERVICOS = _EAP_SERVICOS_COM_CARIMBO[-1]
elif MODO_ONLINE:
    # Online a planilha nao sobe: o painel nao a le (o nome dela ja vem
    # gravado no JSON do quantitativo)
    EAP_SERVICOS = None
else:
    raise SystemExit("Nenhuma 'EAP + SERVICOS WEZIG <carimbo>.xlsx' na pasta da etapa 3")


# -------------------------------------------------------------
# ARQUIVO DE REGRAS DE CADA ORIGEM DA QUANTIDADE
# (a coluna ORIGEM DA QUANTIDADE da EAP + Servicos)
# -------------------------------------------------------------
ARQUIVO_DE_REGRAS_POR_ORIGEM = {
    "MODELO EST": "regras_est.py",
    "MODELO HID": "regras_hid.py",
    "MODELO ARQ": "regras_arq.py",
    "MODELO INT": "regras_int.py",
    "MANUAL": "regras_manual.py",
}


# -------------------------------------------------------------
# MODELOS IFC — qual arquivo vale para cada disciplina
#
# Ao receber um modelo novo, trocar o caminho aqui. O nome da chave
# ("EST", "HID"...) e o que as regras usam no campo 'modelo'.
# -------------------------------------------------------------
PASTA_CDE = PASTA_TFM / "02 RECEBIDO CDE"

MODELOS = {
    "EST": PASTA_TFM / "04 EST" / "1 MODELO"
           / "CRZ-CBE-ZZZ-ZZZ-M3-EST-0001 2026-09-13 06-45.IFC",
    "HID": PASTA_TFM / "05 HID" / "1 MODELO"
           / "CRZ-EGZ-ZZZ-ZZZ-M3-HID-0001 2026-09-06 15-20.ifc",
    "ARQ-0001": PASTA_CDE / "ABO - ARQ_2026-09-22_06-21-05am" / "ABO - ARQ"
                / "CRZ-ABO-B01-ZZZ-M3-ARQ-0001.ifc",
    "ARQ-0002": PASTA_CDE / "ABO - ARQ_2026-09-22_06-21-05am" / "ABO - ARQ"
                / "CRZ-ABO-B01-ZZZ-M3-ARQ-0002.ifc",
    "INT": PASTA_CDE / "ABO - INT_2026-09-01_07-33-56pm" / "ABO - INT"
           / "CRZ-ABO-B01-ZZZ-M3-INT-1001.ifc",
}


# -------------------------------------------------------------
# PAVIMENTOS
#
# A EAP usa sempre os mesmos codigos (NFN, NB1, N00 ... N11). Cada modelo
# chama o pavimento de um jeito (IfcBuildingStorey.Name). As tabelas
# abaixo traduzem o nome do modelo para o codigo da EAP.
#
# Os nomes foram copiados dos proprios IFC em 2026-09-12. Um pavimento
# que nao estiver aqui fica sem traducao e o gerador avisa.
# -------------------------------------------------------------
# NFN = nivel de fundacao (estacas e blocos), NB1 = subsolo.
PAVIMENTOS_DA_EAP = ["NFN", "NB1", "N00", "N01", "N02", "N03", "N04", "N05",
                     "N06", "N07", "N08", "N09", "N10", "N11"]

PAVIMENTOS = {
    # O TQS chama os 6 pavimentos tipo de "N03 ... ST-001" ate "ST-006".
    # Na EAP eles sao N03 ate N08.
    # Desde o modelo de 2026-09-13 o subsolo chama-se "NB1" e a fundacao
    # (estacas e blocos) tem nivel proprio, "NFN". A EAP usa os mesmos
    # codigos desde 2026-09-22.
    "EST": {
        "NFN - Nivel de Fundacao_ST": "NFN",
        "NB1 - Nivel B1_ST": "NB1",
        "N00 - Nivel 00_ST": "N00",
        "N01 - Nivel 01_ST": "N01",
        "N02 - Nivel 02_ST": "N02",
        "N03 - Nivel 03_ST-001": "N03",
        "N03 - Nivel 03_ST-002": "N04",
        "N03 - Nivel 03_ST-003": "N05",
        "N03 - Nivel 03_ST-004": "N06",
        "N03 - Nivel 03_ST-005": "N07",
        "N03 - Nivel 03_ST-006": "N08",
        "N09 - Nivel 09_ST": "N09",
        "N10 - Nivel 10_ST": "N10",
        "N11 - Nivel 11_ST": "N11",
    },

    # Atencao: o Revit escreve "B01- Nivel" (sem espaco antes do hifen);
    # na EAP esse pavimento e o NB1.
    "HID": {
        "B01- Nivel B1_FL": "NB1",
        "N00 - Nivel 00_FL": "N00",
        "N01 - Nivel 01_FL": "N01",
        "N02 - Nivel 02_FL": "N02",
        "N03 - Nivel 03_FL": "N03",
        "N04 - Nivel 04_FL": "N04",
        "N05 - Nivel 05_FL": "N05",
        "N06 - Nivel 06_FL": "N06",
        "N07 - Nivel 07_FL": "N07",
        "N08 - Nivel 08_FL": "N08",
        "N09 - Nivel 09_FL": "N09",
        "N10 - Nivel 10_FL": "N10",
        "N11 - Nivel 11_FL": "N11",
    },

    # O ARQ tem dois niveis por pavimento: _FL (piso acabado) e
    # _ST (estrutura). Os dois vao para o mesmo pavimento da EAP.
    "ARQ-0001": {
        "B01- Nivel B1_FL": "NB1",
        "B01- Nivel B1_ST": "NB1",
        "N00 - Nivel 00_ST": "N00",
        "N00 - Nivel 00_FL": "N00",
        "N01 - Nivel 01_ST": "N01",
        "N01 - Nivel 01_FL": "N01",
        "N02 - Nivel 02_ST": "N02",
        "N02 - Nivel 02_FL": "N02",
        "N03 - Nivel 03_ST": "N03",
        "N03 - Nivel 03_FL": "N03",
        "N04 - Nivel 04_ST": "N04",
        "N04 - Nivel 04_FL": "N04",
        "N05 - Nivel 05_ST": "N05",
        "N05 - Nivel 05_FL": "N05",
        "N06 - Nivel 06_ST": "N06",
        "N06 - Nivel 06_FL": "N06",
        "N07 - Nivel 07_ST": "N07",
        "N07 - Nivel 07_FL": "N07",
        "N08 - Nivel 08_ST": "N08",
        "N08 - Nivel 08_FL": "N08",
        "N09 - Nivel 09_ST": "N09",
        "N09 - Nivel 09_FL": "N09",
        "N10 - Nivel 10_ST": "N10",
        "N10 - Nivel 10_FL": "N10",
        "N11 - Nivel 11_ST": "N11",
        "N11 - Nivel 11_FL": "N11",
    },

    # O ARQ-0002 de 2026-08-02 tinha ainda o nivel _CB; o de 2026-09-22
    # nao tem mais. As linhas _CB ficam, sem efeito, ate a Fase 4.
    "ARQ-0002": {
        "B01- Nivel B1_ST": "NB1",
        "N00 - Nivel 00_ST": "N00",
        "N00 - Nivel 00_FL": "N00",
        "N00 - Nivel 00_CB": "N00",
        "N01 - Nivel 01_ST": "N01",
        "N01 - Nivel 01_FL": "N01",
        "N01 - Nivel 01_CB": "N01",
        "N02 - Nivel 02_ST": "N02",
        "N02 - Nivel 02_FL": "N02",
        "N02 - Nivel 02_CB": "N02",
        "N03 - Nivel 03_ST": "N03",
        "N03 - Nivel 03_FL": "N03",
        "N03 - Nivel 03_CB": "N03",
        "N04 - Nivel 04_ST": "N04",
        "N04 - Nivel 04_FL": "N04",
        "N04 - Nivel 04_CB": "N04",
        "N05 - Nivel 05_ST": "N05",
        "N05 - Nivel 05_FL": "N05",
        "N05 - Nivel 05_CB": "N05",
        "N06 - Nivel 06_ST": "N06",
        "N06 - Nivel 06_FL": "N06",
        "N06 - Nivel 06_CB": "N06",
        "N07 - Nivel 07_ST": "N07",
        "N07 - Nivel 07_FL": "N07",
        "N07 - Nivel 07_CB": "N07",
        "N08 - Nivel 08_ST": "N08",
        "N08 - Nivel 08_FL": "N08",
        "N08 - Nivel 08_CB": "N08",
        "N09 - Nivel 09_ST": "N09",
        "N09 - Nivel 09_FL": "N09",
        "N09 - Nivel 09_CB": "N09",
        "N10 - Nivel 10_ST": "N10",
        "N10 - Nivel 10_FL": "N10",
        "N11 - Nivel 11_ST": "N11",
        "N11 - Nivel 11_FL": "N11",
    },

    # O Archicad escreve "Nivel" com acento. O INT nao tem B01 nem N11.
    "INT": {
        "N00 - Nível 00_FL-ARQ": "N00",
        "N01 - Nível 01_FL-ARQ": "N01",
        "N02 - Nível 02_FL-ARQ": "N02",
        "N03 - Nível 03_ST-ARQ": "N03",
        "N03 - Nível 03_FL-ARQ": "N03",
        "N04 - Nível 04_FL-ARQ": "N04",
        "N05 - Nível 05_FL-ARQ": "N05",
        "N06 - Nível 06_FL-ARQ": "N06",
        "N07 - Nível 07_FL-ARQ": "N07",
        "N08 - Nível 08_FL-ARQ": "N08",
        "N09 - Nível 09_FL-ARQ": "N09",
        "N10 - Nível 10_FL-ARQ": "N10",
    },
}
