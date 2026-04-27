"""
CLI para administrar clientes del Bot Telegram externo.
Uso:
  py bots/admin_clientes.py listar
  py bots/admin_clientes.py registrar --chat_id 123456 --nombre "Juan Perez" --empresa "GRUPO PLANET SPA" --rut "94340000-8"
  py bots/admin_clientes.py desactivar --chat_id 123456
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_manager import init_db, registrar_cliente, get_cliente, listar_clientes
import sqlite3

DB_PATH = Path(__file__).parent / "db" / "egakat_bots.db"


def cmd_listar():
    clientes = listar_clientes()
    if not clientes:
        print("Sin clientes registrados.")
        return
    print(f"{'chat_id':>12} {'nombre':25} {'empresa':35} {'rut':15} {'activo'}")
    print("-" * 100)
    for c in clientes:
        print(f"{c['chat_id']:>12} {c['nombre']:25} {c['empresa']:35} {c['rut_cliente']:15} {'SI' if c['activo'] else 'NO'}")


def cmd_registrar(chat_id: int, nombre: str, empresa: str, rut: str):
    init_db()
    registrar_cliente(chat_id, nombre, empresa, rut)
    print(f"[OK] Registrado: chat_id={chat_id} | {nombre} | {empresa} | RUT {rut}")
    # Verificar
    c = get_cliente(chat_id)
    print(f"     Verificado en BD: {c}")


def cmd_desactivar(chat_id: int):
    with sqlite3.connect(DB_PATH) as con:
        con.execute("UPDATE usuarios_clientes SET activo=0 WHERE chat_id=?", (chat_id,))
    print(f"[OK] Cliente {chat_id} desactivado.")


def cmd_test_api(rut: str):
    """Prueba el endpoint resumen_cliente para un RUT."""
    import urllib.request, json
    port = int(os.getenv("API_COBRANZA_PORT", 8080))
    url = f"http://localhost:{port}/cobranza/resumen_cliente?rut={rut}"
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=60).read())
        print(f"empresa: {d.get('empresa')}")
        print(f"total_pendiente: {d.get('total_pendiente')}")
        cv = d.get('cartera_vencida', {})
        print(f"cartera_vencida: total={cv.get('total')} docs={cv.get('cantidad_documentos')}")
        pv = d.get('proximos_vencimientos', {})
        print(f"proximos (30d): total={pv.get('total')} docs={pv.get('cantidad_documentos')}")
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Admin Bot Clientes Egakat")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("listar")

    reg = sub.add_parser("registrar")
    reg.add_argument("--chat_id", type=int, required=True)
    reg.add_argument("--nombre",  required=True)
    reg.add_argument("--empresa", required=True)
    reg.add_argument("--rut",     required=True)

    des = sub.add_parser("desactivar")
    des.add_argument("--chat_id", type=int, required=True)

    tst = sub.add_parser("test")
    tst.add_argument("--rut", required=True)

    args = parser.parse_args()

    if args.cmd == "listar":
        cmd_listar()
    elif args.cmd == "registrar":
        cmd_registrar(args.chat_id, args.nombre, args.empresa, args.rut)
    elif args.cmd == "desactivar":
        cmd_desactivar(args.chat_id)
    elif args.cmd == "test":
        cmd_test_api(args.rut)
    else:
        parser.print_help()
