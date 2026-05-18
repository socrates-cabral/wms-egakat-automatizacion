{{
(() => {
  const rawMsg =
    $('Limpiar mensaje').item.json.mensaje_limpio ||
    $('Limpiar mensaje').item.json.mensaje ||
    $('Telegram Trigger').item.json.message?.text ||
    '';

  const msg = String(rawMsg).toLowerCase();

  const kpi = $json.kpi_ops || {};
  const prod = kpi.productividad || {};
  const nnss = kpi.nnss || {};

  /*
    Límite operativo para Telegram:
    No enviar 90/125 pedidos en un solo mensaje. Telegram puede rechazar
    la respuesta por largo del texto en el nodo "Enviar Respuesta".
    Este contexto entrega un corte ejecutivo y conserva el total disponible.
  */
  const MAX_LISTADO_TELEGRAM = 15;

  function normText(s) {
    return String(s || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toUpperCase()
      .trim();
  }

  function fmtDateISOFromMsg(text) {
    const m = String(text).match(/(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?/);
    if (!m) return null;

    const dd = String(m[1]).padStart(2, '0');
    const mm = String(m[2]).padStart(2, '0');

    let yyyy = null;

    if (m[3]) {
      yyyy = String(m[3]);
      if (yyyy.length === 2) yyyy = `20${yyyy}`;
    } else {
      yyyy =
        prod?.diario?.periodo?.anio ||
        prod?.global?.periodo?.anio ||
        prod?.periodo?.anio ||
        nnss?.periodo?.anio ||
        '2026';
    }

    return `${yyyy}-${mm}-${dd}`;
  }

  function clienteFromMsg(text) {
    const t = normText(text);

    if (t.includes('GRUPO PLANET') || t.includes('PLANET') || t.includes('DERCO')) return 'DERCO';
    if (t.includes('UNILEVER')) return 'UNILEVER';
    if (t.includes('DAIKIN')) return 'DAIKIN';
    if (t.includes('BARENTZ')) return 'BARENTZ';
    if (t.includes('POCHTECA')) return 'POCHTECA';
    if (t.includes('MASCOTAS')) return 'MASCOTAS LATINAS';
    if (t.includes('RUNO')) return 'RUNO SPA';
    if (t.includes('NATIVO')) return 'NATIVO DRINKS SPA';
    if (t.includes('INTIME')) return 'INTIME';

    return null;
  }

  function normalizarRegistroFechaCliente(x) {
    const pedidosUnicosFecha =
      x.pedidos_unicos_fecha ??
      x.pedidos ??
      x.total_pedidos ??
      null;

    return {
      fecha: x.fecha,
      cliente: x.cliente,
      cd: x.cd,
      lineas: x.lineas,
      unidades: x.unidades,
      pedidos: pedidosUnicosFecha,
      pedidos_unicos_fecha: pedidosUnicosFecha,
      pedidos_tipo: 'pedidos_unicos_fecha',
      nota_pedidos: 'Pedidos corresponde a pedidos únicos del cliente en la fecha consultada, no a cantidad de registros/SKUs.'
    };
  }

  const fechaISO = fmtDateISOFromMsg(msg);
  const clienteSolicitado = clienteFromMsg(msg);

  // Condiciones base de productividad (palabras de dominio WMS)
  const esProductividadBase =
    msg.includes('productividad') ||
    msg.includes('lineas') ||
    msg.includes('líneas') ||
    msg.includes('unidades preparadas') ||
    msg.includes('preparo') ||
    msg.includes('preparó') ||
    msg.includes('preparadas') ||
    msg.includes('ap rack') ||
    msg.includes('ap estanteria') ||
    msg.includes('ap estantería') ||
    (msg.includes('rack') && msg.includes('estanteria')) ||
    (msg.includes('rack') && msg.includes('estantería'));

  // Leer datos de usuarios disponibles para detección dinámica (antes de esProductividad)
  const _porUsuarioMensualGlobal = Array.isArray(kpi.historico?.productividad?.por_usuario_mensual)
    ? kpi.historico.productividad.por_usuario_mensual
    : [];
  // DEBE declararse aquí (antes de cualquier bloque if) para evitar TDZ al usarse
  // dentro del bloque else de esConsultaCanal (línea ~1219).
  const _porUsuarioClienteMensualGlobal = Array.isArray(kpi.historico?.productividad?.por_usuario_cliente_mensual)
    ? kpi.historico.productividad.por_usuario_cliente_mensual
    : [];
  const _usuariosDisponibles = [
    ...new Set(_porUsuarioMensualGlobal.map(x => (x.usuario || '').toUpperCase().trim()).filter(Boolean))
  ];
  const _msgUpper = rawMsg.toUpperCase();
  const usuarioDetectado = _usuariosDisponibles.find(u => u && _msgUpper.includes(u)) || null;

  // Consulta de operador/usuario: se activa aunque no diga "productividad" ni "líneas"
  const esConsultaUsuarioOperador =
    usuarioDetectado !== null ||
    msg.includes('usuario') ||
    msg.includes('usuarios') ||
    msg.includes('operario') ||
    msg.includes('operarios') ||
    msg.includes('operador') ||
    msg.includes('operadores') ||
    msg.includes('trabajador') ||
    msg.includes('trabajadores') ||
    msg.includes('registró') ||
    msg.includes('registro') ||
    msg.includes('ranking') ||
    msg.includes('top operador') ||
    msg.includes('top operadores') ||
    msg.includes('por persona') ||
    msg.includes('por operador') ||
    msg.includes('quien preparo') ||
    msg.includes('quién preparó') ||
    msg.includes('quien preparó') ||
    msg.includes('quién preparo') ||
    msg.includes('mas productivo') ||
    msg.includes('más productivo') ||
    msg.includes('mejor operador') ||
    msg.includes('mayor eficiencia') ||
    msg.includes('eficiencia') ||
    msg.includes('lineas por hora') ||
    msg.includes('líneas por hora');

  // esProductividad se activa por dominio WMS o por consulta de operador
  const esProductividad = esProductividadBase || esConsultaUsuarioOperador;

  // esUsuario ya no depende de esProductividad; se activa solo con señales de operador
  const esUsuario = esConsultaUsuarioOperador;

  // Detecta intención de "lista completa" — el usuario quiere TODOS los operadores,
  // no solo el top. Si está activo, el cap TOP_USUARIOS se desactiva.
  const pideListaCompletaUsuarios = esUsuario && (
    msg.includes('todos los usuarios') ||
    msg.includes('todos los operadores') ||
    msg.includes('todos los registros') ||
    msg.includes('lista completa') ||
    msg.includes('ranking completo') ||
    msg.includes('lista entera') ||
    msg.includes('sin limite') ||
    msg.includes('sin tope') ||
    msg.includes('no top') ||
    msg.includes('ranking total')
  );

  // Detectar si pide "más productivo" (criterio eficiencia) vs ranking por volumen
  const esMasProductivo =
    esUsuario && (
      msg.includes('mas productivo') ||
      msg.includes('más productivo') ||
      msg.includes('mejor operador') ||
      msg.includes('mayor eficiencia') ||
      msg.includes('eficiencia') ||
      msg.includes('lineas por hora') ||
      msg.includes('líneas por hora')
    );

  const esOTIF =
    msg.includes('otif') ||
    msg.includes('in full') ||
    msg.includes('infull') ||
    msg.includes('on time') ||
    msg.includes('no evaluable') ||
    msg.includes('no evaluables') ||
    msg.includes('pendiente') ||
    msg.includes('pendientes') ||
    msg.includes('fuera del otif') ||
    msg.includes('sin entrega evaluable') ||
    msg.includes('lista de pedidos') ||
    msg.includes('listado de pedidos') ||
    msg.includes('estos pedidos');

  const pideListaPedidos =
    esOTIF &&
    (
      msg.includes('lista') ||
      msg.includes('listado') ||
      msg.includes('dame') ||
      msg.includes('mostrar') ||
      msg.includes('muéstrame') ||
      msg.includes('muestrame') ||
      msg.includes('cuáles') ||
      msg.includes('cuales') ||
      msg.includes('estos')
    );

  const pideTodosLosPedidos =
    pideListaPedidos &&
    (
      msg.includes('todos') ||
      msg.includes('toda') ||
      msg.includes('completa') ||
      msg.includes('completo') ||
      msg.includes('los 90') ||
      msg.includes('90 pedidos')
    );

  const pidePorClienteFecha =
    esProductividad &&
    fechaISO &&
    (
      msg.includes('por cliente') ||
      msg.includes('lineas por cliente') ||
      msg.includes('líneas por cliente') ||
      msg.includes('clientes')
    );

  const pideClienteSinFecha =
    esProductividad &&
    clienteSolicitado &&
    !fechaISO;

  const pideClienteConFecha =
    esProductividad &&
    clienteSolicitado &&
    fechaISO;

  const pideAP =
    msg.includes(' ap') ||
    msg.includes('ap ') ||
    msg.includes('rack') ||
    msg.includes('estanteria') ||
    msg.includes('estantería');

  const pideTurno =
    msg.includes('turno') ||
    msg.includes('a.m') ||
    msg.includes('p.m') ||
    msg.includes('pm') ||
    msg.includes('am');

  const pideCanal =
    msg.includes('canal') ||
    msg.includes('gt') ||
    msg.includes('cap') ||
    msg.includes('my') ||
    msg.includes('sg');

  // Detecta consulta de desglose por canal DERCO (AP/MY/SG/CAP/GT/CES).
  // Acepta tanto nombres específicos como referencias genéricas ("canal de derco",
  // "por tipo de canal" cuando el cliente solicitado es DERCO, etc.).
  const _DERCO_CANAL_KEYS = ['my', 'sg', 'cap', 'gt', 'ces'];
  const _dercoCanalesCount = _DERCO_CANAL_KEYS.filter(k => msg.includes(k)).length;
  const _mencionaDerco = msg.includes('derco') || msg.includes('planet');
  const _mencionaCanalGenerico = msg.includes('canal') || msg.includes('canales') ||
    msg.includes('tipo de canal') || msg.includes('por canal');
  const pideDercoCanales = _dercoCanalesCount >= 2 ||
    (msg.includes(' ap') && _dercoCanalesCount >= 1) ||
    msg.includes('ap rack') ||
    msg.includes('ap estanteria') ||
    msg.includes('ap estantería') ||
    (msg.includes('rack') && msg.includes('estanteria')) ||
    (msg.includes('rack') && msg.includes('estantería')) ||
    // Caso genérico: "canal/canales/por canal/tipo de canal" + DERCO mencionado
    (_mencionaCanalGenerico && _mencionaDerco);

  // Detecta intención de DESGLOSE INDIVIDUAL (canales_originales) vs AGRUPADO (canales).
  // Por default canales DERCO se entregan agrupados (AP / CAP-MY-SG-CES / GT). Con estas
  // keywords se prefiere la vista individual (AP, MY, CAP, SG, GT, CES separados).
  const pideDesgloseCanales = pideDercoCanales && (
    msg.includes('desglosa') ||
    msg.includes('desglose') ||
    msg.includes('desglosar') ||
    msg.includes('detalle') ||
    msg.includes('detallado') ||
    msg.includes('detallar') ||
    msg.includes('individual') ||
    msg.includes('individuales') ||
    msg.includes('originales') ||
    msg.includes('separado') ||
    msg.includes('separados') ||
    msg.includes('uno por uno') ||
    // Si menciona CES específicamente, también va a individual (CES solo está en originales)
    msg.includes('ces') ||
    // Si nombra 2+ canales específicos, claramente quiere individual
    _dercoCanalesCount >= 2
  );

  const esInventario =
    msg.includes('inventario') ||
    msg.includes('ubicacion') ||
    msg.includes('ubicación') ||
    msg.includes('ubicaciones') ||
    msg.includes('ocupacion') ||
    msg.includes('ocupación') ||
    msg.includes('layout') ||
    msg.includes('rack') ||
    msg.includes('estanteria') ||
    msg.includes('estantería') ||
    msg.includes('piso') ||
    msg.includes('libres') ||
    msg.includes('ocupadas') ||
    msg.includes('sd');

  const pideListadoCodigosUbicacion =
    esInventario &&
    (
      msg.includes('cuales son las ubicaciones') ||
      msg.includes('cuáles son las ubicaciones') ||
      msg.includes('lista de ubicaciones') ||
      msg.includes('listado de ubicaciones') ||
      msg.includes('codigos de ubicacion') ||
      msg.includes('códigos de ubicación') ||
      msg.includes('nombres de ubicaciones') ||
      msg.includes('ubicaciones de piso') ||
      msg.includes('ubicaciones piso')
    );

  const esConsultaUbicacionesLayout =
    esInventario &&
    (
      msg.includes('tipo de ubicacion') ||
      msg.includes('tipo de ubicación') ||
      msg.includes('tipos de ubicacion') ||
      msg.includes('tipos de ubicación') ||
      msg.includes('que tipo de ubicaciones') ||
      msg.includes('qué tipo de ubicaciones') ||
      msg.includes('ubicaciones existen') ||
      msg.includes('layout') ||
      msg.includes('ocupacion') ||
      msg.includes('ocupación') ||
      msg.includes('libres') ||
      msg.includes('ocupadas') ||
      msg.includes('sd') ||
      pideListadoCodigosUbicacion
    );

  const esConsultaConteoCiclico =
    esInventario &&
    (
      msg.includes('conteo') ||
      msg.includes('conteos') ||
      msg.includes('contadas') ||
      msg.includes('contado') ||
      msg.includes('ira') ||
      msg.includes('ila') ||
      msg.includes('avance de conteo') ||
      msg.includes('diferencia') ||
      msg.includes('diferencias')
    );

  // ── DETECCIÓN RECEPCIONES INBOUND ─────────────────────────────────────
  const esRecepciones =
    msg.includes('recepcion') || msg.includes('recepciones') ||
    msg.includes('recepción') || msg.includes('recepciónes') ||
    msg.includes('recibida') || msg.includes('recibidas') ||
    msg.includes('recibido') || msg.includes('recibidos') ||
    msg.includes('recibio') || msg.includes('recibió') ||
    msg.includes('recibieron') || msg.includes('recibimos') ||
    msg.includes('recibe') || msg.includes('reciben') ||
    msg.includes('pallets recibidos') || msg.includes('pallet recibido') ||
    msg.includes('tpr') ||
    msg.includes('inbound') ||
    msg.includes('backlog') ||
    msg.includes('or abierta') || msg.includes('or abiertas') ||
    msg.includes('or sin cerrar') || msg.includes('or sin cierre') ||
    msg.includes('or pendiente') || msg.includes('or pendientes') ||
    msg.includes('cargas recibidas') || msg.includes('carga recibida') ||
    msg.includes('ingresos recibidos') || msg.includes('ingreso recibido') ||
    msg.includes('tiempo recepcion') || msg.includes('tiempo de recepcion') ||
    msg.includes('tiempo recepción') || msg.includes('tiempo de recepción') ||
    msg.includes('cuanto demora la recepcion') || msg.includes('cuánto demora la recepción');

  const pideBacklog = esRecepciones && (
    msg.includes('abierta') || msg.includes('abiertas') ||
    msg.includes('sin cerrar') || msg.includes('sin cierre') ||
    msg.includes('pendiente') || msg.includes('pendientes') ||
    msg.includes('backlog')
  );

  const pideOrigenRecep = esRecepciones && (
    msg.includes('origen') || msg.includes('proveedor') || msg.includes('proveedores') ||
    msg.includes('de donde') || msg.includes('de dónde') ||
    msg.includes('viene de') || msg.includes('vienen de')
  );

  const pidePorDiaRecep = esRecepciones && (
    msg.includes('por dia') || msg.includes('por día') ||
    msg.includes('diario') || msg.includes('diaria') ||
    msg.includes('que dia') || msg.includes('qué día') ||
    msg.includes('por fecha') ||
    msg.includes('dia pico') || msg.includes('día pico') ||
    msg.includes('dias pico') || msg.includes('días pico')
  );

  const pideTPR = esRecepciones && (
    msg.includes('tpr') ||
    msg.includes('tiempo recepcion') || msg.includes('tiempo de recepcion') ||
    msg.includes('tiempo recepción') || msg.includes('tiempo de recepción') ||
    msg.includes('cuanto demora') || msg.includes('cuánto demora') ||
    msg.includes('duracion recepcion') || msg.includes('duración recepción')
  );

  const pideComplejidadRecep = esRecepciones && (
    msg.includes('complejidad') || msg.includes('tamaño') ||
    msg.includes('grandes') || msg.includes('pequeñas') || msg.includes('pequenas') ||
    msg.includes('significativas') || msg.includes('simples')
  );

  const pideRankingRecep = esRecepciones && (
    msg.includes('ranking') || msg.includes('top') ||
    msg.includes('mas pallets') || msg.includes('más pallets') ||
    msg.includes('mas or') || msg.includes('más or') ||
    msg.includes('cual cliente') || msg.includes('cuál cliente') ||
    msg.includes('que cliente') || msg.includes('qué cliente')
  );

  // Pregunta sobre lo no-disponible: operario en recepciones, guardado, M3/KGs
  const pideOperarioRecep = esRecepciones && (
    msg.includes('operario') || msg.includes('operador') ||
    msg.includes('usuario') || msg.includes('trabajador')
  );
  const pideGuardado = esRecepciones && (
    msg.includes('guardado') || msg.includes('guardar')
  );
  const pideVolumenFisico = esRecepciones && (
    msg.includes(' m3') || msg.includes(' m³') ||
    msg.includes('metros cubicos') || msg.includes('metros cúbicos') ||
    msg.includes('kilos') || msg.includes(' kg') ||
    msg.includes('peso') || msg.includes('toneladas')
  );



  function cdFromMsg(text) {
    const t = normText(text);
    if (t.includes('QUILICURA')) return 'QUILICURA';
    if (t.includes('PUDAHUEL UNITARIO') || (t.includes('PUDAHUEL') && t.includes('UNITARIO'))) return 'PUDAHUEL UNITARIO';
    if (t.includes('PUDAHUEL')) return 'PUDAHUEL';
    if (t.includes('SANTA ROSA') || t.includes('STA ROSA') || t.includes('STA. ROSA')) return 'SANTA ROSA';
    return null;
  }

  function limpiarTipoUbicacion(tipo) {
    const raw = String(tipo ?? '').trim();
    const n = normText(raw);
    if (!raw || n === 'NAN' || n === 'NULL' || n === 'NONE' || n === 'SIN DATO') return 'Sin clasificar';
    return raw;
  }

  const cdSolicitado = cdFromMsg(msg);

  const MESES_ES = {
    enero: 1, ene: 1,
    febrero: 2, feb: 2,
    marzo: 3, mar: 3,
    abril: 4, abr: 4,
    mayo: 5, may: 5,
    junio: 6, jun: 6,
    julio: 7, jul: 7,
    agosto: 8, ago: 8,
    septiembre: 9, setiembre: 9, sep: 9, set: 9,
    octubre: 10, oct: 10,
    noviembre: 11, nov: 11,
    diciembre: 12, dic: 12
  };

  const MESES_NOMBRE = {
    1: 'enero',
    2: 'febrero',
    3: 'marzo',
    4: 'abril',
    5: 'mayo',
    6: 'junio',
    7: 'julio',
    8: 'agosto',
    9: 'septiembre',
    10: 'octubre',
    11: 'noviembre',
    12: 'diciembre'
  };

  function detectarPeriodoSolicitado(texto) {
    const original = String(texto || '');
    const t = original
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();

    const esYtd =
      t.includes('lo que va de ano') ||
      t.includes('en lo que va del ano') ||
      t.includes('acumulado anual') ||
      t.includes('acumulado del ano') ||
      t.includes('acumulado 202') ||
      t.includes('ytd') ||
      t.includes('year to date') ||
      t.includes('del ano') ||
      t.includes('anual');

    const esComparativo =
      t.includes('comparar') ||
      t.includes('comparacion') ||
      t.includes('versus') ||
      t.includes(' vs ') ||
      t.includes('evolucion') ||
      t.includes('tendencia') ||
      t.includes('mes a mes');

    let mes = null;
    let anio = null;

    for (const [nombre, numero] of Object.entries(MESES_ES)) {
      const re = new RegExp(`(^|\\s|de\\s|del\\s|-)${nombre}(\\s|$|-|\\d)`, 'i');
      if (re.test(t)) {
        mes = numero;
        break;
      }
    }

    const mesAnio = t.match(/\b(0?[1-9]|1[0-2])[\/\-](20\d{2})\b/);
    if (mesAnio) {
      mes = Number(mesAnio[1]);
      anio = Number(mesAnio[2]);
    }

    const anioMatch = t.match(/\b(20\d{2})\b/);
    if (anioMatch) {
      anio = Number(anioMatch[1]);
    }

    return {
      solicitado: Boolean(mes || anio || esYtd || esComparativo),
      mes,
      anio,
      es_ytd: esYtd,
      es_comparativo: esComparativo,
      mes_nombre: mes ? MESES_NOMBRE[mes] : null
    };
  }

  function periodoDisponibleDeBloque(nombreKpi, kpiOps) {
    const k = kpiOps || {};

    if (nombreKpi === 'otif' || nombreKpi === 'nnss' || nombreKpi === 'fillrate') {
      const p = kpi?.nnss?.periodo || kpi?.fillrate?.periodo;
      if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'kpi_ops.nnss.periodo' };
    }

    if (nombreKpi === 'productividad') {
      const p = kpi?.productividad?.diario?.periodo || kpi?.productividad?.global?.periodo || kpi?.productividad?.periodo;
      if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'kpi_ops.productividad.periodo' };
    }

    if (nombreKpi === 'inventario') {
      const p = kpi?.inventario?.conteos_ciclicos?.periodo || kpi?.inventario?.ira_ila?.periodo || kpi?.inventario?.avance_conteo?.periodo;
      if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'kpi_ops.inventario.periodo' };
    }

    const p =
      kpi?.nnss?.periodo ||
      kpi?.productividad?.diario?.periodo ||
      kpi?.productividad?.global?.periodo ||
      kpi?.inventario?.conteos_ciclicos?.periodo ||
      kpi?.inventario?.ira_ila?.periodo;

    if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'periodo_disponible_general' };

    return null;
  }

  function detectarKpiPrincipal(texto) {
    const t = String(texto || '').toLowerCase();
    if (t.includes('otif') || t.includes('on time') || t.includes('in full')) return 'otif';
    if (t.includes('fill rate') || t.includes('fillrate')) return 'fillrate';
    if (
      t.includes('productividad') || t.includes('lineas') || t.includes('líneas') ||
      t.includes('unidades preparadas') || t.includes('operador') || t.includes('operadores') ||
      t.includes('usuario') || t.includes('usuarios') || t.includes('ranking') ||
      t.includes('mas productivo') || t.includes('más productivo') ||
      t.includes('mejor operador') || t.includes('eficiencia')
    ) return 'productividad';
    if (t.includes('inventario') || t.includes('ubicacion') || t.includes('ubicación') || t.includes('ocupacion') || t.includes('ocupación') || t.includes('ira') || t.includes('ila')) return 'inventario';
    if (t.includes('nnss') || t.includes('pedido') || t.includes('pedidos')) return 'nnss';
    return 'general';
  }

  const periodoSolicitado = detectarPeriodoSolicitado(rawMsg);
  const kpiPrincipalSolicitado = detectarKpiPrincipal(rawMsg);
  const periodoDisponible = periodoDisponibleDeBloque(kpiPrincipalSolicitado, kpi);

  const periodoSolicitadoNoDisponible =
    periodoSolicitado.solicitado &&
    periodoDisponible &&
    !periodoSolicitado.es_ytd &&
    !periodoSolicitado.es_comparativo &&
    (
      (periodoSolicitado.mes && periodoSolicitado.mes !== periodoDisponible.mes) ||
      (periodoSolicitado.anio && periodoSolicitado.anio !== periodoDisponible.anio)
    );

  const solicitudYtdSinHistorico =
    periodoSolicitado.es_ytd &&
    !(
      kpi?.historico ||
      kpi?.kpi_historico ||
      kpi?.nnss?.otif_ytd ||
      kpi?.nnss?.historico ||
      kpi?.productividad?.ytd ||
      kpi?.productividad?.historico ||
      kpi?.inventario?.historico
    );

  const solicitudComparativaSinHistorico =
    periodoSolicitado.es_comparativo &&
    !(
      kpi?.historico ||
      kpi?.kpi_historico ||
      kpi?.nnss?.historico ||
      kpi?.productividad?.historico ||
      kpi?.inventario?.historico
    );

  let contexto = {
    disponible: $json.disponible,
    fecha_consulta: $json.fecha_consulta,
    alertas: $json.alertas,
    recomendaciones: $json.recomendaciones,
    pipeline: $json.pipeline,
    validacion: $json.validacion,
    kpi_ops: kpi
  };

  // ── Helpers de historico ─────────────────────────────────────────────────
  const maxContextLength = 20000;
  const principalClients = new Set(['DERCO', 'DAIKIN', 'POCHTECA', 'UNILEVER', 'BARENTZ', 'RUNO']);
  const normClienteHist = (v) => String(v || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim();
  const filtrarRows = (rows) => Array.isArray(rows)
    ? rows.filter(r => principalClients.has(normClienteHist(r?.cliente)))
    : rows;

  const tryAddTopLevel = (key, value) => {
    if (value === undefined) return false;
    const candidate = JSON.parse(JSON.stringify(contexto));
    candidate.kpi_ops[key] = value;
    if (JSON.stringify(candidate).length <= maxContextLength) {
      contexto.kpi_ops[key] = value;
      return true;
    }
    return false;
  };

  const historico = kpi.historico || null;

  const construirHistoricoCompacto = (filtrarClientes) => {
    if (!historico || typeof historico !== 'object') return null;
    const hn = historico.nnss || {};
    const hp = historico.productividad || {};
    return {
      disponible: historico.disponible,
      periodo_cobertura: historico.periodo_cobertura,
      criterio_historico: historico.criterio_historico,
      origen_historico: historico.origen_historico,
      fecha_generacion: historico.fecha_generacion,
      advertencia: historico.advertencia,
      corte_operativo_disponible: historico.corte_operativo_disponible,
      nnss: {
        otif_mensual:      filtrarClientes ? filtrarRows(hn.otif_mensual)      : hn.otif_mensual,
        otif_ytd:          filtrarClientes ? filtrarRows(hn.otif_ytd)          : hn.otif_ytd,
        fillrate_mensual:  filtrarClientes ? filtrarRows(hn.fillrate_mensual)  : hn.fillrate_mensual,
        fillrate_ytd:      filtrarClientes ? filtrarRows(hn.fillrate_ytd)      : hn.fillrate_ytd
      },
      productividad: {
        mensual_cliente:                  filtrarClientes ? filtrarRows(hp.mensual_cliente) : hp.mensual_cliente,
        ytd_cliente:                      filtrarClientes ? filtrarRows(hp.ytd_cliente)     : hp.ytd_cliente,
        derco_ap_mensual:                 hp.derco_ap_mensual,
        derco_ap_ytd:                     hp.derco_ap_ytd,
        por_usuario:                      hp.por_usuario,
        por_usuario_mensual:              hp.por_usuario_mensual,
        por_usuario_canal:                hp.por_usuario_canal,
        por_usuario_canal_mensual:        hp.por_usuario_canal_mensual,
        por_usuario_cliente:              hp.por_usuario_cliente,
        por_usuario_cliente_mensual:      hp.por_usuario_cliente_mensual,
        lineas_no_asignadas_por_canal_mes: hp.lineas_no_asignadas_por_canal_mes
      }
    };
  };

  if (historico === null) {
    contexto.kpi_ops.historico = null;
  } else {
    const hFull = construirHistoricoCompacto(false);
    if (!tryAddTopLevel('historico', hFull)) {
      tryAddTopLevel('historico', construirHistoricoCompacto(true));
    }
  }
  // ── Fin helpers de historico ──────────────────────────────────────────────

  function historicoTienePeriodo(kpiTipo, mes, anio, esYtd) {
    if (!historico || typeof historico !== 'object') return false;
    const hn = historico.nnss || {};
    const hp = historico.productividad || {};

    function rowMatch(r) {
      const rMes = r?.mes ?? r?.periodo_mes ?? r?.periodo?.mes ?? null;
      const rAnio = r?.anio ?? r?.periodo_anio ?? r?.periodo?.anio ?? null;
      const mesOk = !mes || (rMes !== null && rMes !== undefined && Number(rMes) === Number(mes));
      const anioOk = !anio || (rAnio !== null && rAnio !== undefined && Number(rAnio) === Number(anio));
      return mesOk && anioOk;
    }

    function arrTiene(arr) {
      if (!Array.isArray(arr) || arr.length === 0) return false;
      if (esYtd) {
        if (!anio) return true;
        return arr.some(r => {
          const rAnio = r?.anio ?? r?.periodo_anio ?? r?.periodo?.anio ?? null;
          return !rAnio || Number(rAnio) === Number(anio);
        });
      }
      return arr.some(rowMatch);
    }

    if (esYtd) {
      if (kpiTipo === 'otif' || kpiTipo === 'nnss') return arrTiene(hn.otif_ytd);
      if (kpiTipo === 'fillrate') return arrTiene(hn.fillrate_ytd);
      if (kpiTipo === 'productividad') return arrTiene(hp.ytd_cliente) || arrTiene(hp.derco_ap_ytd);
      return arrTiene(hn.otif_ytd) || arrTiene(hn.fillrate_ytd) || arrTiene(hp.ytd_cliente) || arrTiene(hp.derco_ap_ytd);
    }

    if (kpiTipo === 'otif' || kpiTipo === 'nnss') return arrTiene(hn.otif_mensual);
    if (kpiTipo === 'fillrate') return arrTiene(hn.fillrate_mensual);
    if (kpiTipo === 'productividad') return arrTiene(hp.mensual_cliente) || arrTiene(hp.derco_ap_mensual) || arrTiene(hp.derco_canales_mensual);
    return arrTiene(hn.otif_mensual) || arrTiene(hn.fillrate_mensual) || arrTiene(hp.mensual_cliente);
  }

  const historicoResponde = historicoTienePeriodo(
    kpiPrincipalSolicitado,
    periodoSolicitado.mes,
    periodoSolicitado.anio,
    periodoSolicitado.es_ytd
  );

  if ((periodoSolicitadoNoDisponible || solicitudYtdSinHistorico || solicitudComparativaSinHistorico) && !historicoResponde && !esUsuario && !esRecepciones) {
    const solicitadoTexto = periodoSolicitado.es_ytd
      ? 'acumulado anual / YTD'
      : periodoSolicitado.es_comparativo
        ? 'comparación entre períodos'
        : `${periodoSolicitado.mes_nombre || 'mes no especificado'} ${periodoSolicitado.anio || periodoDisponible?.anio || ''}`.trim();

    const disponibleTexto = periodoDisponible
      ? `${MESES_NOMBRE[periodoDisponible.mes]} ${periodoDisponible.anio}`
      : 'período no identificado en el contexto';

    contexto = {
      disponible: $json.disponible,
      fecha_consulta: $json.fecha_consulta,
      control_periodo: {
        bloqueo_periodo: true,
        kpi_solicitado: kpiPrincipalSolicitado,
        periodo_solicitado: {
          texto: solicitadoTexto,
          mes: periodoSolicitado.mes,
          anio: periodoSolicitado.anio,
          es_ytd: periodoSolicitado.es_ytd,
          es_comparativo: periodoSolicitado.es_comparativo
        },
        periodo_disponible: periodoDisponible,
        periodo_disponible_texto: disponibleTexto,
        regla: 'No usar datos del período disponible para responder un período distinto solicitado por el usuario. Si no existe histórico o YTD explícito, responder información no disponible.',
        respuesta_obligatoria: periodoSolicitado.es_ytd
          ? `No hay ${kpiPrincipalSolicitado.toUpperCase()} acumulado anual/YTD estructurado en el contexto actual. Actualmente solo está disponible ${disponibleTexto}. Para responder YTD se requiere histórico mensual o detalle acumulado.`
          : periodoSolicitado.es_comparativo
            ? `No hay histórico comparativo estructurado para ${kpiPrincipalSolicitado.toUpperCase()} en el contexto actual. Actualmente solo está disponible ${disponibleTexto}.`
            : `No hay ${kpiPrincipalSolicitado.toUpperCase()} estructurado para ${solicitadoTexto} dentro del contexto actual. El período disponible corresponde a ${disponibleTexto}. No se debe usar ${disponibleTexto} como si fuera ${solicitadoTexto}.`
      }
    };

    return JSON.stringify(contexto);
  }

  if ((periodoSolicitadoNoDisponible || periodoSolicitado.es_ytd || periodoSolicitado.es_comparativo) && historicoResponde && !esUsuario && !esRecepciones) {
    const historicoOut = {
      disponible: $json.disponible,
      fecha_consulta: $json.fecha_consulta,
      consulta_historico: {
        kpi: kpiPrincipalSolicitado,
        periodo_solicitado: periodoSolicitado.es_ytd
          ? 'ytd'
          : `${periodoSolicitado.mes_nombre || 'mes'} ${periodoSolicitado.anio || ''}`.trim(),
        es_ytd: periodoSolicitado.es_ytd,
        es_comparativo: periodoSolicitado.es_comparativo,
        mes: periodoSolicitado.mes,
        anio: periodoSolicitado.anio,
        cliente: clienteSolicitado,
        regla: 'Responder usando kpi_ops.historico. Para mensual, filtrar por kpi y periodo solicitado. Para YTD, usar la sección ytd correspondiente. No usar datos del período actual para responder períodos históricos.'
      },
      kpi_ops: {
        historico: contexto.kpi_ops.historico
      }
    };
    if (pideDercoCanales && !periodoSolicitado.es_ytd) {
      const canalMensual = Array.isArray(contexto.kpi_ops?.historico?.productividad?.derco_canales_mensual)
        ? contexto.kpi_ops.historico.productividad.derco_canales_mensual
        : [];
      const filtrado = canalMensual.filter(r =>
        (!periodoSolicitado.mes || Number(r.mes) === Number(periodoSolicitado.mes)) &&
        (!periodoSolicitado.anio || Number(r.anio) === Number(periodoSolicitado.anio))
      );
      historicoOut.derco_canales_historico = {
        periodo: `${periodoSolicitado.mes_nombre || 'mes'} ${periodoSolicitado.anio || ''}`.trim(),
        canales: filtrado,
        regla: 'Mostrar desglose líneas/unidades por canal DERCO desde derco_canales_historico.canales. Si CES aparece como canal, reportarlo (corresponde a MY con destino concesionario, mismo criterio que FillRate). La conclusión debe señalar el canal con mayor carga operativa del período.'
      };
    }
    // Safety net específico: historicoOut puede llegar a 700KB con todo el detalle mensual.
    // Si supera 30K chars, devolver solo metadata + consulta_historico + aviso de filtrado.
    const _hOut = JSON.stringify(historicoOut);
    if (_hOut.length > 30000) {
      return JSON.stringify({
        disponible: historicoOut.disponible,
        fecha_consulta: historicoOut.fecha_consulta,
        consulta_historico: historicoOut.consulta_historico,
        kpi_ops: {
          _aviso: 'Historico completo supera limite de tokens. Reformular consulta con cliente especifico (ej: Barentz) + KPI especifico (fillrate/otif/productividad) + mes (ej: abril) para filtrado dinamico.'
        }
      });
    }
    return _hOut;
  }

  if (esConsultaUbicacionesLayout && !esConsultaConteoCiclico && !esProductividad && !esOTIF) {
    const inv = kpi.inventario || {};
    const ocupacion = inv.ocupacion || {};
    const stock = inv.stock || {};

    const porCd = Array.isArray(ocupacion.por_cd) ? ocupacion.por_cd : [];
    const porLocacion = Array.isArray(ocupacion.por_locacion) ? ocupacion.por_locacion : [];
    const porTipoUbicacion = Array.isArray(ocupacion.por_tipo_ubicacion) ? ocupacion.por_tipo_ubicacion : [];

    const cdFiltro = cdSolicitado;

    const porCdFiltrado = (cdFiltro
      ? porCd.filter(x => normText(x.cd) === cdFiltro)
      : porCd
    ).map(x => {
      const ocupadas = Number(x.ocupadas || 0);
      const libres = Number(x.libres || 0);
      const sd = Number(x.sd || 0);
      const totalLayout = Number(x.total_ubicaciones_layout || 0);
      const totalOperativo = ocupadas + libres;

      return {
        cd: x.cd,
        total_operativo_actual: totalOperativo,
        ocupadas: x.ocupadas,
        libres: x.libres,
        sd_referencial: x.sd,
        total_layout_referencial: x.total_ubicaciones_layout,
        ocupacion_operativa_pct: x.ocupacion_operativa_pct ?? x.ocupacion_pct,
        ocupacion_tecnica_pct: x.ocupacion_tecnica_pct,
        nota_total_operativo: 'Total operativo actual = ocupadas + libres. Excluye SD referencial.',
        nota_sd: 'SD referencial existe en base/layout histórico, pero no forma parte del total operativo actual del WMS.'
      };
    });

    const porLocacionFiltrado = (cdFiltro
      ? porLocacion.filter(x => normText(x.cd) === cdFiltro)
      : porLocacion
    ).map(x => {
      const ocupadas = Number(x.ocupadas || 0);
      const libres = Number(x.libres || 0);
      const sd = Number(x.sd || 0);
      const totalLayout = Number(x.total || 0);
      const totalOperativo = ocupadas + libres;

      return {
        cd: x.cd,
        locacion: limpiarTipoUbicacion(x.locacion),
        total_operativo_actual: totalOperativo,
        ocupadas: x.ocupadas,
        libres: x.libres,
        sd_referencial: x.sd,
        total_layout_referencial: x.total,
        ocupacion_operativa_pct: totalOperativo > 0 ? Number(((ocupadas / totalOperativo) * 100).toFixed(2)) : 0,
        ocupacion_tecnica_pct: totalLayout > 0 ? Number(((ocupadas / totalLayout) * 100).toFixed(2)) : 0,
        nota_total_operativo: 'Total operativo actual = ocupadas + libres. Excluye SD referencial.',
        nota_sd: 'SD referencial existe en base/layout histórico, pero no forma parte del total operativo actual del WMS.'
      };
    });

    const porTipoFiltrado = (cdFiltro
      ? porTipoUbicacion.filter(x => normText(x.cd) === cdFiltro)
      : porTipoUbicacion
    )
      .map(x => {
        const ocupadas = Number(x.ocupadas || 0);
        const libres = Number(x.libres || 0);
        const sd = Number(x.sd || 0);
        const totalLayout = Number(x.total || 0);
        const totalOperativo = ocupadas + libres;

        const tipoLimpio = limpiarTipoUbicacion(x.tipo);
        const tipoNormalizado = normText(tipoLimpio);
        const esTipoSdOperativo = tipoNormalizado === 'SD';

        return {
          cd: x.cd,
          tipo: tipoLimpio,
          total_operativo_actual: totalOperativo,
          ocupadas: x.ocupadas,
          libres: x.libres,
          sd_referencial: x.sd,
          total_layout_referencial: x.total,
          ocupacion_operativa_pct: totalOperativo > 0 ? Number(((ocupadas / totalOperativo) * 100).toFixed(2)) : 0,
          ocupacion_tecnica_pct: totalLayout > 0 ? Number(((ocupadas / totalLayout) * 100).toFixed(2)) : 0,
          nota_total_operativo: 'Total operativo actual = ocupadas + libres. Excluye SD referencial.',
          nota_sd: esTipoSdOperativo
            ? 'Este registro aparece como tipo SD con libres operativas. Debe interpretarse como clasificación pendiente de revisión, no como SD referencial.'
            : 'SD referencial existe en base/layout histórico, pero no forma parte del total operativo actual del WMS.',
          tipo_sd_operativo_requiere_revision: esTipoSdOperativo
        };
      })
      .sort((a, b) => Number(b.total_operativo_actual || 0) - Number(a.total_operativo_actual || 0));

    const stockPorCd = Array.isArray(stock.por_cd)
      ? (cdFiltro ? stock.por_cd.filter(x => normText(x.cd) === cdFiltro) : stock.por_cd)
      : undefined;

    const inventarioCompacto = {
      consulta_resuelta: {
        tipo: pideListadoCodigosUbicacion ? 'listado_codigos_ubicacion_no_disponible_en_contexto' : 'ubicaciones_layout_ocupacion',
        cd: cdFiltro || 'TODOS',
        requiere_detalle_codigos_ubicacion: pideListadoCodigosUbicacion,
        regla: pideListadoCodigosUbicacion
          ? 'El usuario pide cuáles son las ubicaciones/códigos específicos. El contexto actual de inventario.ocupacion trae agregados por CD, locación y tipo, pero no trae el listado de códigos/nombres de ubicaciones. No inventar códigos. Responder el resumen disponible y aclarar que para listar códigos se debe incorporar detalle desde Consulta de Posiciones diaria WMS o Tabla Ubicaciones CDs.'
          : 'Usar exclusivamente inventario.ocupacion para responder tipos de ubicación, layout, ocupación, libres, ocupadas y SD. Usar total_operativo_actual como realidad actual del WMS; total_layout_referencial y SD referencial son solo referencia histórica/reconciliación. Si aparece SD como tipo de ubicación con libres operativas, tratarlo como clasificación pendiente de revisión, no como SD referencial. No usar conteos_ciclicos para esta consulta, porque conteos_ciclicos representa ubicaciones contadas, no ubicaciones existentes.'
      },
      fuente_correcta: 'inventario.ocupacion',
      fuente_operacional: 'Consulta de Posiciones diaria WMS + base/layout referencial Ubicaciones CDs',
      fuente_no_usar_para_esta_consulta: 'inventario.conteos_ciclicos',
      motivo_no_usar_conteos: 'Registros de conteo ciclico sirve para IRA, ILA, avance de conteo, ubicaciones contadas y diferencias; no para responder el universo de ubicaciones existentes.',
      detalle_codigos_ubicacion_disponible: false,
      nota_detalle_codigos: 'El contexto actual no incluye códigos/nombres individuales de ubicaciones; solo agregados por CD, locación y tipo.',
      fuente_para_detalle_codigos: 'Consulta de Posiciones diaria WMS o Tabla Ubicaciones CDs, si se incorpora el detalle al JSON/API.',
      ocupacion: {
        disponible: ocupacion.disponible,
        fecha_referencia: ocupacion.fecha_referencia,
        kpi_principal: ocupacion.kpi_principal,
        total_operativo_actual: Number(ocupacion.ocupadas || 0) + Number(ocupacion.libres || 0),
        total_layout_referencial: ocupacion.total_ubicaciones_layout,
        ocupadas: ocupacion.ocupadas,
        libres: ocupacion.libres,
        sd_referencial: ocupacion.sd,
        nota_total_operativo: 'Total operativo actual = ocupadas + libres. Excluye SD referencial.',
        nota_sd: 'SD referencial existe en base/layout histórico, pero no forma parte del total operativo actual del WMS.',
        sd_definicion: ocupacion.sd_definicion,
        ocupacion_pct: ocupacion.ocupacion_pct,
        ocupacion_tecnica: ocupacion.ocupacion_tecnica,
        ocupacion_operativa: ocupacion.ocupacion_operativa,
        por_cd: porCdFiltrado,
        por_locacion: porLocacionFiltrado,
        por_tipo_ubicacion: porTipoFiltrado,
        alertas: ocupacion.alertas,
        observaciones: ocupacion.observaciones
      },
      stock: stockPorCd ? {
        por_cd: stockPorCd
      } : undefined,
      regla_respuesta: [
        'Si el usuario pregunta que tipos de ubicaciones existen en un CD, responder desde ocupacion.por_locacion y ocupacion.por_tipo_ubicacion filtrado por CD.',
        'Usar total_operativo_actual como total real actual. No usar total_layout_referencial como total actual.',
        'SD referencial no pertenece al total operativo actual. SD referencial es solo referencia de ubicaciones existentes en base/layout historico, pero eliminadas del WMS actual por retiro fisico o desarme de racks.',
        'Cuando muestres una linea, usa formato: total operativo actual | ocupadas | libres. Si hay SD referencial, mencionarlo aparte como SD referencial.',
        'Si aparece un registro cuyo tipo es SD y tiene libres operativas, no lo confundas con SD referencial. Debe interpretarse como clasificacion pendiente de revision.',
        'En la nota, usar esta redaccion: SD referencial corresponde a ubicaciones fuera del WMS actual. Si aparece SD como tipo de ubicacion con libres operativas, debe interpretarse como clasificacion pendiente de revision, no como SD referencial.',
        'Para Pudahuel, si resumes tipos existentes, usar esta redaccion: En Pudahuel existen locaciones Rack, Rack Unitario y Piso, además de tipos Doble, Simple, Driving, SD pendiente de revisión y Sobredimensionado.',
        'Evitar palabras interpretativas como principalmente, predominan o concentrado en respuestas de inventario/ubicaciones.',
        'Si el usuario pregunta cuales son las ubicaciones especificas, codigos o nombres de ubicaciones, no inventar. El contexto actual solo trae resumen agregado por locacion/tipo; no trae codigos individuales. Responder que para listar codigos se debe incorporar detalle desde Consulta de Posiciones diaria WMS o Tabla Ubicaciones CDs.',
        'No mencionar registros de conteo ciclico ni ubicaciones contadas salvo que el usuario pregunte explicitamente por conteos, IRA, ILA o avance de conteo.',
        'No mostrar tipo nan; usar Sin clasificar.',
        'Mantener respuesta operacional, breve y con fuente clara.'
      ]
    };

    contexto = {
      disponible: $json.disponible,
      fecha_consulta: $json.fecha_consulta,
      kpi_ops: {
        inventario: inventarioCompacto
      }
    };
  }

  if (esProductividad) {
    const porFechaCliente = Array.isArray(prod.por_fecha_cliente) ? prod.por_fecha_cliente : [];
    const porFechaClienteCanal = Array.isArray(prod.por_fecha_cliente_canal) ? prod.por_fecha_cliente_canal : [];
    const porFechaClienteTurno = Array.isArray(prod.por_fecha_cliente_turno) ? prod.por_fecha_cliente_turno : [];
    const porClienteMensual = Array.isArray(prod.por_cliente) ? prod.por_cliente : [];
    const porUsuarioMensual = _porUsuarioMensualGlobal; // ya cargado arriba

    let prodCompacta = {
      disponible: prod.disponible,
      global: prod.global,
      diario: prod.diario ? {
        disponible: prod.diario.disponible,
        periodo: prod.diario.periodo,
        fecha_min: prod.diario.fecha_min,
        fecha_max: prod.diario.fecha_max,
        alertas: prod.diario.alertas
      } : undefined
    };

    if (pidePorClienteFecha) {
      const registrosFecha = porFechaCliente
        .filter(x => x.fecha === fechaISO)
        .sort((a, b) => Number(b.lineas || 0) - Number(a.lineas || 0))
        .map(normalizarRegistroFechaCliente);

      prodCompacta.consulta_resuelta = {
        tipo: 'fecha_todos_los_clientes',
        fecha: fechaISO,
        regla: 'Usar exclusivamente por_fecha_cliente_filtrado. No agregar clientes ausentes. No usar turnos, canales ni acumulados mensuales. El campo pedidos representa pedidos únicos del cliente en la fecha.'
      };

      prodCompacta.por_fecha_cliente_filtrado = registrosFecha;
    }

    if (pideClienteConFecha) {
      const registrosClienteFecha = porFechaCliente
        .filter(x => x.fecha === fechaISO && normText(x.cliente) === clienteSolicitado)
        .sort((a, b) => Number(b.lineas || 0) - Number(a.lineas || 0))
        .map(normalizarRegistroFechaCliente);

      prodCompacta.consulta_resuelta = {
        tipo: 'cliente_fecha',
        fecha: fechaISO,
        cliente: clienteSolicitado,
        regla: 'Usar exclusivamente por_fecha_cliente_filtrado para el total cliente-fecha. No usar turnos ni canales salvo que se pidan explícitamente. El campo pedidos representa pedidos únicos del cliente en la fecha.'
      };

      prodCompacta.por_fecha_cliente_filtrado = registrosClienteFecha;

      if (clienteSolicitado === 'DERCO') {
        prodCompacta.derco = {
          por_fecha: Array.isArray(prod?.derco?.por_fecha)
            ? prod.derco.por_fecha
                .filter(x => x.fecha === fechaISO)
                .map(x => ({
                  ...x,
                  pedidos: x.pedidos_unicos_fecha ?? x.pedidos ?? null,
                  pedidos_unicos_fecha: x.pedidos_unicos_fecha ?? x.pedidos ?? null,
                  pedidos_tipo: 'pedidos_unicos_fecha'
                }))
            : []
        };
      }
    }

    if (pideClienteSinFecha) {
      const registrosCliente = porFechaCliente
        .filter(x => normText(x.cliente) === clienteSolicitado)
        .sort((a, b) => String(a.fecha).localeCompare(String(b.fecha)))
        .map(normalizarRegistroFechaCliente);

      const totalLineas = registrosCliente.reduce((s, x) => s + Number(x.lineas || 0), 0);
      const totalUnidades = registrosCliente.reduce((s, x) => s + Number(x.unidades || 0), 0);

      const registrosMensualesCliente = porClienteMensual.filter(x =>
        normText(x.cliente) === clienteSolicitado
      );

      const pedidosUnicosPeriodo = registrosMensualesCliente.length > 0
        ? registrosMensualesCliente.reduce((s, x) => {
            const valor =
              x.pedidos_unicos_periodo ??
              x.pedidos ??
              x.total_pedidos ??
              x.pedidos_unicos ??
              0;
            return s + Number(valor || 0);
          }, 0)
        : null;

      prodCompacta.consulta_resuelta = {
        tipo: 'cliente_sin_fecha',
        cliente: clienteSolicitado,
        regla: 'Usar registros_cliente para líneas/unidades por fecha. Para pedidos del período usar exclusivamente pedidos_unicos_periodo desde productividad.por_cliente. No usar suma diaria como pedidos únicos. No inventar fechas. No usar alertas generales.'
      };

      prodCompacta.resumen_cliente = {
        cliente: clienteSolicitado,
        fechas_con_registro: registrosCliente.length,
        lineas_periodo: totalLineas,
        unidades_periodo: totalUnidades,
        pedidos_unicos_periodo: pedidosUnicosPeriodo,
        pedidos_tipo: 'pedidos_unicos_periodo',
        nota_pedidos: pedidosUnicosPeriodo === null
          ? 'No se encontró pedidos únicos del período en productividad.por_cliente.'
          : 'Pedidos únicos del período tomados desde productividad.por_cliente.'
      };

      prodCompacta.registros_cliente = registrosCliente;
      prodCompacta.ultimas_fechas_cliente = registrosCliente.slice(-10).reverse();
    }

    if (pideAP && fechaISO) {
      prodCompacta.derco = {
        ...(prodCompacta.derco || {}),
        ap_por_fecha: Array.isArray(prod?.derco?.ap_por_fecha)
          ? prod.derco.ap_por_fecha
              .filter(x => x.fecha === fechaISO)
              .map(x => ({
                fecha: x.fecha,
                ap_total: x.ap_total ? {
                  ...x.ap_total,
                  pedidos: x.ap_total.pedidos_unicos_fecha ?? x.ap_total.pedidos ?? null,
                  pedidos_unicos_fecha: x.ap_total.pedidos_unicos_fecha ?? x.ap_total.pedidos ?? null,
                  pedidos_tipo: 'pedidos_unicos_fecha'
                } : undefined,
                ap_rack: x.ap_rack ? {
                  ...x.ap_rack,
                  pedidos: x.ap_rack.pedidos_unicos_fecha ?? x.ap_rack.pedidos ?? null,
                  pedidos_unicos_fecha: x.ap_rack.pedidos_unicos_fecha ?? x.ap_rack.pedidos ?? null,
                  pedidos_tipo: 'pedidos_unicos_fecha'
                } : undefined,
                ap_estanteria: x.ap_estanteria ? {
                  ...x.ap_estanteria,
                  pedidos: x.ap_estanteria.pedidos_unicos_fecha ?? x.ap_estanteria.pedidos ?? null,
                  pedidos_unicos_fecha: x.ap_estanteria.pedidos_unicos_fecha ?? x.ap_estanteria.pedidos ?? null,
                  pedidos_tipo: 'pedidos_unicos_fecha'
                } : undefined,
                nota_pedidos: 'AP total no debe asumirse como suma de AP Rack + AP Estantería; cada bloque trae pedidos únicos de su propio universo.'
              }))
          : []
      };
    }

    if (pideDercoCanales) {
      // Cuando el usuario pide operarios × canal (esUsuario=true), NO agregar derco_canales
      // (totales por canal) porque el AI elige los totales e ignora por_usuario_canal.
      // El bloque por_usuario_canal (más abajo) maneja toda la respuesta en ese caso.
      if (!esUsuario) {
        prodCompacta.derco_canales = {
          canales: Array.isArray(prod?.derco?.canales) ? prod.derco.canales : [],
          canales_originales: Array.isArray(prod?.derco?.canales_originales) ? prod.derco.canales_originales : [],
          top_canal_por_lineas: prod?.derco?.top_canal_por_lineas || null,
          top_canal_por_unidades: prod?.derco?.top_canal_por_unidades || null,
          nota: 'canales agrupa AP_R+AP_E como AP y CAP+MY+SG+CES en CAP-MY-SG-CES (canal mayorista). canales_originales separa: AP, MY, CAP, SG, GT, CES (CES = MY con destino concesionario, parte del mayorista). Si CES aparece, reportarlo; si no aparece para el período, mencionar que no hubo pedidos CES en ese rango. La suma de los 4 individuales (CAP+MY+SG+CES) debe igualar el grupo CAP-MY-SG-CES.'
        };
        prodCompacta.consulta_resuelta = {
          tipo: pideDesgloseCanales ? 'derco_canales_individuales' : 'derco_canales_agrupados',
          cliente: 'DERCO',
          vista_preferida: pideDesgloseCanales ? 'canales_originales' : 'canales',
          regla: pideDesgloseCanales
            ? 'Vista INDIVIDUAL solicitada (palabra clave: desglosa/desglose/detalle/individual/originales/separado o se nombró CES o 2+ canales). Usar derco_canales.canales_originales (AP, MY, CAP, SG, GT, CES separados). NO agrupar CAP+MY+SG+CES. Si CES aparece, reportarlo; si no aparece para el período, mencionar que no hubo pedidos CES. La conclusión debe señalar qué canal individual concentra mayor carga operativa.'
            : 'Vista AGRUPADA por default. Usar derco_canales.canales (AP, CAP-MY-SG-CES, GT). El grupo CAP-MY-SG-CES contiene CAP+MY+SG+CES y representa el canal mayorista DERCO. Si el usuario después pide individual, usar canales_originales. La conclusión debe señalar qué grupo concentra mayor carga operativa.'
        };
      }
    }

    if (pideCanal && fechaISO) {
      prodCompacta.por_fecha_cliente_canal_filtrado = porFechaClienteCanal
        .filter(x => x.fecha === fechaISO && (!clienteSolicitado || normText(x.cliente) === clienteSolicitado))
        .map(x => ({
          ...x,
          pedidos: x.pedidos_unicos_fecha ?? x.pedidos ?? null,
          pedidos_unicos_fecha: x.pedidos_unicos_fecha ?? x.pedidos ?? null,
          pedidos_tipo: 'pedidos_unicos_fecha'
        }));
    }

    if (pideTurno && fechaISO) {
      prodCompacta.por_fecha_cliente_turno_filtrado = porFechaClienteTurno
        .filter(x => x.fecha === fechaISO && (!clienteSolicitado || normText(x.cliente) === clienteSolicitado))
        .map(x => ({
          ...x,
          pedidos: x.pedidos_unicos_fecha ?? x.pedidos ?? null,
          pedidos_unicos_fecha: x.pedidos_unicos_fecha ?? x.pedidos ?? null,
          pedidos_tipo: 'pedidos_unicos_fecha'
        }));
    }

    if (esUsuario && porUsuarioMensual.length > 0) {
      const TOP_USUARIOS = 25;

      // Determinar mes objetivo: el solicitado o el más reciente disponible
      const _mesesDisponibles = [...new Set(porUsuarioMensual.map(x => Number(x.mes)))].sort((a, b) => b - a);
      const mesObjetivo = periodoSolicitado.mes || _mesesDisponibles[0] || null;

      // Filtrar base: siempre por mes (solicitado o más reciente) — nunca mezclar meses
      let porUsuarioBase = mesObjetivo
        ? porUsuarioMensual.filter(x => Number(x.mes) === mesObjetivo)
        : porUsuarioMensual;

      // Filtrar por CD con coincidencia exacta: "PUDAHUEL" → "CD PUDAHUEL" únicamente.
      // No usar .includes() — evita que "PUDAHUEL" coincida con "CD PUDAHUEL UNITARIO".
      if (cdSolicitado) {
        const cdExacto = 'CD ' + cdSolicitado;
        porUsuarioBase = porUsuarioBase.filter(
          x => normText(x.cd) === cdExacto
        );
      }

      // Filtrar por usuario específico si se detectó en el mensaje
      let porUsuarioFiltrado;
      if (usuarioDetectado) {
        porUsuarioFiltrado = porUsuarioBase.filter(
          x => (x.usuario || '').toUpperCase() === usuarioDetectado
        );
        // Si no hay resultados para el mes solicitado, ampliar a todos los meses del usuario
        if (porUsuarioFiltrado.length === 0) {
          porUsuarioFiltrado = porUsuarioMensual.filter(
            x => (x.usuario || '').toUpperCase() === usuarioDetectado
          );
        }
        // Ordenar por mes para mostrar evolución
        porUsuarioFiltrado = porUsuarioFiltrado.slice().sort((a, b) => Number(a.mes) - Number(b.mes));
      } else if (esMasProductivo) {
        // "Operador más productivo" → criterio eficiencia: lineas_por_hora_activa
        // Top N POR CD para que todos los CDs queden representados.
        const TOP_EFI_POR_CD = 8;
        if (pideListaCompletaUsuarios) {
          porUsuarioFiltrado = porUsuarioBase
            .slice()
            .sort((a, b) => Number(b.lineas_por_hora_activa || 0) - Number(a.lineas_por_hora_activa || 0))
            .map((x, i) => ({ ...x, posicion: i + 1 }));
        } else {
          const cdsEfi = [...new Set(porUsuarioBase.map(x => (x.cd || 'SIN_CD').trim()))].sort();
          porUsuarioFiltrado = [];
          let posEfi = 1;
          for (const cd of cdsEfi) {
            porUsuarioBase
              .filter(x => (x.cd || 'SIN_CD').trim() === cd)
              .sort((a, b) => Number(b.lineas_por_hora_activa || 0) - Number(a.lineas_por_hora_activa || 0))
              .slice(0, TOP_EFI_POR_CD)
              .forEach((x, i) => porUsuarioFiltrado.push({ ...x, posicion_cd: i + 1, posicion: posEfi++ }));
          }
        }
      } else {
        // "Ranking de operadores" → criterio volumen: lineas totales descendente
        // Top N POR CD para que todos los CDs queden representados.
        const TOP_VOL_POR_CD = 8;
        if (pideListaCompletaUsuarios) {
          porUsuarioFiltrado = porUsuarioBase
            .slice()
            .sort((a, b) => Number(b.lineas || 0) - Number(a.lineas || 0))
            .map((x, i) => ({ ...x, posicion: i + 1 }));
        } else {
          const cdsVol = [...new Set(porUsuarioBase.map(x => (x.cd || 'SIN_CD').trim()))].sort();
          porUsuarioFiltrado = [];
          let posVol = 1;
          for (const cd of cdsVol) {
            porUsuarioBase
              .filter(x => (x.cd || 'SIN_CD').trim() === cd)
              .sort((a, b) => Number(b.lineas || 0) - Number(a.lineas || 0))
              .slice(0, TOP_VOL_POR_CD)
              .forEach((x, i) => porUsuarioFiltrado.push({ ...x, posicion_cd: i + 1, posicion: posVol++ }));
          }
        }
      }

      const totalBase = porUsuarioBase.length;
      const criterioRanking = esMasProductivo
        ? 'lineas_por_hora_activa (eficiencia WMS)'
        : 'lineas (volumen total)';
      const textoRanking = esMasProductivo
        ? 'Ranking por líneas por hora activa WMS'
        : 'Ranking por volumen de líneas';

      // Cuando la consulta pide canal, por_usuario_canal es la fuente principal.
      // Se omite por_usuario (ranking general) para que el AI no lo confunda con el canal.
      const _esConsultaCanal = pideDercoCanales || _mencionaCanalGenerico;

      if (_esConsultaCanal) {
        prodCompacta.consulta_resuelta = {
          tipo: 'operador_por_canal',
          fuente_principal: 'por_usuario_canal',
          cd: cdSolicitado ? 'CD ' + cdSolicitado : 'TODOS',
          mes: mesObjetivo || 'todos',
          usuario_filtrado: usuarioDetectado || null,
          lista_completa: pideListaCompletaUsuarios,
          regla: [
            'CONSULTA OPERARIO × CANAL. Fuente principal: campo por_usuario_canal.',
            'OBLIGATORIO: listar cada OPERARIO INDIVIDUALMENTE dentro de su canal. NO sumar ni totalizar por canal.',
            'Cada fila de por_usuario_canal es UN operario en UN canal: (cd, usuario, canal, mes, lineas, unidades, ...).',
            'Agrupar la presentación por canal, luego listar operarios de mayor a menor líneas dentro de cada canal.',
            'TERMINOLOGIA: dias_trabajados → "Días activos WMS"; horas_activas → "Horas activas WMS"; lineas_por_hora_activa → "Líneas por hora activa WMS".',
            'Si por_usuario_canal_truncado=true, aclarar que se muestran los principales N y el usuario puede pedir "lista completa".',
            'La conclusión DEBE incluir: "El criterio es líneas por hora activa WMS. No corresponde a asistencia ni horas trabajadas reales."',
            'NO usar canal totals del campo derco_canales (no está en este contexto). Usar SOLO por_usuario_canal.'
          ].join(' ')
        };
        // NO agregar por_usuario para evitar que el AI lo use en lugar de por_usuario_canal.
      } else {
        // ── Cliente específico no-DERCO: usar por_usuario_cliente si disponible ──
        // por_usuario_cliente_mensual tiene desglose real (cd, cliente, usuario)
        // generado por calcular_por_usuario_cliente en productividad_usuarios.py.
        const _clienteEsNoDerco = clienteSolicitado && clienteSolicitado !== 'DERCO';
        const _mesUC2 = periodoSolicitado.mes ||
          ([...new Set(_porUsuarioClienteMensualGlobal.map(x => Number(x.mes)))]
            .sort((a, b) => b - a)[0] || null);

        // Intentar usar datos exactos por cliente
        let _baseCliente = [];
        if (_clienteEsNoDerco && _porUsuarioClienteMensualGlobal.length > 0) {
          _baseCliente = _porUsuarioClienteMensualGlobal.filter(x =>
            (!_mesUC2 || Number(x.mes) === _mesUC2) &&
            (x.cliente || '').toUpperCase().trim() === clienteSolicitado
          );
          if (cdSolicitado) {
            const _cdExCli = 'CD ' + cdSolicitado;
            _baseCliente = _baseCliente.filter(x => normText(x.cd) === cdSolicitado ||
              (x.cd || '').toUpperCase().trim() === _cdExCli.toUpperCase());
          }
        }

        const _usaClienteExacto = _clienteEsNoDerco && _baseCliente.length > 0;

        if (_usaClienteExacto) {
          // ✅ Datos exactos para este cliente — top N por CD
          const TOP_CLI_POR_CD = 10;
          const _cdsCliente = [...new Set(_baseCliente.map(x => (x.cd||'SIN_CD').trim()))].sort();
          let _filtradoCliente = [];
          let _posCliGlobal = 1;
          if (pideListaCompletaUsuarios || usuarioDetectado) {
            _filtradoCliente = _baseCliente
              .sort((a, b) => Number(b.lineas||0) - Number(a.lineas||0))
              .map((x, i) => ({ ...x, posicion: i + 1 }));
          } else {
            for (const cd of _cdsCliente) {
              _baseCliente
                .filter(x => (x.cd||'SIN_CD').trim() === cd)
                .sort((a, b) => Number(b.lineas||0) - Number(a.lineas||0))
                .slice(0, TOP_CLI_POR_CD)
                .forEach((x, i) => _filtradoCliente.push({ ...x, posicion_cd: i+1, posicion: _posCliGlobal++ }));
            }
          }
          const _hayTruncCliente = !usuarioDetectado && !pideListaCompletaUsuarios &&
            _cdsCliente.some(cd => _baseCliente.filter(x=>(x.cd||'SIN_CD').trim()===cd).length > TOP_CLI_POR_CD);

          prodCompacta.consulta_resuelta = {
            tipo: 'por_usuario_cliente_exacto',
            cliente: clienteSolicitado,
            cd: cdSolicitado ? 'CD ' + cdSolicitado : 'TODOS',
            mes: _mesUC2 || 'todos',
            usuario_filtrado: usuarioDetectado || null,
            fuente: 'por_usuario_cliente',
            nota_fuente: 'Datos exactos: operarios que registraron movimientos WMS para ' + clienteSolicitado + '. No es un estimado CD-global.',
            lista_completa: pideListaCompletaUsuarios,
            regla: [
              'DATOS EXACTOS por cliente. por_usuario_cliente contiene solo los operarios que trabajaron para ' + clienteSolicitado + '.',
              'Agrupar por CD si hay varios. Dentro de cada CD ordenar por líneas desc.',
              'TERMINOLOGIA: dias_trabajados → "Días activos WMS"; horas_activas → "Horas activas WMS"; lineas_por_hora_activa → "Líneas por hora activa WMS".',
              'La conclusión DEBE incluir: "El criterio usado es líneas por hora activa WMS. No corresponde a asistencia ni horas trabajadas reales."',
              'Si por_usuario_cliente_truncado=true, aclarar top N y que el usuario puede pedir lista completa.'
            ].join(' ')
          };
          prodCompacta.por_usuario_cliente = _filtradoCliente;
          prodCompacta.por_usuario_cliente_total = _baseCliente.length;
          prodCompacta.por_usuario_cliente_mostrados = _filtradoCliente.length;
          prodCompacta.por_usuario_cliente_truncado = _hayTruncCliente;

        } else {
          // Fallback: ranking CD-completo con advertencia
          const _cdsConDatosUsuario = [
            ...new Set(porUsuarioBase.map(x => (x.cd || '').trim()).filter(Boolean))
          ].sort();
          const _notaFallback = _clienteEsNoDerco
            ? ('INSTRUCCIÓN: MOSTRAR el array por_usuario que está en el contexto — '
              + 'es el ranking del CD completo para el período, no datos vacíos. '
              + 'ACLARAR al usuario que los operarios se reportan a nivel de CD completo '
              + 'y que próximamente se contará con el desglose específico por cliente. '
              + 'CDs con datos disponibles: ' + _cdsConDatosUsuario.join(', ') + '.')
            : null;

          prodCompacta.consulta_resuelta = {
            tipo: 'por_usuario_operador',
            cd: cdSolicitado ? 'CD ' + cdSolicitado : 'TODOS',
            cds_con_datos_operarios: _cdsConDatosUsuario,
            mes: mesObjetivo || 'todos',
            usuario_filtrado: usuarioDetectado || null,
            criterio_ranking: criterioRanking,
            texto_ranking: textoRanking,
            nota_cliente_operario: _notaFallback,
            lista_completa: pideListaCompletaUsuarios,
            regla: [
              'El array por_usuario YA ESTÁ ORDENADO según criterio_ranking. Presentar en el MISMO ORDEN del campo posicion.',
              'TERMINOLOGIA OBLIGATORIA: dias_trabajados → "Días activos WMS"; horas_activas → "Horas activas WMS"; lineas_por_hora_activa → "Líneas por hora activa WMS".',
              'REGLA METODOLOGICA: provienen de movimientos WMS, no de asistencia RRHH. La conclusión DEBE incluir: "El criterio usado es líneas por hora activa WMS. No corresponde a asistencia ni horas trabajadas reales."',
              'ACCIÓN OBLIGATORIA: MOSTRAR el array por_usuario que está en el contexto. NO decir que no hay datos.',
              'Si nota_cliente_operario es no-nulo: leerlo y aclarar al usuario que son del CD completo, no del cliente específico.',
              'Para "ranking de operadores": usar lineas totales, texto "' + textoRanking + '".',
              'Si por_usuario_truncado=true, aclarar top (por_usuario_mostrados de por_usuario_total).'
            ].join(' ')
          };
          prodCompacta.por_usuario = porUsuarioFiltrado;
          prodCompacta.por_usuario_total = totalBase;
          prodCompacta.por_usuario_mostrados = porUsuarioFiltrado.length;
          const _topPorCdActual2 = esMasProductivo ? 8 : 8;
          const _cdsEnBase2 = [...new Set(porUsuarioBase.map(x => (x.cd||'SIN_CD').trim()))];
          prodCompacta.por_usuario_truncado = !usuarioDetectado && !pideListaCompletaUsuarios &&
            _cdsEnBase2.some(cd => porUsuarioBase.filter(x=>(x.cd||'SIN_CD').trim()===cd).length > _topPorCdActual2);
        }
        // por_usuario data handled in if/else blocks above
      }
    }

    // Desglose operador × canal (solo DERCO). Se activa cuando el query menciona
    // operador/usuario Y canal (pideDercoCanales o _mencionaCanalGenerico). El único
    // desglose por canal disponible es DERCO, así que se sirve aunque DERCO no se
    // mencione explícitamente ("operario por canal" → se entiende que es DERCO).
    const _porUsuarioCanalMensualGlobal = Array.isArray(kpi.historico?.productividad?.por_usuario_canal_mensual)
      ? kpi.historico.productividad.por_usuario_canal_mensual
      : [];
    // _porUsuarioClienteMensualGlobal declarado al inicio del script (evita TDZ).
    if (esUsuario && (pideDercoCanales || _mencionaCanalGenerico) && _porUsuarioCanalMensualGlobal.length > 0) {
      // Top 8 por canal → máx ~24 registros para 3 canales, ~1.900 chars, bajo límite Telegram.
      // El usuario puede pedir "lista completa" para ver todos.
      const TOP_POR_CANAL = 8;
      const _mesesDisponiblesUC = [...new Set(_porUsuarioCanalMensualGlobal.map(x => Number(x.mes)))].sort((a, b) => b - a);
      const mesObjetivoUC = periodoSolicitado.mes || _mesesDisponiblesUC[0] || null;

      let baseUC = mesObjetivoUC
        ? _porUsuarioCanalMensualGlobal.filter(x => Number(x.mes) === mesObjetivoUC)
        : _porUsuarioCanalMensualGlobal;

      if (cdSolicitado) {
        const cdExactoUC = 'CD ' + cdSolicitado;
        baseUC = baseUC.filter(x => normText(x.cd) === cdExactoUC);
      }

      let filtradoUC;
      if (usuarioDetectado) {
        filtradoUC = baseUC.filter(
          x => (x.usuario || '').toUpperCase() === usuarioDetectado
        );
        if (filtradoUC.length === 0) {
          filtradoUC = _porUsuarioCanalMensualGlobal.filter(
            x => (x.usuario || '').toUpperCase() === usuarioDetectado
          );
        }
        // Orden lógico: por mes ascendente, luego canal por líneas desc
        filtradoUC = filtradoUC.slice().sort((a, b) =>
          Number(a.mes) - Number(b.mes) ||
          (a.canal || '').localeCompare(b.canal || '') ||
          Number(b.lineas || 0) - Number(a.lineas || 0)
        );
      } else {
        // Sin usuario específico: top N POR CANAL (no global).
        // Garantiza que todos los canales aparezcan representados.
        const canalesUnicos = [...new Set(baseUC.map(x => x.canal || 'SIN_CANAL'))].sort();
        filtradoUC = [];
        let posGlobal = 1;
        for (const canal of canalesUnicos) {
          const enCanal = baseUC
            .filter(x => (x.canal || 'SIN_CANAL') === canal)
            .sort((a, b) => Number(b.lineas || 0) - Number(a.lineas || 0));
          const limite = pideListaCompletaUsuarios ? enCanal.length : TOP_POR_CANAL;
          enCanal.slice(0, limite).forEach((x, i) => {
            filtradoUC.push({ ...x, posicion_canal: i + 1, posicion: posGlobal++ });
          });
        }
      }

      // Totales reales por canal para que el AI indique cuántos quedan fuera.
      const canalesUnicosBase = [...new Set(baseUC.map(x => x.canal || 'SIN_CANAL'))].sort();
      const totalPorCanal = Object.fromEntries(
        canalesUnicosBase.map(c => [c, baseUC.filter(x => (x.canal || 'SIN_CANAL') === c).length])
      );
      const hayTruncadoEnAlgunCanal = !usuarioDetectado && !pideListaCompletaUsuarios &&
        canalesUnicosBase.some(c => totalPorCanal[c] > TOP_POR_CANAL);

      prodCompacta.por_usuario_canal = filtradoUC;
      prodCompacta.por_usuario_canal_total = baseUC.length;
      prodCompacta.por_usuario_canal_total_por_canal = totalPorCanal;
      prodCompacta.por_usuario_canal_mostrados = filtradoUC.length;
      prodCompacta.por_usuario_canal_truncado = hayTruncadoEnAlgunCanal;

      // Líneas no asignadas a operador por canal/mes — para que el modelo pueda
      // explicar diferencias cuando la suma de operadores no totaliza el total del canal.
      const lineasNoAsignadas = Array.isArray(kpi.historico?.productividad?.lineas_no_asignadas_por_canal_mes)
        ? kpi.historico.productividad.lineas_no_asignadas_por_canal_mes
        : [];
      let lineasNoAsignadasFiltrado = lineasNoAsignadas;
      if (mesObjetivoUC) {
        lineasNoAsignadasFiltrado = lineasNoAsignadasFiltrado.filter(x => Number(x.mes) === mesObjetivoUC);
      }
      if (cdSolicitado) {
        const cdExactoLNA = cdSolicitado;
        lineasNoAsignadasFiltrado = lineasNoAsignadasFiltrado.filter(x => normText(x.cd).includes(cdExactoLNA));
      }
      if (lineasNoAsignadasFiltrado.length > 0) {
        prodCompacta.lineas_no_asignadas_por_canal = lineasNoAsignadasFiltrado;
      }

      prodCompacta.consulta_resuelta_canal = {
        tipo: 'operador_por_canal',
        cliente: 'DERCO',
        nota_cliente: 'El desglose operador × canal solo existe para DERCO. Si el usuario preguntó genéricamente ("por canal" sin mencionar DERCO), responder con los datos de DERCO y aclarar que el canal aplica a DERCO únicamente.',
        cd: cdSolicitado ? 'CD ' + cdSolicitado : 'TODOS',
        mes: mesObjetivoUC || 'todos',
        usuario_filtrado: usuarioDetectado || null,
        lista_completa: pideListaCompletaUsuarios,
        regla: [
          'Usar por_usuario_canal para responder desglose operador × canal.',
          'Cada registro es (cd, usuario, canal, mes) con lineas, unidades, dias_trabajados, horas_activas y sus tasas derivadas.',
          'Terminología: "Días activos WMS", "Horas activas WMS", "Líneas por día activo", "Líneas por hora activa WMS", "Unidades por día activo", "Unidades por hora activa WMS". No usar "asistencia" ni "horas trabajadas reales".',
          'Si el usuario pidió un usuario específico, agrupar la presentación por canal y mostrar los meses si hay varios.',
          'Si no hay usuario específico, agrupar por canal y presentar top operadores dentro de cada canal (los registros ya vienen ordenados por líneas descendente globalmente — el modelo debe agrupar).',
          'Si por_usuario_canal_truncado=true, aclarar que se muestran los principales N de un universo más grande (por_usuario_canal_total) y que el usuario puede pedir "lista completa" para verlos todos.',
          'Si lineas_no_asignadas_por_canal existe, AVISAR que la suma de operadores puede ser menor al total del canal porque hay líneas con Fecha_Turno fuera del mes (spillover) o sin operador WMS registrado. Mostrar lineas_asignadas_a_operador, lineas_no_asignadas y total_lineas_canal para que el usuario vea el desglose.',
          'La conclusión debe explicar que el criterio es líneas por hora activa WMS y que el split por canal aplica solo a DERCO.'
        ].join(' ')
      };
    }

    contexto = {
      disponible: $json.disponible,
      fecha_consulta: $json.fecha_consulta,
      kpi_ops: {
        productividad: prodCompacta
      }
    };
  }


  // ══════════════════════════════════════════════════════════════════════
  // RECEPCIONES INBOUND
  // Patrón análogo a esProductividad / esOTIF / esInventario.
  // Fuente: kpi.historico?.recepciones (generado por recepciones_kpi.py)
  // ══════════════════════════════════════════════════════════════════════
  if (esRecepciones && !esProductividad && !esOTIF && !esInventario) {
    const recep = kpi.historico?.recepciones || {};

    // Helper: filtra array por mes
    const _filtMs = (arr, mes) =>
      Array.isArray(arr) && mes
        ? arr.filter(x => Number(x.mes) === mes)
        : (Array.isArray(arr) ? arr : []);

    // Helper: filtra por cliente
    const _filtCli = (arr, cli) =>
      cli ? arr.filter(x => (x.cliente || '').toUpperCase() === cli) : arr;

    // Helper: filtra por CD
    const _filtCd = (arr, cd) => {
      if (!cd) return arr;
      const target = 'CD ' + cd.toUpperCase();
      return arr.filter(x => (x.cd || '').toUpperCase() === target);
    };

    // Período objetivo (mes solicitado o mes actual disponible)
    const mesObjetivoRec = periodoSolicitado.mes || recep.periodo?.hasta_mes || null;
    const cdsDisponiblesRecep = recep.cds_detectados || [];
    const clientesDisponiblesRecep = recep.clientes_detectados || [];

    // ── por_cliente (agregación principal) ────────────────────────────
    let _porClienteRec = _filtMs(recep.por_cliente_mensual, mesObjetivoRec);
    _porClienteRec = _filtCli(_porClienteRec, clienteSolicitado);
    _porClienteRec = _filtCd(_porClienteRec, cdSolicitado);

    // ── por_cd (cross-cliente) ─────────────────────────────────────────
    let _porCdRec = _filtMs(recep.por_cd_mensual, mesObjetivoRec);
    _porCdRec = _filtCd(_porCdRec, cdSolicitado);

    const recepCompacta = {
      disponible: recep.disponible,
      periodo: recep.periodo,
      cds_detectados: cdsDisponiblesRecep,
      clientes_detectados: clientesDisponiblesRecep,
      por_cliente: _porClienteRec,
      por_cd: _porCdRec,
    };

    // ── Detalle diario (solo si se pide) ──────────────────────────────
    if (pidePorDiaRecep) {
      let _pdCli = _filtMs(recep.por_dia_cliente_mensual, mesObjetivoRec);
      _pdCli = _filtCli(_pdCli, clienteSolicitado);
      _pdCli = _filtCd(_pdCli, cdSolicitado);
      recepCompacta.por_dia_cliente = _pdCli;

      let _pdCd = _filtMs(recep.por_dia_cd_mensual, mesObjetivoRec);
      _pdCd = _filtCd(_pdCd, cdSolicitado);
      recepCompacta.por_dia_cd = _pdCd;
    }

    // ── Por origen / proveedor ─────────────────────────────────────────
    if (pideOrigenRecep) {
      let _porOrigen = _filtMs(recep.por_origen_mensual, mesObjetivoRec);
      _porOrigen = _filtCli(_porOrigen, clienteSolicitado);
      _porOrigen = _filtCd(_porOrigen, cdSolicitado);
      recepCompacta.por_origen = _porOrigen;
    }

    // ── Backlog detallado ──────────────────────────────────────────────
    if (pideBacklog) {
      let _blMs = _filtMs(recep.backlog_or_mensual, mesObjetivoRec);
      _blMs = _filtCli(_blMs, clienteSolicitado);
      _blMs = _filtCd(_blMs, cdSolicitado);
      recepCompacta.backlog_or = _blMs;
      recepCompacta.backlog_total = _blMs.length;
    }

    // ── Nota metodológica (siempre presente) ──────────────────────────
    recepCompacta.nota_metodologica = recep.nota_metodologica || {};

    // ── Consulta resuelta (instrucciones al AI) ────────────────────────
    recepCompacta.consulta_resuelta = {
      tipo: 'recepciones',
      cd: cdSolicitado ? 'CD ' + cdSolicitado : 'TODOS',
      cliente: clienteSolicitado || 'TODOS',
      mes: mesObjetivoRec || 'todos',
      sub_query: {
        backlog:        pideBacklog,
        origen:         pideOrigenRecep,
        por_dia:        pidePorDiaRecep,
        tpr:            pideTPR,
        complejidad:    pideComplejidadRecep,
        ranking:        pideRankingRecep,
        operario:       pideOperarioRecep,
        guardado:       pideGuardado,
        volumen_fisico: pideVolumenFisico,
      },
      regla: [
        'TERMINOLOGIA: usar OR (Orden de Recepción). Usar pallets o PLT. NUNCA OP.',
        'NO mencionar: operario (sin columna en archivo), tiempo guardado (0% cobertura WMS), M3/Kilos/Litros (excluidos).',
        'Si sub_query.operario=true: indicar "el archivo de recepciones no incluye columna de operario WMS".',
        'Si sub_query.guardado=true: indicar "los timestamps de guardado no se completan en el WMS actual".',
        'Si sub_query.volumen_fisico=true: indicar "métricas de masa/volumen están excluidas del análisis".',
        'TPR: reportar tpr_dias_por_or como dato principal (más operacional). tpr_dias_por_fila como referencia Power BI.',
        'TPR NOTA OBLIGATORIA: mide desde Fh. Generación (creación OR) hasta Fh. Fin Recepción. No mide tránsito físico.',
        'Días actividad = Fh. Generación, NO fecha llegada física del camión.',
        'Si backlog_or vacío para el filtro: "Sin OR pendientes en el período consultado."',
        'OR significativa = >= 20 pallets (criterio operacional match Power BI).',
        'Si !recep.disponible o arrays vacíos: indicar que recepciones no están disponibles para el período/cliente.',
      ].join(' ')
    };

    contexto = {
      disponible: $json.disponible,
      fecha_consulta: $json.fecha_consulta,
      kpi_ops: {
        recepciones: recepCompacta
      }
    };

    return JSON.stringify(contexto);
  }

  if (esOTIF && !esProductividad) {
    const otif = nnss.otif || {};
    const pendientes = nnss.pendientes || {};
    const porCliente = Array.isArray(otif.por_cliente) ? otif.por_cliente : [];
    const detalle = Array.isArray(otif.pedidos_no_evaluables_detalle) ? otif.pedidos_no_evaluables_detalle : [];
    const detallePorCliente = Array.isArray(otif.pedidos_no_evaluables_detalle_por_cliente) ? otif.pedidos_no_evaluables_detalle_por_cliente : [];
    const clientesNoEvaluables = Array.isArray(otif.clientes_no_evaluables) ? otif.clientes_no_evaluables : [];
    const porCdOtif = Array.isArray(otif.por_cd) ? otif.por_cd : [];
    const porCdFiltradoOtif = cdSolicitado
      ? porCdOtif.filter(x => normText(x.cd) === cdSolicitado)
      : [];

    const resumenCliente =
      clienteSolicitado
        ? porCliente.find(x => normText(x.cliente) === clienteSolicitado) || null
        : null;

    const bloqueClienteDetalle =
      clienteSolicitado
        ? detallePorCliente.find(x => normText(x.cliente) === clienteSolicitado) || null
        : null;

    let pedidosFiltrados = [];

    if (clienteSolicitado) {
      if (bloqueClienteDetalle && Array.isArray(bloqueClienteDetalle.detalle)) {
        pedidosFiltrados = bloqueClienteDetalle.detalle.map(x => ({
          cliente: bloqueClienteDetalle.cliente,
          nro_pedido: x.nro_pedido,
          estado: x.estado,
          dias_abierto: x.dias_abierto,
          lineas: x.lineas,
          unidades: x.unidades,
          motivo: x.motivo,
          fecha_inicio_preparacion: x.fecha_inicio_preparacion
        }));
      } else {
        pedidosFiltrados = detalle.filter(x => normText(x.cliente) === clienteSolicitado);
      }
    } else {
      pedidosFiltrados = detalle;
    }

    pedidosFiltrados = pedidosFiltrados
      .slice()
      .sort((a, b) => {
        const dias = Number(b.dias_abierto || 0) - Number(a.dias_abierto || 0);
        if (dias !== 0) return dias;
        const fecha = String(a.fecha_inicio_preparacion || '').localeCompare(String(b.fecha_inicio_preparacion || ''));
        if (fecha !== 0) return fecha;
        const cli = String(a.cliente || '').localeCompare(String(b.cliente || ''));
        if (cli !== 0) return cli;
        return String(a.nro_pedido || '').localeCompare(String(b.nro_pedido || ''));
      });

    /*
      Aunque el usuario pida "todos", por Telegram se entrega un corte.
      El total completo queda informado en pedidos_no_evaluables_filtrados_total.
      Para enviar los 90/125 completos, conviene implementar archivo o paginación.
    */
    const limiteListado = pideListaPedidos ? Math.min(MAX_LISTADO_TELEGRAM, pedidosFiltrados.length) : 0;
    const pedidosMostrados = pideListaPedidos ? pedidosFiltrados.slice(0, limiteListado) : [];

    const detallePorClienteResumen = detallePorCliente.map(x => ({
      cliente: x.cliente,
      total_pedidos: x.total_pedidos,
      lineas: x.lineas,
      unidades: x.unidades
    }));

    const otifCompacto = {
      disponible: otif.disponible ?? nnss.disponible,
      periodo: nnss.periodo,
      pedidos_evaluados: otif.pedidos_evaluados,
      pedidos_no_evaluables: otif.pedidos_no_evaluables,
      pct_on_time: otif.pct_on_time,
      pct_in_full: otif.pct_in_full,
      pct_otif: otif.pct_otif,
      criterio_calculo: otif.criterio_calculo,
      por_cliente_filtrado: clienteSolicitado && resumenCliente ? [resumenCliente] : undefined,
      por_cliente: !clienteSolicitado && !pideListaPedidos
        ? porCliente.map(x => {
            const { detalle_no_on_time, detalle_no_in_full, ...rest } = x;
            return rest;
          })
        : undefined,
      clientes_no_evaluables: clientesNoEvaluables,
      pedidos_no_evaluables_detalle_total: otif.pedidos_no_evaluables_detalle_total ?? detalle.length,
      pedidos_no_evaluables_detalle_mostrados: pedidosMostrados.length,
      pedidos_no_evaluables_detalle_truncado: pedidosMostrados.length < pedidosFiltrados.length,
      pedidos_no_evaluables_filtrados_total: pedidosFiltrados.length,
      pedidos_no_evaluables_filtrados_mostrados: pedidosMostrados.length,
      limite_listado_telegram: MAX_LISTADO_TELEGRAM,
      solicitud_todos_los_pedidos: pideTodosLosPedidos,
      pedidos_no_evaluables_detalle_por_cliente_resumen: detallePorClienteResumen,
      pedidos_no_evaluables_detalle_cliente: bloqueClienteDetalle ? {
        cliente: bloqueClienteDetalle.cliente,
        total_pedidos: bloqueClienteDetalle.total_pedidos,
        lineas: bloqueClienteDetalle.lineas,
        unidades: bloqueClienteDetalle.unidades
      } : undefined,
      pedidos_no_evaluables_detalle_filtrado: pideListaPedidos ? pedidosMostrados : undefined,
      regla_listado: pideListaPedidos
        ? 'Usar exclusivamente pedidos_no_evaluables_detalle_filtrado. Listar solo los registros entregados en ese arreglo. No inventar pedidos adicionales. No decir que se muestran 90 registros si el arreglo trae menos. Si pedidos_no_evaluables_detalle_truncado es true, aclarar: se muestran X de Y pedidos no evaluables, ordenados por días abiertos. No enviar los 90/125 completos en un solo mensaje de Telegram.'
        : undefined,
      mensaje_si_pide_todos: pideTodosLosPedidos
        ? 'El usuario pidió todos los pedidos. Por límite de Telegram, se debe mostrar solo el corte indicado y aclarar el total disponible. Para entregar todos, se requiere implementar archivo, paginación o consulta por rangos.'
        : undefined,
      aclaracion_202: 'En el contexto vigente no aparece 202 como total de pedidos no evaluables. El total vigente global es 125. DERCO tiene 90.',
      por_cd: porCdOtif,
      por_cd_filtrado: cdSolicitado && porCdFiltradoOtif.length > 0 ? porCdFiltradoOtif : undefined,
      regla_otif_por_cd: cdSolicitado
        ? `OTIF por CD ${cdSolicitado}: usar el objeto de por_cd_filtrado con cd="${cdSolicitado}". Campos de resumen: pedidos_evaluados, pedidos_no_on_time, pedidos_no_in_full, pedidos_otif, pct_on_time, pct_in_full, pct_otif. gap_pct = 100 - pct_otif. gap_pedidos = pedidos_evaluados - pedidos_otif. NO usar pedidos_evaluados ni pct_otif globales. NO sumar pedidos_no_on_time + pedidos_no_in_full (se solapan). NO confundir arrastres.total con pedidos_no_on_time. Para motivos de no IN FULL: usar motivos_no_in_full (agregado por motivo con lineas) y detalle_no_in_full (listado por pedido con nro_pedido, cliente, estado, motivos). Para pedidos no OT: usar detalle_no_on_time (nro_pedido, cliente, estado, es_arrastre).`
        : 'Si el usuario pregunta por OTIF o gap de un CD, usar el objeto correspondiente en por_cd filtrado por campo cd. NO usar totales globales. gap_pct = 100 - pct_otif del CD. gap_pedidos = pedidos_evaluados - pedidos_otif. NO sumar pedidos_no_on_time + pedidos_no_in_full. Para motivos de no IN FULL usar motivos_no_in_full y detalle_no_in_full del objeto CD. Para pedidos no OT usar detalle_no_on_time.'
    };

    contexto = {
      disponible: $json.disponible,
      fecha_consulta: $json.fecha_consulta,
      kpi_ops: {
        nnss: {
          disponible: nnss.disponible,
          periodo: nnss.periodo,
          otif: otifCompacto,
          pendientes: {
            total_pedidos: pendientes.total_pedidos,
            total_lineas: pendientes.total_lineas,
            total_unidades: pendientes.total_unidades,
            pedido_mas_antiguo: pendientes.pedido_mas_antiguo,
            por_cliente: pendientes.por_cliente,
            mayores_7_dias: pendientes.mayores_7_dias
          }
        }
      }
    };
  }

  // Safety net: cualquier output > 30000 chars (~7.5K tokens) se reemplaza por minimo.
  // Evita que queries no clasificadas envien el kpi_ops crudo (>1MB) al LLM.
  const _rawOut = JSON.stringify(contexto);
  if (_rawOut.length > 30000) {
    return JSON.stringify({
      disponible: contexto.disponible,
      fecha_consulta: contexto.fecha_consulta,
      alertas: contexto.alertas,
      pipeline: contexto.pipeline,
      kpi_ops: {
        _aviso: 'Contexto omitido por exceso de tamaño. Reformular con palabras clave: recepcion/recibio, OTIF/pedido, productividad/lineas, inventario/stock, staging.'
      }
    });
  }
  return _rawOut;
})()
}}