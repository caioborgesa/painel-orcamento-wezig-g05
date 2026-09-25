# =============================================================
# VERIFICACOES — o registro do que ja foi auditado
# =============================================================
#
# O QUE ESTE ARQUIVO FAZ
#   Guarda, em "verificacoes WEZIG.json", as linhas que voce conferiu no
#   painel do orcamento — com a quantidade que estava valendo naquele momento.
#
#   Na proxima geracao, cada linha verificada e comparada:
#     mesma quantidade (e mesmo codigo)  -> status VERIFICADO
#     quantidade mudou desde a conferencia -> status DIVERGENTE
#
# POR QUE GUARDAR A QUANTIDADE, E NAO SO "OK"
#   Porque o numero muda quando o modelo ou a regra mudam. Um "OK" solto
#   continuaria valendo para um numero que ninguem conferiu. Guardando o
#   numero, a verificacao "vence" sozinha quando ele muda.
#
# QUEM ESCREVE
#   So o painel do orcamento. O gerar_quantitativos.py apenas le.
# =============================================================

import json
from datetime import datetime

import config

ARQUIVO_DE_VERIFICACOES = config.PASTA_SAIDA / "verificacoes WEZIG.json"

# Diferenca aceita entre a quantidade verificada e a atual.
# O JSON guarda 4 casas decimais; abaixo disso e so arredondamento.
TOLERANCIA = 0.001


def ler_verificacoes():
    """Devolve {referencia: registro}. Vazio se ainda nao ha verificacoes."""
    if not ARQUIVO_DE_VERIFICACOES.exists():
        return {}
    with open(ARQUIVO_DE_VERIFICACOES, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _gravar(registros):
    with open(ARQUIVO_DE_VERIFICACOES, "w", encoding="utf-8") as arquivo:
        json.dump(registros, arquivo, ensure_ascii=False, indent=2, sort_keys=True)


def gravar_verificacao(linha, observacao, arquivo_de_quantitativos):
    """Registra que a linha foi conferida, com a quantidade atual."""
    registros = ler_verificacoes()
    registros[linha["referencia"]] = {
        "codigo": linha["codigo"],
        "unidade": linha["unidade"],
        "quantidade": linha["quantidade"],
        "verificado_em": datetime.now().strftime("%Y-%m-%d %H%M"),
        "observacao": observacao,
        "conferido_no_arquivo": arquivo_de_quantitativos,
    }
    _gravar(registros)


def remover_verificacao(referencia):
    """Desfaz a verificacao de uma linha."""
    registros = ler_verificacoes()
    if referencia in registros:
        del registros[referencia]
        _gravar(registros)


def aplicar_verificacao(linha, registros):
    """Ajusta o status da linha conforme o registro de verificacao.

    O status original da medicao fica em 'status_medicao'; assim, se a
    verificacao for removida, a linha volta ao status de antes.
    """
    status_da_medicao = linha.get("status_medicao", linha["status"])
    linha["status_medicao"] = status_da_medicao
    linha["status"] = status_da_medicao

    registro = registros.get(linha["referencia"])
    linha["verificacao"] = registro
    if registro is None or linha["quantidade"] is None:
        return

    mesmo_numero = abs(linha["quantidade"] - registro["quantidade"]) <= TOLERANCIA
    mesmo_codigo = registro["codigo"] == linha["codigo"]
    if mesmo_numero and mesmo_codigo:
        linha["status"] = "VERIFICADO"
    else:
        linha["status"] = "DIVERGENTE"
