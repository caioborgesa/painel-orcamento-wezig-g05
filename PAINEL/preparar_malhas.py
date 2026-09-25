# =============================================================
# PREPARAR AS MALHAS 3D PARA O APP DE AUDITORIA
# =============================================================
#
# O QUE ESTE ARQUIVO FAZ
#   Converte um modelo IFC em dois arquivos leves, lidos pelo app:
#     static\malhas\malha_EST.glb       -> a forma de cada elemento, em
#                                          triangulos (o navegador desenha)
#     static\malhas\elementos_EST.json  -> nome, classe, pavimento e
#                                          parametros (o app mostra)
#
#   A geometria sai do mesmo ifcopenshell usado nos medidores: a forma
#   que se ve no 3D e a mesma que as regras enxergam.
#
# QUAL IFC
#   O app passa o caminho do IFC que esta registrado no quantitativo
#   (procedencia.modelos do JSON). Assim o 3D e sempre o modelo que foi
#   medido — nao o que estiver no config.py naquele momento.
#
# POR QUE GLB
#   GLB e o formato padrao de 3D para a web (glTF binario). Os numeros vao
#   gravados como numeros, e nao como texto: o arquivo fica varias vezes
#   menor que um JSON e o navegador abre mais rapido. Cada elemento vira
#   um "no" do GLB com o GlobalId e o pavimento, para o app destacar e
#   esconder pavimentos. Qualquer visualizador de glTF abre o arquivo.
#
# POR QUE NAO MANDAR O IFC PARA O NAVEGADOR
#   O navegador so enxerga arquivos dentro da pasta static do app. Mandar
#   o IFC exigiria copiar os modelos para la — e os do CDE nao se copiam.
#   A malha e um produto derivado, refeito sozinho quando o IFC muda.
#
# QUANDO REFAZ
#   Quando o IFC pedido (caminho + data de modificacao) e diferente do
#   que gerou a malha gravada. So existe uma malha por modelo.
#   Online (painel publicado) nunca refaz: usa a malha que foi publicada.
#
# COMO RODAR SOZINHO (opcional; o app chama automaticamente)
#   python PAINEL\preparar_malhas.py EST      <- usa o IFC do config.py
# =============================================================

import json
import multiprocessing
import struct
import sys
from datetime import datetime
from pathlib import Path

# Este arquivo mora em 06 ORCAMENTO\PAINEL; config.py e ler_modelos.py estao na
# etapa 4. Esta linha ensina o Python a procurar la.
PASTA_PAINEL = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_PAINEL.parent / "4 QUANTITATIVOS" / "SCRIPTS"))

import config  # noqa: E402

# O ifcopenshell e o numpy so servem para GERAR malha, o que so acontece no
# computador local. Online a malha ja vem pronta, e assim o servidor nem
# precisa instalar essas bibliotecas.
if not config.MODO_ONLINE:
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element as util_elemento
    import numpy as np
    from ler_modelos import data_do_arquivo, ler_parametros

PASTA_MALHAS = PASTA_PAINEL / "static" / "malhas"


def url_da_malha(nome_do_modelo, versao):
    """Endereco da malha no app. O '?v=' muda quando o IFC muda, para o
    navegador nao reaproveitar uma malha antiga guardada em cache.

    O endereco e RELATIVO (sem "/" no inicio): o navegador completa a partir
    da pagina do painel. No computador a pagina e "localhost:8501/"; online
    o Streamlit Cloud serve o app em ".../~/+/", e um endereco com "/" no
    inicio pularia essa parte e cairia na tela de login."""
    return f"app/static/malhas/malha_{nome_do_modelo}.glb?v={versao.replace(' ', '_')}"


def pavimento_do_elemento(elemento_ifc, traducao):
    """Pavimento da EAP do elemento. Pecas agregadas (ex.: montantes de
    uma parede cortina) herdam o pavimento da peca-mae."""
    container = util_elemento.get_container(elemento_ifc)
    if container is None:
        mae = util_elemento.get_aggregate(elemento_ifc)
        if mae is not None:
            container = util_elemento.get_container(mae)
    if container is None:
        return None
    return traducao.get(container.Name)


# -------------------------------------------------------------
# GRAVAR O GLB
#
# Um GLB tem tres partes: um cabecalho de 12 bytes, um bloco JSON que
# descreve a cena (quais pecas existem e onde estao os numeros de cada
# uma) e um bloco binario com os numeros em si (vertices e triangulos).
# -------------------------------------------------------------
def gravar_glb(pecas, destino):
    """pecas: lista de {"global_id", "pavimento", "vertices", "triangulos"}."""

    # As coordenadas do IFC podem ser grandes (coordenadas do terreno).
    # Gravadas em float32 (7 algarismos) perderiam precisao, entao todas
    # as pecas sao deslocadas para perto do zero. So a posicao RELATIVA
    # entre pecas importa para o visor.
    todos_os_vertices = np.concatenate([p["vertices"] for p in pecas])
    origem = np.floor(todos_os_vertices.min(axis=0))

    binario = bytearray()
    buffer_views, accessors, meshes, nodes = [], [], [], []

    def acrescentar(bytes_, alvo):
        """Poe um bloco de numeros no binario e devolve o indice da 'view'."""
        while len(binario) % 4:          # cada bloco comeca em multiplo de 4
            binario.append(0)
        buffer_views.append({"buffer": 0, "byteOffset": len(binario),
                             "byteLength": len(bytes_), "target": alvo})
        binario.extend(bytes_)
        return len(buffer_views) - 1

    for peca in pecas:
        vertices = (peca["vertices"] - origem).astype(np.float32)
        triangulos = peca["triangulos"]
        # indices pequenos cabem em 2 bytes; so pecas enormes precisam de 4
        if triangulos.max() < 65535:
            triangulos, tipo_do_indice = triangulos.astype(np.uint16), 5123
        else:
            triangulos, tipo_do_indice = triangulos.astype(np.uint32), 5125

        view_v = acrescentar(vertices.tobytes(), 34962)     # 34962 = vertices
        accessors.append({"bufferView": view_v, "componentType": 5126,  # float32
                          "count": len(vertices), "type": "VEC3",
                          "min": vertices.min(axis=0).tolist(),
                          "max": vertices.max(axis=0).tolist()})
        view_t = acrescentar(triangulos.tobytes(), 34963)   # 34963 = indices
        accessors.append({"bufferView": view_t, "componentType": tipo_do_indice,
                          "count": len(triangulos), "type": "SCALAR"})

        meshes.append({"primitives": [{"attributes": {"POSITION": len(accessors) - 2},
                                       "indices": len(accessors) - 1}]})
        nodes.append({"name": peca["global_id"], "mesh": len(meshes) - 1,
                      "extras": {"global_id": peca["global_id"],
                                 "pavimento": peca["pavimento"]}})

    # No IFC o eixo Z aponta para cima; no glTF, o Y. O no "modelo" gira
    # tudo -90 graus em torno de X para o predio ficar em pe.
    nodes.append({"name": "modelo", "children": list(range(len(nodes))),
                  "rotation": [-0.7071068, 0, 0, 0.7071068],
                  "extras": {"origem_no_ifc": origem.tolist()}})

    cena = {
        "asset": {"version": "2.0", "generator": "preparar_malhas.py (WEZIG)"},
        "scene": 0,
        "scenes": [{"nodes": [len(nodes) - 1]}],
        "nodes": nodes,
        "meshes": meshes,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(binario)}],
    }

    bloco_json = json.dumps(cena, separators=(",", ":")).encode("utf-8")
    bloco_json += b" " * (-len(bloco_json) % 4)   # completa com espacos
    binario.extend(b"\0" * (-len(binario) % 4))   # completa com zeros

    tamanho_total = 12 + 8 + len(bloco_json) + 8 + len(binario)
    with open(destino, "wb") as arquivo:
        arquivo.write(struct.pack("<4sII", b"glTF", 2, tamanho_total))
        arquivo.write(struct.pack("<I4s", len(bloco_json), b"JSON"))
        arquivo.write(bloco_json)
        arquivo.write(struct.pack("<I4s", len(binario), b"BIN\0"))
        arquivo.write(binario)


# -------------------------------------------------------------
# PREPARAR
# -------------------------------------------------------------
def preparar_malha(nome_do_modelo, caminho_do_ifc=None):
    """Garante que a malha do modelo existe e e do IFC pedido.

    caminho_do_ifc: o IFC registrado no quantitativo. Se nao vier, usa o
    do config.py (so para rodar este arquivo sozinho).

    Devolve {"url": endereco da malha, "elementos": {GlobalId: dados},
             "ifc": caminho, "ifc_modificado_em": data}.
    Online, devolve None se a malha do modelo nao foi publicada.
    """
    arquivo_da_malha = PASTA_MALHAS / f"malha_{nome_do_modelo}.glb"
    arquivo_dos_elementos = PASTA_MALHAS / f"elementos_{nome_do_modelo}.json"

    # ---- online: nao ha IFC para conferir; usa a malha publicada ----
    if config.MODO_ONLINE:
        if not (arquivo_da_malha.exists() and arquivo_dos_elementos.exists()):
            return None
        with open(arquivo_dos_elementos, encoding="utf-8") as arquivo:
            gravado = json.load(arquivo)
        # "ifc" e so o nome do arquivo (o caminho completo e do computador local)
        return {"url": url_da_malha(nome_do_modelo, gravado["ifc_modificado_em"]),
                "elementos": gravado["elementos"],
                "ifc": gravado["ifc"], "ifc_modificado_em": gravado["ifc_modificado_em"]}

    caminho_do_ifc = Path(caminho_do_ifc or config.MODELOS[nome_do_modelo])
    versao = data_do_arquivo(caminho_do_ifc)
    # Gravado a partir da pasta do TFM ("04 EST\1 MODELO\..."), como no
    # quantitativo: o elementos_*.json e publicado, e o caminho completo
    # (C:\Users\...) e so deste computador.
    caminho_no_tfm = str(caminho_do_ifc.relative_to(config.PASTA_TFM))

    # ---- ja existe e e do mesmo IFC (mesmo arquivo, mesma data)? ----
    if arquivo_da_malha.exists() and arquivo_dos_elementos.exists():
        with open(arquivo_dos_elementos, encoding="utf-8") as arquivo:
            gravado = json.load(arquivo)
        if (gravado.get("ifc_caminho") == caminho_no_tfm
                and gravado.get("ifc_modificado_em") == versao):
            return {"url": url_da_malha(nome_do_modelo, versao),
                    "elementos": gravado["elementos"],
                    "ifc": str(caminho_do_ifc), "ifc_modificado_em": versao}

    # ---- gerar ----
    print(f"preparando malha 3D do modelo {nome_do_modelo} ({caminho_do_ifc.name})...")
    arquivo_ifc = ifcopenshell.open(str(caminho_do_ifc))
    traducao = config.PAVIMENTOS[nome_do_modelo]

    # Aberturas (vaos recortados nas paredes) nao sao pecas: ficam de fora.
    pecas_ifc = [elemento for elemento in arquivo_ifc.by_type("IfcElement")
                 if not elemento.is_a("IfcFeatureElement")]

    elementos = {}
    for elemento_ifc in pecas_ifc:
        parametros = ler_parametros(elemento_ifc)
        elementos[elemento_ifc.GlobalId] = {
            "nome": parametros.get("TQS_Padrao.Titulo") or elemento_ifc.Name,
            "classe": elemento_ifc.is_a(),
            "pavimento": pavimento_do_elemento(elemento_ifc, traducao),
            "tem_geometria": False,
            "parametros": parametros,
        }

    configuracao = ifcopenshell.geom.settings()
    configuracao.set("use-world-coords", True)  # cotas reais do predio

    pecas_com_forma = []
    iterador = ifcopenshell.geom.iterator(
        configuracao, arquivo_ifc, multiprocessing.cpu_count(), include=pecas_ifc)
    if iterador.initialize():
        while True:
            forma = iterador.get()
            vertices = np.array(forma.geometry.verts, dtype=np.float64).reshape(-1, 3)
            triangulos = np.array(forma.geometry.faces, dtype=np.int64)
            if len(triangulos):
                pecas_com_forma.append({
                    "global_id": forma.guid,
                    "pavimento": elementos[forma.guid]["pavimento"],
                    "vertices": vertices,
                    "triangulos": triangulos,
                })
                elementos[forma.guid]["tem_geometria"] = True
            if not iterador.next():
                break

    PASTA_MALHAS.mkdir(parents=True, exist_ok=True)
    gravar_glb(pecas_com_forma, arquivo_da_malha)
    with open(arquivo_dos_elementos, "w", encoding="utf-8") as arquivo:
        json.dump({"modelo": nome_do_modelo,
                   "ifc": caminho_do_ifc.name,
                   "ifc_caminho": caminho_no_tfm,
                   "ifc_modificado_em": versao,
                   "gerado_em": datetime.now().strftime("%Y-%m-%d %H%M"),
                   "elementos": elementos},
                  arquivo, ensure_ascii=False, default=str)

    tamanho = arquivo_da_malha.stat().st_size / 1e6
    print(f"  {len(pecas_com_forma)} elementos com geometria, de {len(pecas_ifc)} pecas"
          f" · malha {tamanho:.1f} MB")
    return {"url": url_da_malha(nome_do_modelo, versao), "elementos": elementos,
            "ifc": str(caminho_do_ifc), "ifc_modificado_em": versao}


if __name__ == "__main__":
    nomes = sys.argv[1:] or list(config.MODELOS)
    for nome in nomes:
        resultado = preparar_malha(nome)
        print(f"{nome}: pronto ({len(resultado['elementos'])} elementos) -> {resultado['url']}")
