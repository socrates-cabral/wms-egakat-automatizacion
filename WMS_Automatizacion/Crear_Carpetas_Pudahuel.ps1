# ============================================================
# Crear_Carpetas_Pudahuel.ps1
# Crea estructura de carpetas de Recepciones 2026 para
# clientes del CD Pudahuel en OneDrive (sincronizado con SP).
# Ejecutar en PowerShell como usuario Socrates Cabral.
# ============================================================

$base = "C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Clientes EK"

$clientes = @(
    "BARENTZ",
    "CEPAS CHILE",
    "COLLICO",
    "DELIBEST",
    "INTIME",
    "NATIVO DRINKS SPA",   # empresa_wms WMS confirmada: "NATIVO DRINKS SPA"
    "OMNITECH",
    "RUNO SPA",             # deposito PUDAHUEL UNITARIO — misma estructura de carpetas
    "TRES MONTES",          # cliente nuevo, puede no tener movimientos aun
    "UNILEVER"
)

$meses = @(
    "01 Enero",
    "02 Febrero",
    "03 Marzo",
    "04 Abril",
    "05 Mayo",
    "06 Junio",
    "07 Julio",
    "08 Agosto",
    "09 Septiembre",
    "10 Octubre",
    "11 Noviembre",
    "12 Diciembre"
)

$totalCreadas = 0
$totalExistian = 0

foreach ($cliente in $clientes) {
    Write-Host "`n-- $cliente" -ForegroundColor Cyan

    foreach ($mes in $meses) {
        $ruta = Join-Path $base "$cliente\Recepciones\2026\$mes"

        if (Test-Path $ruta) {
            Write-Host "   [ya existe] $ruta" -ForegroundColor DarkGray
            $totalExistian++
        } else {
            New-Item -ItemType Directory -Path $ruta -Force | Out-Null
            Write-Host "   [creada]    $ruta" -ForegroundColor Green
            $totalCreadas++
        }
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "Carpetas creadas  : $totalCreadas"           -ForegroundColor Green
Write-Host "Ya existian       : $totalExistian"          -ForegroundColor DarkGray
Write-Host "Total meses/cliente: $($meses.Count * $clientes.Count)" -ForegroundColor Yellow
Write-Host ""
Write-Host "PROXIMO PASO:" -ForegroundColor White
Write-Host "  Confirmar empresa_wms de TRES MONTES en dropdown WMS Pudahuel," -ForegroundColor White
Write-Host "  luego agregar a CLIENTES_PUDAHUEL en recepciones_descarga.py" -ForegroundColor White
Write-Host ""
Write-Host "  Backfill 2026 Pudahuel:" -ForegroundColor White
Write-Host "  py WMS_Automatizacion\recepciones_descarga.py --sucursal PUDAHUEL --mes 01/2026 --mes 02/2026 --mes 03/2026 --mes 04/2026 --mes 05/2026" -ForegroundColor Cyan
Write-Host "  py WMS_Automatizacion\recepciones_descarga.py --sucursal PUDAHUEL UNITARIO --mes 01/2026 --mes 02/2026 --mes 03/2026 --mes 04/2026 --mes 05/2026" -ForegroundColor Cyan
