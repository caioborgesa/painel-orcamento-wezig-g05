# =============================================================
# PREPARAR A PUBLICACAO DO PAINEL
# =============================================================
#
# O QUE ESTE ARQUIVO FAZ
#   Deixa o 3D em dia com o quantitativo mais recente, antes de publicar.
#   Para cada modelo medido, confere se a malha em static\malhas e do
#   mesmo IFC registrado no quantitativo, e refaz a que estiver atrasada.
#   E o mesmo que o painel faz ao abrir no computador local.
#
# POR QUE ISSO IMPORTA
#   Online nao ha IFC: o 3D que o link mostra e exatamente a malha que foi
#   enviada. Se ela for de um IFC antigo, o 3D fica diferente dos numeros.
#
# QUEM CHAMA
#   O "PUBLICAR PAINEL ONLINE.bat" (pasta 06 ORCAMENTO), antes do envio.
# =============================================================

import json
import sys
from pathlib import Path

PASTA_PAINEL = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_PAINEL.parent / "4 QUANTITATIVOS" / "SCRIPTS"))
sys.path.insert(0, str(PASTA_PAINEL))

import config  # noqa: E402
from preparar_malhas import preparar_malha  # noqa: E402

# O quantitativo que o painel mostra: o de carimbo mais recente
arquivos = sorted(config.PASTA_SAIDA.glob("quantitativos WEZIG *.json"))
if not arquivos:
    raise SystemExit("Nenhum quantitativo em 4 QUANTITATIVOS\\3 RESULTADOS.")

with open(arquivos[-1], encoding="utf-8") as arquivo:
    modelos = json.load(arquivo)["procedencia"]["modelos"]

print(f"Quantitativo: {arquivos[-1].name}")
for nome, info in modelos.items():
    if not info.get("aberto_nesta_rodada"):
        continue  # modelo nao medido: nao aparece no 3D
    caminho_do_ifc = config.PASTA_TFM / info["caminho"]
    if not caminho_do_ifc.exists():
        raise SystemExit(f"O IFC medido do modelo {nome} nao existe mais: {info['caminho']}\n"
                         "Gere o quantitativo de novo antes de publicar.")
    malha = preparar_malha(nome, caminho_do_ifc)
    print(f"  {nome}: 3D em dia ({len(malha['elementos'])} elementos · {caminho_do_ifc.name})")
