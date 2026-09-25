# =============================================================
# ARVORE DA EAP — componente do app de auditoria
# =============================================================
#
# O QUE ESTE ARQUIVO FAZ
#   Mostra as linhas de quantitativo penduradas na EAP, em arvore:
#     macro-servico > grupo > item > linhas de servico
#   Cada nivel abre e fecha (seta), mostra quantas linhas ja tem medida e
#   quanto custa o ramo — a EAP virando orcamento na tela.
#
# COMO SE USA
#   - clicar na SETA abre ou fecha o nivel;
#   - clicar numa LINHA DE SERVICO escolhe a linha (detalhe + 3D);
#   - clicar no NOME de um nivel acima escolhe o ramo inteiro: o 3D destaca
#     os elementos de todas as linhas daquele ramo.
#
# COMO CONVERSA COM O PYTHON (Streamlit Custom Components v2)
#   Python -> navegador: `data` leva a lista de nos (ja filtrados), o que
#     esta escolhido e a altura.
#   Navegador -> Python: ao clicar, o JavaScript avisa
#       setTriggerValue("clicado", {"tipo": "linha" ou "ramo", "id": REFERENCIA})
#
#   Quais niveis estao abertos fica guardado so no navegador: assim abrir
#   e fechar e instantaneo e nao recarrega o app.
#
# A maior parte deste arquivo e HTML/CSS/JavaScript. A parte em Python
# (montar_nos) e a que organiza as linhas em arvore.
# =============================================================

import streamlit as st

# Status que contam como "linha com medida" na contagem dos niveis
STATUS_COM_MEDIDA = ("EXTRAIDO", "ARBITRADO", "VERIFICADO", "DIVERGENTE")


def montar_nos(linhas):
    """Organiza as linhas de servico em nos de arvore, na ordem da EAP.

    A REFERENCIA de uma linha de servico ja diz onde ela mora: tirando os
    3 ultimos digitos tem-se o item, tirando 6 o grupo e tirando 9 o macro.
      7001004001 -> item 7001004 -> grupo 7001 -> macro 7
    Devolve uma lista "achatada": cada no com o id, o id do pai, o nivel e
    o texto, e as linhas de servico com os dados das colunas.
    """
    nos = {}          # id -> no (niveis 1 a 3)
    ordem = []        # ids na ordem em que devem aparecer

    # Ordem da EAP: primeiro pelo tamanho da REFERENCIA, depois pelo texto.
    # Assim o macro 2 (2003001001) vem antes do 20 (20004001001) — em ordem
    # so de texto, "20..." viria antes de "2003...".
    for linha in sorted(linhas, key=lambda linha: (len(linha["referencia"]), linha["referencia"])):
        ref = linha["referencia"]
        caminho = [(ref[:-9], 1, linha["macro"]),
                   (ref[:-6], 2, linha["grupo"]),
                   (ref[:-3], 3, linha["item"])]
        pai = None
        for id_do_no, nivel, texto in caminho:
            if id_do_no not in nos:
                nos[id_do_no] = {"id": id_do_no, "pai": pai, "nivel": nivel,
                                 "texto": texto, "total": 0, "medidas": 0,
                                 "custo": 0.0, "sem_preco": 0}
                ordem.append(id_do_no)
            no = nos[id_do_no]
            no["total"] += 1
            if linha["status"] in STATUS_COM_MEDIDA:
                no["medidas"] += 1
            # O custo do ramo e a soma dos filhos: e assim que a EAP
            # inteira ganha preco sem ninguem somar nada a mao.
            no["custo"] += linha.get("custo_total") or 0.0
            if linha.get("status_preco") == "SEM PRECO":
                no["sem_preco"] += 1
            pai = id_do_no

        nos[ref] = {
            "id": ref, "pai": pai, "nivel": 4,
            "codigo": linha["codigo"], "texto": linha["descricao"],
            "origem": linha["origem"], "quantidade": linha["quantidade"],
            "unidade": linha["unidade"], "status": linha["status"],
            "custo": linha.get("custo_total"),
            "status_preco": linha.get("status_preco"),
        }
        ordem.append(ref)

    return [nos[id_do_no] for id_do_no in ordem]


HTML = """
<div class="caixa-arvore">
  <div class="barra">
    <button class="botao abrir-tudo" type="button">Abrir tudo</button>
    <button class="botao fechar-tudo" type="button">Fechar tudo</button>
    <button class="botao limpar" type="button">Limpar escolha</button>
    <span class="dica">seta: abrir/fechar &middot; nome do nivel: destacar o ramo no 3D &middot; linha: detalhe &middot; clicar de novo: desmarcar</span>
  </div>
  <div class="arvore"></div>
</div>
"""

CSS = """
.caixa-arvore {
  font-family: var(--st-font, sans-serif);
  font-size: 0.85rem;
  color: var(--st-text-color, #31333f);
}
.barra {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.4rem;
  flex-wrap: wrap;
}
.botao {
  font: inherit;
  font-size: 0.8rem;
  padding: 0.15rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--st-border-color, #d5d8de);
  background: var(--st-background-color, #fff);
  color: inherit;
  cursor: pointer;
}
.botao:hover { border-color: var(--st-primary-color, #ff4b4b); }
.dica { opacity: 0.6; font-size: 0.75rem; }
.arvore {
  overflow: auto;
  border: 1px solid var(--st-border-color, #d5d8de);
  border-radius: 0.5rem;
}
.linha {
  display: grid;
  grid-template-columns: 1.4rem 7.2rem minmax(0, 1fr) 6.5rem 6rem 2.6rem 8rem 8.4rem;
  align-items: center;
  column-gap: 0.5rem;
  padding: 0.18rem 0.5rem;
  border-bottom: 1px solid var(--st-border-color, #eceef1);
  cursor: pointer;
  white-space: nowrap;
}
.linha:hover { background: var(--st-secondary-background-color, #f0f2f6); }
.cabecalho {
  position: sticky;
  top: 0;
  z-index: 1;
  cursor: default;
  font-weight: 600;
  background: var(--st-secondary-background-color, #f0f2f6);
}
.ramo .texto { grid-column: 3 / 6; font-weight: 600; }
.nivel-2 .texto { font-weight: 500; }
.nivel-3 .texto { font-weight: 400; }
.contagem { font-size: 0.75rem; opacity: 0.7; text-align: right; }
.seta { text-align: center; opacity: 0.7; user-select: none; }
.seta:hover { opacity: 1; }
.ref { font-variant-numeric: tabular-nums; opacity: 0.8; }
.texto { overflow: hidden; text-overflow: ellipsis; }
.codigo { font-weight: 600; margin-right: 0.35rem; }
.origem { font-size: 0.75rem; opacity: 0.8; overflow: hidden; text-overflow: ellipsis; }
.qtde { text-align: right; font-variant-numeric: tabular-nums; }
.custo { text-align: right; font-variant-numeric: tabular-nums; }
.ramo .custo { font-weight: 600; }
/* custo que nao pode ser calculado: aparece marcado, nunca como zero */
.sem-preco { color: #e03131; opacity: 0.9; }
.status {
  font-size: 0.72rem;
  padding: 0.05rem 0.45rem;
  border-radius: 0.6rem;
  justify-self: start;
  background: rgba(128, 128, 128, 0.15);
}
.s-EXTRAIDO { background: rgba(28, 126, 214, 0.18); }
.s-VERIFICADO { background: rgba(47, 158, 68, 0.22); }
.s-ARBITRADO { background: rgba(132, 94, 247, 0.2); }
.s-DIVERGENTE, .s-REGRA-DESATUALIZADA { background: rgba(224, 49, 49, 0.2); }
.s-SEM-ELEMENTOS { background: rgba(245, 159, 0, 0.2); }
.s-NAO-ATENDE { background: rgba(247, 103, 7, 0.22); }
.escolhida {
  background: var(--st-secondary-background-color, #f0f2f6);
  box-shadow: inset 3px 0 0 var(--st-primary-color, #ff4b4b);
}
.vazia { padding: 1rem; opacity: 0.7; }
"""

JS = """
// Estado de cada arvore (quais niveis estao abertos), guardado no navegador
const estados = new WeakMap()

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]))
}

function numero(valor) {
  if (valor === null || valor === undefined) return "—"
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

function reais(valor) {
  if (!valor) return "—"
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function desenhar(estado) {
  const { nos, selecionado, raiz } = estado
  const porId = new Map(nos.map((no) => [no.id, no]))

  // Um no aparece se todos os niveis acima dele estiverem abertos
  const visivel = (no) => {
    let pai = no.pai
    while (pai) {
      if (!estado.abertos.has(pai)) return false
      pai = porId.get(pai).pai
    }
    return true
  }

  const partes = [
    '<div class="linha cabecalho"><span></span><span>Referencia</span><span>Servico</span>' +
    '<span>Origem</span><span class="qtde">Quantidade</span><span>Un.</span>' +
    '<span class="custo">Custo R$</span><span>Status</span></div>',
  ]
  for (const no of nos) {
    if (!visivel(no)) continue
    const recuo = `padding-left: ${0.5 + (no.nivel - 1) * 1.1}rem`
    const escolhida = no.id === selecionado ? " escolhida" : ""
    if (no.nivel < 4) {
      const seta = estado.abertos.has(no.id) ? "▾" : "▸"
      partes.push(
        `<div class="linha ramo nivel-${no.nivel}${escolhida}" data-id="${no.id}" data-tipo="ramo" style="${recuo}">` +
        `<span class="seta" data-seta="${no.id}">${seta}</span>` +
        `<span class="ref">${no.id}</span>` +
        `<span class="texto">${escapar(no.texto)}</span>` +
        `<span class="contagem">${no.medidas}/${no.total} medidas</span>` +
        `<span class="custo">${reais(no.custo)}</span>` +
        `<span>${no.sem_preco ? `<span class="status sem-preco">${no.sem_preco} sem preco</span>` : ""}</span></div>`)
    } else {
      const classeStatus = "s-" + String(no.status).replace(/ /g, "-")
      partes.push(
        `<div class="linha folha${escolhida}" data-id="${no.id}" data-tipo="linha" style="${recuo}">` +
        `<span></span>` +
        `<span class="ref">${no.id}</span>` +
        `<span class="texto" title="${escapar(no.codigo + " " + no.texto)}"><span class="codigo">${escapar(no.codigo)}</span>${escapar(no.texto)}</span>` +
        `<span class="origem">${escapar(no.origem)}</span>` +
        `<span class="qtde">${numero(no.quantidade)}</span>` +
        `<span>${escapar(no.unidade)}</span>` +
        `<span class="custo${no.status_preco === "SEM PRECO" ? " sem-preco" : ""}">` +
        `${no.status_preco === "SEM PRECO" ? "sem preco" : reais(no.custo)}</span>` +
        `<span class="status ${classeStatus}">${escapar(no.status)}</span></div>`)
    }
  }
  if (nos.length === 0) partes.push('<div class="vazia">Nenhuma linha passa pelos filtros.</div>')
  raiz.innerHTML = partes.join("")
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const dados = data || {}
  const raiz = parentElement.querySelector(".arvore")
  raiz.style.maxHeight = `${dados.altura || 460}px`

  let estado = estados.get(parentElement)
  if (!estado) {
    // Na primeira vez a arvore vem toda recolhida: a tela abre mostrando
    // os macro-servicos e o custo de cada um, e o Caio desce so no que
    // quiser olhar. Antes ela abria o primeiro nivel e a lista ja nascia
    // com mais de cem linhas.
    estado = { abertos: new Set(), raiz }
    estados.set(parentElement, estado)
  }
  estado.nos = dados.nos || []
  estado.selecionado = dados.selecionado || null
  estado.raiz = raiz

  // Quando a escolha muda, abre os niveis acima dela (para ficar a vista).
  // So na mudanca: se depois o usuario fechar o nivel, ele fica fechado.
  if (estado.selecionado && estado.selecionado !== estado.ultimaEscolha) {
    estado.ultimaEscolha = estado.selecionado
    const porId = new Map(estado.nos.map((no) => [no.id, no]))
    let pai = porId.get(estado.selecionado)?.pai
    while (pai) { estado.abertos.add(pai); pai = porId.get(pai)?.pai }
  }

  desenhar(estado)

  // Cliques (atribuidos com "on...=" para nao acumular a cada atualizacao)
  raiz.onclick = (evento) => {
    const seta = evento.target.closest("[data-seta]")
    if (seta) {
      const id = seta.dataset.seta
      if (estado.abertos.has(id)) estado.abertos.delete(id)
      else estado.abertos.add(id)
      desenhar(estado)
      return
    }
    const linha = evento.target.closest("[data-id]")
    if (!linha) return
    // clicar no que ja estava escolhido = desmarcar
    if (linha.dataset.id === estado.selecionado) {
      estado.selecionado = null
      estado.ultimaEscolha = null
      desenhar(estado)
      setTriggerValue("clicado", { tipo: "nenhum", id: null })
      return
    }
    if (linha.dataset.tipo === "ramo") estado.abertos.add(linha.dataset.id)
    estado.selecionado = linha.dataset.id
    desenhar(estado)
    setTriggerValue("clicado", { tipo: linha.dataset.tipo, id: linha.dataset.id })
  }
  parentElement.querySelector(".abrir-tudo").onclick = () => {
    for (const no of estado.nos) if (no.nivel < 4) estado.abertos.add(no.id)
    desenhar(estado)
  }
  parentElement.querySelector(".limpar").onclick = () => {
    estado.selecionado = null
    estado.ultimaEscolha = null
    desenhar(estado)
    setTriggerValue("clicado", { tipo: "nenhum", id: null })
  }
  parentElement.querySelector(".fechar-tudo").onclick = () => {
    estado.abertos.clear()
    desenhar(estado)
  }
}
"""

# Registrado uma vez so, quando o arquivo e importado
_ARVORE = st.components.v2.component(
    "auditoria_arvore_eap",
    html=HTML,
    css=CSS,
    js=JS,
)


def arvore_eap(linhas, selecionado, *, altura=460, key="arvore_eap", ao_clicar=None):
    """Coloca a arvore da EAP na tela.

    linhas: as linhas de quantitativo que passaram pelos filtros.
    selecionado: REFERENCIA da linha ou do ramo escolhido (ou None).
    ao_clicar: funcao chamada no clique. Dentro dela, o que foi clicado
    esta em st.session_state[key].clicado -> {"tipo": ..., "id": ...}.
    """
    return _ARVORE(
        key=key,
        data={"nos": montar_nos(linhas), "selecionado": selecionado, "altura": altura},
        on_clicado_change=ao_clicar or (lambda: None),
    )
