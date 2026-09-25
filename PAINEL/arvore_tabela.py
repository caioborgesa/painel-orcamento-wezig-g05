# =============================================================
# ARVORE-TABELA — uma tabela que abre e fecha os niveis
# =============================================================
#
# O QUE ESTE ARQUIVO FAZ
#   E a mesma ideia da arvore da EAP (arvore_eap.py), mas generica e so
#   para leitura: recebe colunas e nos prontos e desenha uma tabela em
#   arvore, com seta para abrir e fechar cada nivel e os botoes
#   "Abrir tudo" e "Fechar tudo".
#
#   Serve aos relatorios: no Sintetico os niveis sao a EAP
#   (macro > grupo > item > servico); no Analitico sao a composicao e
#   os itens dela.
#
# POR QUE NAO REAPROVEITAR A arvore_eap.py
#   Aquela carrega o comportamento de ESCOLHA da auditoria: clicar numa
#   linha manda a REFERENCIA para o Python, clicar de novo desmarca, um
#   ramo destaca elementos no 3D. Aqui nada disso existe — so abre e
#   fecha. Misturar as duas coisas num arquivo so deixaria os dois usos
#   mais dificeis de ler.
#
# COMO SE USA
#   arvore_tabela(
#       colunas=[{"nome": "Item", "largura": "7.5rem"},
#                {"nome": "Descricao", "largura": "minmax(0, 1fr)"},
#                {"nome": "Total", "largura": "8rem", "alinhar": "direita"}],
#       nos=[{"id": "1", "pai": None, "nivel": 1, "folha": False,
#             "celulas": ["1", "CANTEIRO DE OBRAS", "R$ 4.815,60"]}],
#       altura=620, abrir_ate=1, key="sintetico")
#
#   Os valores das celulas ja vem formatados (texto). O componente nao
#   faz conta nem formata numero — quem faz isso e o relatorio.
# =============================================================

import streamlit as st

HTML = """
<div class="caixa-arvore">
  <div class="barra">
    <button class="botao abrir-tudo" type="button">Abrir tudo</button>
    <button class="botao fechar-tudo" type="button">Fechar tudo</button>
    <span class="dica">seta ou nome do nivel: abrir e fechar</span>
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
.dica { font-size: 0.75rem; opacity: 0.6; }
.arvore {
  overflow: auto;
  border: 1px solid var(--st-border-color, #d5d8de);
  border-radius: 0.5rem;
}
.linha {
  display: grid;
  align-items: center;
  column-gap: 0.5rem;
  padding: 0.18rem 0.5rem;
  border-bottom: 1px solid var(--st-border-color, #eceef1);
  white-space: nowrap;
}
.linha.ramo { cursor: pointer; }
.linha.ramo:hover { background: var(--st-secondary-background-color, #f0f2f6); }
.cabecalho {
  position: sticky;
  top: 0;
  z-index: 1;
  cursor: default;
  font-weight: 600;
  background: var(--st-secondary-background-color, #f0f2f6);
}
/* quanto mais alto o nivel, mais forte o texto */
.nivel-1 { font-weight: 600; }
.nivel-2 { font-weight: 500; }
.seta { text-align: center; opacity: 0.7; user-select: none; }
.seta:hover { opacity: 1; }
.celula { overflow: hidden; text-overflow: ellipsis; }
.direita { text-align: right; font-variant-numeric: tabular-nums; }
.apagado { opacity: 0.55; }
.destaque { color: #e03131; }
.vazia { padding: 1rem; opacity: 0.7; }
"""

JS = """
// Quais niveis estao abertos fica guardado no navegador: abrir e fechar
// e instantaneo e nao recarrega o app.
const estados = new WeakMap()

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]))
}

function desenhar(estado) {
  const { nos, colunas, raiz } = estado
  const porId = new Map(nos.map((no) => [no.id, no]))

  // Um no aparece se todos os niveis acima dele estiverem abertos
  const visivel = (no) => {
    let pai = no.pai
    while (pai) {
      if (!estado.abertos.has(pai)) return false
      pai = porId.get(pai)?.pai
    }
    return true
  }

  const grade = "1.4rem " + colunas.map((c) => c.largura || "8rem").join(" ")
  const cabecalho = colunas
    .map((c) => `<span class="celula ${c.alinhar === "direita" ? "direita" : ""}">${escapar(c.nome)}</span>`)
    .join("")
  const partes = [
    `<div class="linha cabecalho" style="grid-template-columns: ${grade}"><span></span>${cabecalho}</div>`,
  ]

  for (const no of nos) {
    if (!visivel(no)) continue
    const recuo = 0.5 + (no.nivel - 1) * 1.1
    const estilo = `grid-template-columns: ${grade}; padding-left: ${recuo}rem`
    const seta = no.folha ? "" : (estado.abertos.has(no.id) ? "▾" : "▸")
    const celulas = no.celulas
      .map((valor, i) => {
        const coluna = colunas[i] || {}
        const classes = ["celula"]
        if (coluna.alinhar === "direita") classes.push("direita")
        if ((no.classes || {})[coluna.nome]) classes.push(no.classes[coluna.nome])
        return `<span class="${classes.join(" ")}" title="${escapar(valor)}">${escapar(valor)}</span>`
      })
      .join("")
    partes.push(
      `<div class="linha ${no.folha ? "folha" : "ramo"} nivel-${no.nivel}" ` +
      `data-id="${no.id}" style="${estilo}">` +
      `<span class="seta">${seta}</span>${celulas}</div>`)
  }
  if (nos.length === 0) partes.push('<div class="vazia">Nada a mostrar.</div>')
  raiz.innerHTML = partes.join("")
}

export default function (component) {
  const { data, parentElement } = component
  const dados = data || {}
  const raiz = parentElement.querySelector(".arvore")
  raiz.style.maxHeight = `${dados.altura || 620}px`
  raiz.dataset.qual = dados.qual || ""

  let estado = estados.get(parentElement)
  if (!estado) {
    // Na primeira vez, abre ate o nivel pedido
    const ate = dados.abrir_ate ?? 1
    estado = {
      abertos: new Set((dados.nos || []).filter((no) => !no.folha && no.nivel <= ate).map((no) => no.id)),
      raiz,
    }
    estados.set(parentElement, estado)
  }
  estado.nos = dados.nos || []
  estado.colunas = dados.colunas || []
  estado.raiz = raiz
  desenhar(estado)

  raiz.onclick = (evento) => {
    const linha = evento.target.closest(".ramo[data-id]")
    if (!linha) return
    const id = linha.dataset.id
    if (estado.abertos.has(id)) estado.abertos.delete(id)
    else estado.abertos.add(id)
    desenhar(estado)
  }
  parentElement.querySelector(".abrir-tudo").onclick = () => {
    for (const no of estado.nos) if (!no.folha) estado.abertos.add(no.id)
    desenhar(estado)
  }
  parentElement.querySelector(".fechar-tudo").onclick = () => {
    estado.abertos.clear()
    desenhar(estado)
  }
}
"""

# Registrado uma vez so, quando o arquivo e importado
_ARVORE_TABELA = st.components.v2.component(
    "orcamento_arvore_tabela",
    html=HTML,
    css=CSS,
    js=JS,
)


def arvore_tabela(colunas, nos, *, altura=620, abrir_ate=1, key="arvore_tabela"):
    """Coloca a tabela em arvore na tela.

    colunas: [{"nome", "largura", "alinhar"}] — largura em CSS grid
             ("8rem", "minmax(0, 1fr)"...), alinhar="direita" para numero.
    nos:     [{"id", "pai", "nivel", "folha", "celulas": [...],
               "classes": {"<coluna>": "destaque"}}]
    abrir_ate: ate que nivel ja vem aberto na primeira vez.
    """
    return _ARVORE_TABELA(
        key=key,
        data={"colunas": colunas, "nos": nos, "altura": altura,
              "abrir_ate": abrir_ate, "qual": key},
    )
