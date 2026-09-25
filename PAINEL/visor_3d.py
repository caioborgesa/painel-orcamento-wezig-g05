# =============================================================
# VISOR 3D — componente do app de auditoria
# =============================================================
#
# O QUE ESTE ARQUIVO FAZ
#   Desenha JUNTOS os modelos medidos no quantitativo (ex.: EST + HID) e
#   destaca os elementos da linha ou do ramo escolhido. O resto fica
#   translucido, como contexto.
#
# COMO CONVERSA COM O PYTHON (Streamlit Custom Components v2)
#   Python -> navegador: a cada atualizacao do app, vai em `data`:
#       modelos          [{"nome": "EST", "url": malha}, ...] a carregar
#       modelos_visiveis nomes dos modelos ligados no 3D
#       destacados       GlobalIds que somaram (laranja)
#       destacados_zero  GlobalIds que entraram com valor zero (laranja claro)
#       selecionado      GlobalId escolhido (rosa)
#       pavimentos       pavimentos a mostrar (lista vazia = todos)
#       altura           altura do visor, em pixels
#   Navegador -> Python: ao clicar num elemento, o JavaScript avisa
#       setTriggerValue("elemento_clicado", GlobalId)
#
# CADA MODELO NO SEU LUGAR
#   Cada malha GLB foi gravada perto do zero, e guarda de quanto foi
#   deslocada ("origem_no_ifc"). O visor usa esse numero para devolver
#   cada modelo a posicao real do IFC — assim a tubulacao cai dentro da
#   estrutura, como nos modelos originais.
#
# O desenho usa a biblioteca three.js, baixada do CDN jsdelivr: precisa de
# internet ao abrir o app.
#
# A maior parte deste arquivo e JavaScript (o texto dentro de JS = """...""").
# Nao precisa ser mexido para usar o app.
# =============================================================

import streamlit as st

HTML = """
<div class="visor">
  <canvas class="tela"></canvas>
  <div class="legenda">Carregando o modelo 3D...</div>
  <div class="ajuda">arrastar: girar &middot; botao direito: mover &middot; roda: zoom &middot; clique: selecionar</div>
</div>
"""

CSS = """
.visor {
  position: relative;
  width: 100%;
  border-radius: 0.5rem;
  overflow: hidden;
  background: var(--st-secondary-background-color, #f0f2f6);
}
.tela {
  display: block;
  width: 100%;
  height: 100%;
}
.legenda, .ajuda {
  position: absolute;
  left: 0.75rem;
  font-size: 0.8rem;
  color: var(--st-text-color, #31333f);
  background: var(--st-background-color, #ffffff);
  opacity: 0.85;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  pointer-events: none;
}
.legenda { top: 0.5rem; }
.ajuda { bottom: 0.5rem; }
"""

JS = """
const THREE_URL = "https://cdn.jsdelivr.net/npm/three@0.186.0/+esm"
const CONTROLES_URL = "https://cdn.jsdelivr.net/npm/three@0.186.0/examples/jsm/controls/OrbitControls.js/+esm"
const GLTF_URL = "https://cdn.jsdelivr.net/npm/three@0.186.0/examples/jsm/loaders/GLTFLoader.js/+esm"

// Um visor por instancia do componente (a chave e o elemento onde ele mora)
const visores = new WeakMap()

async function criarVisor(parentElement) {
  const THREE = await import(THREE_URL)
  const { OrbitControls } = await import(CONTROLES_URL)
  const { GLTFLoader } = await import(GLTF_URL)

  const caixa = parentElement.querySelector(".visor")
  const tela = parentElement.querySelector(".tela")
  const legenda = parentElement.querySelector(".legenda")

  const renderer = new THREE.WebGLRenderer({ canvas: tela, antialias: true, alpha: true })
  renderer.setPixelRatio(window.devicePixelRatio)

  const cena = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000)
  // O GLB ja vem com o eixo Y para cima (padrao do three.js)
  cena.add(new THREE.AmbientLight(0xffffff, 0.8))
  const sol = new THREE.DirectionalLight(0xffffff, 1.4)
  sol.position.set(1, 3, 2)
  cena.add(sol)

  const controles = new OrbitControls(camera, tela)

  const materiais = {
    neutro: new THREE.MeshLambertMaterial({ color: 0xb8bec8 }),
    fundo: new THREE.MeshLambertMaterial({ color: 0xb8bec8, transparent: true, opacity: 0.08, depthWrite: false }),
    destacado: new THREE.MeshLambertMaterial({ color: 0xf08c00 }),
    zero: new THREE.MeshLambertMaterial({ color: 0xffc078, transparent: true, opacity: 0.55 }),
    selecionado: new THREE.MeshLambertMaterial({ color: 0xd6336c }),
  }

  const visor = {
    THREE, GLTFLoader, renderer, cena, camera, controles, materiais, legenda, caixa,
    modelos: new Map(),   // url -> {nome, cena, malhas}
    malhas: new Map(),    // GlobalId -> malha (de todos os modelos)
    referencia: null,     // origem do primeiro modelo carregado
    carga: Promise.resolve(),
    chaveDoDestaque: null, aoClicar: null, rodando: true,
  }

  visor.observador = new ResizeObserver(() => ajustarTamanho(visor))
  visor.observador.observe(caixa)

  // Clique sem arrastar = selecionar elemento
  let inicio = null
  tela.addEventListener("pointerdown", (e) => { inicio = [e.clientX, e.clientY] })
  tela.addEventListener("pointerup", (e) => {
    if (!inicio) return
    const arrastou = Math.hypot(e.clientX - inicio[0], e.clientY - inicio[1]) > 4
    inicio = null
    if (arrastou || !visor.aoClicar) return
    const id = elementoNoPonto(visor, e)
    if (id) visor.aoClicar(id)
  })

  const desenhar = () => {
    if (!visor.rodando) return
    controles.update()
    renderer.render(cena, camera)
    requestAnimationFrame(desenhar)
  }
  desenhar()
  return visor
}

function ajustarTamanho(visor) {
  const largura = visor.caixa.clientWidth
  const altura = visor.caixa.clientHeight
  if (!largura || !altura) return
  visor.renderer.setSize(largura, altura, false)
  visor.camera.aspect = largura / altura
  visor.camera.updateProjectionMatrix()
}

function elementoNoPonto(visor, evento) {
  const { THREE, camera, renderer, materiais } = visor
  const r = renderer.domElement.getBoundingClientRect()
  const ponto = new THREE.Vector2(
    ((evento.clientX - r.left) / r.width) * 2 - 1,
    -((evento.clientY - r.top) / r.height) * 2 + 1,
  )
  const raio = new THREE.Raycaster()
  raio.setFromCamera(ponto, camera)
  const todas = [...visor.malhas.values()].filter((m) => m.visible)
  // Primeiro tenta acertar os elementos em destaque; se nao, qualquer um
  const visiveis = todas.filter((m) => m.material !== materiais.fundo)
  const acerto = raio.intersectObjects(visiveis, false)[0] || raio.intersectObjects(todas, false)[0]
  return acerto ? acerto.object.userData.global_id : null
}

async function carregarModelo(visor, nome, url) {
  const gltf = await new visor.GLTFLoader().loadAsync(url)

  // Devolve o modelo a posicao real: diferenca entre a origem deste
  // modelo e a do primeiro carregado. No IFC o Z aponta para cima; no
  // three.js, o Y: (x, y, z) do IFC vira (x, z, -y).
  const raizDoModelo = gltf.scene.getObjectByName("modelo")
  const origem = (raizDoModelo && raizDoModelo.userData.origem_no_ifc) || [0, 0, 0]
  if (!visor.referencia) visor.referencia = origem
  const d = origem.map((valor, i) => valor - visor.referencia[i])
  gltf.scene.position.set(d[0], d[2], -d[1])

  const malhas = []
  gltf.scene.traverse((objeto) => {
    if (!objeto.isMesh) return
    objeto.geometry.computeVertexNormals() // para a luz sombrear as faces
    objeto.material = visor.materiais.neutro
    objeto.userData.modelo = nome
    malhas.push(objeto)
    visor.malhas.set(objeto.userData.global_id, objeto)
  })
  visor.cena.add(gltf.scene)
  return { nome, cena: gltf.scene, malhas }
}

function removerModelo(visor, url) {
  const modelo = visor.modelos.get(url)
  visor.cena.remove(modelo.cena)
  for (const malha of modelo.malhas) {
    malha.geometry.dispose()
    visor.malhas.delete(malha.userData.global_id)
  }
  visor.modelos.delete(url)
}

// Deixa carregados exatamente os modelos pedidos (carrega os novos,
// tira os que sairam). Roda um de cada vez, na fila visor.carga.
async function sincronizarModelos(visor, pedidos) {
  const urls = new Set(pedidos.map((m) => m.url))
  for (const url of [...visor.modelos.keys()]) {
    if (!urls.has(url)) removerModelo(visor, url)
  }
  for (const pedido of pedidos) {
    if (visor.modelos.has(pedido.url)) continue
    visor.legenda.textContent = `Carregando o modelo ${pedido.nome}...`
    visor.modelos.set(pedido.url, await carregarModelo(visor, pedido.nome, pedido.url))
    visor.chaveDoDestaque = null // reenquadra com o modelo novo
  }
}

function enquadrar(visor, malhas) {
  const { THREE, camera, controles } = visor
  const caixa = new THREE.Box3()
  for (const malha of malhas) caixa.expandByObject(malha)
  if (caixa.isEmpty()) return
  const centro = caixa.getCenter(new THREE.Vector3())
  const raio = caixa.getSize(new THREE.Vector3()).length() / 2 || 1
  const distancia = (raio / Math.sin((camera.fov * Math.PI) / 360)) * 0.9
  camera.position.set(centro.x + distancia * 0.55, centro.y + distancia * 0.45, centro.z + distancia * 0.7)
  camera.near = distancia / 200
  camera.far = distancia * 50
  camera.updateProjectionMatrix()
  controles.target.copy(centro)
  controles.update()
}

function aplicarDestaque(visor, data) {
  const destacados = new Set(data.destacados || [])
  const zeros = new Set(data.destacados_zero || [])
  const selecionado = data.selecionado || null
  const haDestaque = destacados.size > 0 || zeros.size > 0
  const pavimentos = new Set(data.pavimentos || []) // vazio = todos
  const modelosVisiveis = new Set(data.modelos_visiveis || [])
  const { materiais } = visor

  for (const [id, malha] of visor.malhas) {
    // Aparece se o modelo esta ligado e o pavimento passa no filtro.
    // Pecas sem pavimento aparecem sempre.
    const pavimento = malha.userData.pavimento
    malha.visible = modelosVisiveis.has(malha.userData.modelo)
      && (pavimentos.size === 0 || !pavimento || pavimentos.has(pavimento))

    if (id === selecionado) {
      malha.material = materiais.selecionado
      malha.renderOrder = 2
    } else if (destacados.has(id)) {
      malha.material = materiais.destacado
      malha.renderOrder = 1
    } else if (zeros.has(id)) {
      malha.material = materiais.zero
      malha.renderOrder = 1
    } else {
      malha.material = haDestaque ? materiais.fundo : materiais.neutro
      malha.renderOrder = 0
    }
  }

  // So reenquadra a camera quando o destaque, os pavimentos ou os modelos mudam
  const chave = [...destacados, ...zeros].sort().join("|") + "#" + [...pavimentos].sort().join("|")
    + "#" + [...modelosVisiveis].sort().join("|")
  if (chave !== visor.chaveDoDestaque) {
    const visiveis = [...visor.malhas].filter(([, malha]) => malha.visible)
    const alvo = visiveis
      .filter(([id]) => destacados.has(id) || zeros.has(id))
      .map(([, malha]) => malha)
    enquadrar(visor, alvo.length ? alvo : visiveis.map(([, malha]) => malha))
    visor.chaveDoDestaque = chave
  }

  const total = destacados.size + zeros.size
  const semGeometria = [...destacados, ...zeros].filter((id) => !visor.malhas.has(id)).length
  const visiveis = [...visor.malhas.values()].filter((m) => m.visible).length
  const nomes = [...visor.modelos.values()].map((m) => m.nome)
    .filter((nome) => modelosVisiveis.has(nome)).join(" + ") || "nenhum modelo ligado"
  let texto = haDestaque ? `${total} elementos destacados` : `${visiveis} elementos`
  if (zeros.size) texto += ` (${zeros.size} com valor zero)`
  if (semGeometria) texto += ` · ${semGeometria} sem geometria`
  texto += ` · ${nomes}`
  visor.legenda.textContent = texto
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const dados = data || {}

  const caixa = parentElement.querySelector(".visor")
  if (caixa) caixa.style.height = `${dados.altura || 600}px`

  let registro = visores.get(parentElement)
  if (!registro) {
    registro = { promessa: criarVisor(parentElement) }
    visores.set(parentElement, registro)
  }

  registro.promessa
    .then(async (visor) => {
      visor.aoClicar = (id) => setTriggerValue("elemento_clicado", id)
      ajustarTamanho(visor)
      const pedidos = dados.modelos || []
      visor.carga = visor.carga.then(() => sincronizarModelos(visor, pedidos))
      await visor.carga
      aplicarDestaque(visor, dados)
    })
    .catch((erro) => {
      const legenda = parentElement.querySelector(".legenda")
      if (legenda) legenda.textContent = "Erro no visor 3D: " + erro.message
    })

  // Chamado quando o Streamlit retira o componente da tela
  return () => {
    registro.promessa.then((visor) => {
      visor.rodando = false
      visor.observador.disconnect()
      visor.renderer.dispose()
    })
    visores.delete(parentElement)
  }
}
"""

# Registrado uma vez so, quando o arquivo e importado
_VISOR = st.components.v2.component(
    "auditoria_visor_3d",
    html=HTML,
    css=CSS,
    js=JS,
)


def visor_3d(modelos, destacados, destacados_zero, selecionado, *,
             modelos_visiveis=None, pavimentos=None, altura=620,
             key="visor_3d", ao_clicar=None):
    """Coloca o visor 3D na tela.

    modelos: lista [{"nome": "EST", "url": endereco da malha}, ...].
    modelos_visiveis: nomes dos modelos ligados (None = todos).
    pavimentos: lista de pavimentos a mostrar (ex.: ["N02", "N03"]).
    Vazia ou None mostra todos.
    ao_clicar: funcao chamada quando um elemento e clicado. Dentro dela, o
    GlobalId clicado esta em st.session_state[key].elemento_clicado.
    """
    if modelos_visiveis is None:
        modelos_visiveis = [modelo["nome"] for modelo in modelos]
    return _VISOR(
        key=key,
        data={
            "modelos": modelos,
            "modelos_visiveis": list(modelos_visiveis),
            "destacados": destacados,
            "destacados_zero": destacados_zero,
            "selecionado": selecionado,
            "pavimentos": pavimentos or [],
            "altura": altura,
        },
        on_elemento_clicado_change=ao_clicar or (lambda: None),
    )
