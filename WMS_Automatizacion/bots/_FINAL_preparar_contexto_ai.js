={{
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

  const esProductividad =
    msg.includes('productividad') ||
    msg.includes('lineas') ||
    msg.includes('líneas') ||
    msg.includes('unidades preparadas') ||
    msg.includes('preparo') ||
    msg.includes('preparó') ||
    msg.includes('preparadas');

  // Leer datos de usuarios disponibles para detección dinámica
  const _porUsuarioMensualGlobal = Array.isArray(kpi.historico?.productividad?.por_usuario_mensual)
    ? kpi.historico.productividad.por_usuario_mensual
    : [];
  const _usuariosDisponibles = [
    ...new Set(_porUsuarioMensualGlobal.map(x => (x.usuario || '').toUpperCase().trim()).filter(Boolean))
  ];
  const _msgUpper = rawMsg.toUpperCase();
  const usuarioDetectado = _usuariosDisponibles.find(u => u && _msgUpper.includes(u)) || null;

  const esUsuario =
    esProductividad && (
      usuarioDetectado !== null ||
      msg.includes('usuario') ||
      msg.includes('operador') ||
      msg.includes('trabajador') ||
      msg.includes('registró') ||
      msg.includes('registro') ||
      msg.includes('quien preparo') ||
      msg.includes('quién preparó') ||
      msg.includes('quien preparó') ||
      msg.includes('quién preparo') ||
      msg.includes('top operador') ||
      msg.includes('ranking') ||
      msg.includes('por persona') ||
      msg.includes('por operador')
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

  function cdFromMsg(text) {
    const t = normText(text);
    if (t.includes('QUILICURA')) return 'QUILICURA';
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
      const p = k?.nnss?.periodo || k?.fillrate?.periodo;
      if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'kpi_ops.nnss.periodo' };
    }

    if (nombreKpi === 'productividad') {
      const p = k?.productividad?.diario?.periodo || k?.productividad?.global?.periodo || k?.productividad?.periodo;
      if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'kpi_ops.productividad.periodo' };
    }

    if (nombreKpi === 'inventario') {
      const p = k?.inventario?.conteos_ciclicos?.periodo || k?.inventario?.ira_ila?.periodo || k?.inventario?.avance_conteo?.periodo;
      if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'kpi_ops.inventario.periodo' };
    }

    const p =
      k?.nnss?.periodo ||
      k?.productividad?.diario?.periodo ||
      k?.productividad?.global?.periodo ||
      k?.inventario?.conteos_ciclicos?.periodo ||
      k?.inventario?.ira_ila?.periodo;

    if (p?.anio && p?.mes) return { anio: Number(p.anio), mes: Number(p.mes), fuente: 'periodo_disponible_general' };

    return null;
  }

  function detectarKpiPrincipal(texto) {
    const t = String(texto || '').toLowerCase();
    if (t.includes('otif') || t.includes('on time') || t.includes('in full')) return 'otif';
    if (t.includes('fill rate') || t.includes('fillrate')) return 'fillrate';
    if (t.includes('productividad') || t.includes('lineas') || t.includes('líneas') || t.includes('unidades preparadas')) return 'productividad';
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
      k?.historico ||
      k?.kpi_historico ||
      k?.nnss?.otif_ytd ||
      k?.nnss?.historico ||
      k?.productividad?.ytd ||
      k?.productividad?.historico ||
      k?.inventario?.historico
    );

  const solicitudComparativaSinHistorico =
    periodoSolicitado.es_comparativo &&
    !(
      k?.historico ||
      k?.kpi_historico ||
      k?.nnss?.historico ||
      k?.productividad?.historico ||
      k?.inventario?.historico
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
  const maxContextLength = 60000;
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
        mensual_cliente:     filtrarClientes ? filtrarRows(hp.mensual_cliente) : hp.mensual_cliente,
        ytd_cliente:         filtrarClientes ? filtrarRows(hp.ytd_cliente)     : hp.ytd_cliente,
        derco_ap_mensual:    hp.derco_ap_mensual,
        derco_ap_ytd:        hp.derco_ap_ytd,
        por_usuario:         hp.por_usuario,
        por_usuario_mensual: hp.por_usuario_mensual
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
    if (kpiTipo === 'productividad') return arrTiene(hp.mensual_cliente) || arrTiene(hp.derco_ap_mensual);
    return arrTiene(hn.otif_mensual) || arrTiene(hn.fillrate_mensual) || arrTiene(hp.mensual_cliente);
  }

  const historicoResponde = historicoTienePeriodo(
    kpiPrincipalSolicitado,
    periodoSolicitado.mes,
    periodoSolicitado.anio,
    periodoSolicitado.es_ytd
  );

  if ((periodoSolicitadoNoDisponible || solicitudYtdSinHistorico || solicitudComparativaSinHistorico) && !historicoResponde && !esUsuario) {
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

  if ((periodoSolicitadoNoDisponible || periodoSolicitado.es_ytd || periodoSolicitado.es_comparativo) && historicoResponde && !esUsuario) {
    return JSON.stringify({
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
    });
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
      const mesObjetivo = periodoSolicitado.mes || null;

      // Filtrar base: por mes si se especificó, sino todos los meses
      let porUsuarioBase = mesObjetivo
        ? porUsuarioMensual.filter(x => Number(x.mes) === mesObjetivo)
        : porUsuarioMensual;

      // Filtrar por CD si se menciona uno
      if (cdSolicitado) {
        porUsuarioBase = porUsuarioBase.filter(
          x => normText(x.cd).includes(cdSolicitado)
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
      } else {
        // Sin usuario específico: ranking top N por lineas
        porUsuarioFiltrado = porUsuarioBase
          .slice()
          .sort((a, b) => Number(b.lineas || 0) - Number(a.lineas || 0))
          .slice(0, TOP_USUARIOS);
      }

      const totalBase = porUsuarioBase.length;
      prodCompacta.consulta_resuelta = {
        tipo: 'por_usuario_operador',
        cd: cdSolicitado || 'TODOS',
        mes: mesObjetivo || 'todos',
        usuario_filtrado: usuarioDetectado || null,
        regla: [
          'Usar exclusivamente por_usuario para responder preguntas de productividad por operador/usuario.',
          'horas_activas representa slots de hora únicos con actividad WMS; no son horas reales trabajadas ni asistencia.',
          'Para ranking sin usuario específico, ordenar por lineas descendente.',
          'Si se filtra por usuario específico, mostrar todos sus meses disponibles si el mes solicitado no tiene datos.'
        ].join(' ')
      };
      prodCompacta.por_usuario = porUsuarioFiltrado;
      prodCompacta.por_usuario_total = totalBase;
      prodCompacta.por_usuario_mostrados = porUsuarioFiltrado.length;
      prodCompacta.por_usuario_truncado = !usuarioDetectado && totalBase > TOP_USUARIOS;
    }

    contexto = {
      disponible: $json.disponible,
      fecha_consulta: $json.fecha_consulta,
      kpi_ops: {
        productividad: prodCompacta
      }
    };
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

  return JSON.stringify(contexto);
})()
}}