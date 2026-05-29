#!/usr/bin/env python3
"""
skillopt.py — Auto-optimizacion de skills via patron SkillOpt
Entrena skills como redes neuronales: epocas, batch, learning rate, validation gates.
Sin modificar pesos del modelo — solo mejora los prompts de los agentes.

Referencia: SkillOpt (Microsoft) — "Executive Strategy for Self-Evolving Agent Skills"

Uso:
    py skillopt.py revisor                    # optimiza con defaults (2 epocas)
    py skillopt.py revisor --epochs 3 --lr aggressive
    py skillopt.py --list                     # muestra skills con score actual
    py skillopt.py revisor --eval-only        # solo evalua, no optimiza
"""
import sys
import json
import shutil
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import os

sys.stdout.reconfigure(encoding="utf-8")

BASE    = Path(__file__).parent
AGENTS  = BASE / ".claude" / "agents"
CASES   = BASE / "skillopt" / "cases"
RESULTS = BASE / "skillopt" / "resultados"
BACKUPS = BASE / "skillopt" / "backups"

load_dotenv(BASE / ".env")

# ─── Learning rates ───────────────────────────────────────────────────────────
LEARNING_RATES = {
    "conservative": "Haz cambios minimos y quirurgicos. Solo modifica las secciones que claramente causaron fallos. No reorganices la estructura general.",
    "moderate":     "Puedes reorganizar secciones y agregar ejemplos. Mantener la intencion original pero mejora la especificidad.",
    "aggressive":   "Puedes reescribir secciones completas si crees que mejoraria significativamente el rendimiento. Mantener el objetivo del skill.",
}

VALIDATION_GATE = 0.5   # mejora minima para aceptar cambio (sobre 10)
MAX_TOKENS_EVAL = 1500
MAX_TOKENS_OPT  = 4000


# ─── Claude API ───────────────────────────────────────────────────────────────

def _claude(system: str, user: str, max_tokens: int = 1500) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""), timeout=30)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text


# ─── Lectura de skills ────────────────────────────────────────────────────────

def _parse_skill(path: Path) -> tuple[str, str]:
    """Retorna (frontmatter, system_prompt) del archivo .md del skill."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        return "---" + parts[1] + "---", parts[2].strip()
    return "", text.strip()


def _write_skill(path: Path, frontmatter: str, prompt: str):
    path.write_text(f"{frontmatter}\n\n{prompt}\n", encoding="utf-8")


# ─── Evaluador ────────────────────────────────────────────────────────────────

EVAL_SYSTEM = """Eres un evaluador experto de prompts de agentes de IA.
Tu trabajo: dado un skill (prompt de agente), su output sobre un caso de prueba,
y el resultado esperado — puntuar la calidad del output.

Responde SOLO con JSON valido en este formato exacto:
{
  "recall": <float 0-10>,
  "precision": <float 0-10>,
  "formato": <float 0-10>,
  "accionabilidad": <float 0-10>,
  "score_total": <float 0-10>,
  "fallos": ["descripcion de cada fallo detectado"],
  "aciertos": ["descripcion de cada cosa bien hecha"]
}

Criterios:
- recall (0-10): cuantos bugs esperados encontro? 10 = todos, 0 = ninguno
- precision (0-10): cuantos falsos positivos genero? 10 = cero FP, 0 = muchos FP
- formato (0-10): siguio el formato de output requerido (secciones, severidades, veredicto)?
- accionabilidad (0-10): los fixes propuestos son concretos y ejecutables?
- score_total: promedio ponderado (recall x0.4 + precision x0.3 + formato x0.15 + accionabilidad x0.15)
"""


def evaluar_caso(skill_prompt: str, caso: dict) -> dict:
    """Ejecuta el skill sobre el caso y evalua el output."""
    # Paso 1: ejecutar el skill
    output_skill = _claude(
        system=skill_prompt,
        user=f"Revisar el siguiente codigo:\n\n```python\n{caso['code']}\n```",
        max_tokens=MAX_TOKENS_EVAL,
    )

    # Paso 2: evaluar el output
    bugs_str = json.dumps(caso["bugs_esperados"], ensure_ascii=False, indent=2)
    eval_input = (
        f"CASO: {caso['descripcion']}\n\n"
        f"BUGS ESPERADOS:\n{bugs_str}\n\n"
        f"VEREDICTO ESPERADO: {caso['veredicto_esperado']}\n\n"
        f"OUTPUT DEL SKILL:\n{output_skill}\n"
    )
    eval_raw = _claude(EVAL_SYSTEM, eval_input, max_tokens=800)

    try:
        # Extraer JSON del output (puede venir con texto alrededor)
        match = re.search(r'\{.*\}', eval_raw, re.DOTALL)
        scores = json.loads(match.group()) if match else {}
    except Exception:
        scores = {"score_total": 5.0, "fallos": ["Error al parsear evaluacion"], "aciertos": []}

    scores["caso_id"]     = caso["id"]
    scores["output_skill"] = output_skill
    return scores


def evaluar_skill(skill_prompt: str, casos: list[dict]) -> dict:
    """Evalua un skill contra todos los casos. Retorna metricas agregadas."""
    resultados = []
    for caso in casos:
        print(f"  Evaluando {caso['id']}...", end=" ", flush=True)
        r = evaluar_caso(skill_prompt, caso)
        score = r.get("score_total", 5.0)
        print(f"score={score:.1f}/10")
        resultados.append(r)

    scores = [r.get("score_total", 5.0) for r in resultados]
    fallos_totales = [f for r in resultados for f in r.get("fallos", [])]

    return {
        "score_promedio": round(sum(scores) / len(scores), 2),
        "score_minimo":   round(min(scores), 2),
        "score_maximo":   round(max(scores), 2),
        "n_casos":        len(casos),
        "fallos":         fallos_totales[:10],
        "resultados":     resultados,
    }


# ─── Optimizador ─────────────────────────────────────────────────────────────

OPT_SYSTEM = """Eres un experto en prompt engineering para agentes de IA.
Tu trabajo: dado un skill (prompt de agente) que fallo en ciertos casos de prueba,
generar una version mejorada del prompt que corrija esos fallos.

Responde SOLO con el prompt mejorado — sin explicaciones, sin markdown extra,
sin comentarios. Solo el texto del prompt mejorado listo para reemplazar al original."""


def optimizar_skill(skill_prompt: str, metricas: dict, lr_instruccion: str) -> str:
    """Genera un prompt mejorado basado en los fallos detectados."""
    fallos_str = "\n".join(f"- {f}" for f in metricas["fallos"]) or "- Ninguno especifico"

    opt_input = (
        f"SKILL ACTUAL:\n\n{skill_prompt}\n\n"
        f"SCORE ACTUAL: {metricas['score_promedio']:.1f}/10 "
        f"(min={metricas['score_minimo']:.1f}, max={metricas['score_maximo']:.1f})\n\n"
        f"FALLOS DETECTADOS:\n{fallos_str}\n\n"
        f"INSTRUCCION DE LEARNING RATE: {lr_instruccion}\n\n"
        f"Genera el prompt mejorado:"
    )
    return _claude(OPT_SYSTEM, opt_input, max_tokens=MAX_TOKENS_OPT)


# ─── Loop principal ───────────────────────────────────────────────────────────

def run_skillopt(skill_name: str, epochs: int, lr: str, eval_only: bool):
    skill_path = AGENTS / f"{skill_name}.md"
    cases_path = CASES / f"{skill_name}_cases.json"

    if not skill_path.exists():
        print(f"[ERROR] Skill no encontrado: {skill_path}")
        sys.exit(1)
    if not cases_path.exists():
        print(f"[ERROR] Test cases no encontrados: {cases_path}")
        sys.exit(1)

    casos     = json.loads(cases_path.read_text(encoding="utf-8"))
    lr_text   = LEARNING_RATES.get(lr, LEARNING_RATES["moderate"])
    ts        = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path  = RESULTS / f"{skill_name}_{ts}.json"

    # Backup del skill original
    backup_path = BACKUPS / f"{skill_name}_{ts}_original.md"
    shutil.copy2(skill_path, backup_path)
    print(f"Backup: {backup_path.name}")

    frontmatter, prompt_actual = _parse_skill(skill_path)
    historial = []

    print(f"\n=== SkillOpt: {skill_name} | {len(casos)} casos | {epochs} epocas | lr={lr} ===\n")

    # Evaluacion inicial
    print("Evaluacion inicial:")
    metricas_base = evaluar_skill(prompt_actual, casos)
    score_base = metricas_base["score_promedio"]
    print(f"  Score base: {score_base:.1f}/10\n")
    historial.append({"epoca": 0, "score": score_base, "accion": "baseline"})

    if eval_only:
        log_path.write_text(json.dumps(historial, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Resultados guardados: {log_path}")
        return

    prompt_mejor = prompt_actual
    score_mejor  = score_base

    for epoca in range(1, epochs + 1):
        print(f"Epoca {epoca}/{epochs}:")

        # Optimizar
        print(f"  Optimizando prompt (lr={lr})...", flush=True)
        prompt_candidato = optimizar_skill(prompt_mejor, metricas_base, lr_text)

        # Evaluar candidato
        print("  Evaluando prompt candidato:")
        metricas_cand = evaluar_skill(prompt_candidato, casos)
        score_cand = metricas_cand["score_promedio"]
        mejora = score_cand - score_mejor

        print(f"  Score candidato: {score_cand:.1f}/10 (mejora: {mejora:+.1f})")

        if mejora >= VALIDATION_GATE:
            print(f"  Validation gate SUPERADO ({mejora:.1f} >= {VALIDATION_GATE}) — aceptando mejora")
            prompt_mejor  = prompt_candidato
            score_mejor   = score_cand
            metricas_base = metricas_cand
            _write_skill(skill_path, frontmatter, prompt_mejor)
            historial.append({"epoca": epoca, "score": score_cand, "accion": "actualizado", "mejora": mejora})
        else:
            print(f"  Validation gate NO superado ({mejora:.1f} < {VALIDATION_GATE}) — descartando")
            historial.append({"epoca": epoca, "score": score_cand, "accion": "descartado", "mejora": mejora})

        print()

    # Resumen final
    print("=" * 60)
    print(f"SkillOpt completado: {skill_name}")
    print(f"  Score inicial: {score_base:.1f}/10")
    print(f"  Score final:   {score_mejor:.1f}/10")
    print(f"  Mejora total:  {score_mejor - score_base:+.1f}")
    if score_mejor > score_base:
        print(f"  Skill actualizado: {skill_path}")
    else:
        print(f"  Skill sin cambios (ninguna mejora supero el gate de {VALIDATION_GATE})")
    print(f"  Backup original: {backup_path.name}")

    log_path.write_text(json.dumps(historial, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Log: {log_path.name}")


def listar_skills():
    print("Skills disponibles para optimizacion:\n")
    for skill_file in sorted(AGENTS.glob("*.md")):
        name = skill_file.stem
        cases_file = CASES / f"{name}_cases.json"
        tiene_cases = "Si" if cases_file.exists() else "No"

        # Buscar ultimo resultado
        resultados = sorted(RESULTS.glob(f"{name}_*.json"))
        if resultados:
            ultimo = json.loads(resultados[-1].read_text(encoding="utf-8"))
            ultimo_score = ultimo[-1].get("score", "?") if ultimo else "?"
            ultimo_ts = resultados[-1].stem.split("_", 2)[-1]
            print(f"  {name:<20} cases={tiene_cases:<4} ultimo_score={ultimo_score}/10 ({ultimo_ts})")
        else:
            print(f"  {name:<20} cases={tiene_cases:<4} sin historial")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SkillOpt — Auto-optimizacion de agentes")
    parser.add_argument("skill", nargs="?", help="Nombre del skill a optimizar")
    parser.add_argument("--epochs", type=int, default=2, help="Numero de epocas (default: 2)")
    parser.add_argument("--lr", choices=["conservative", "moderate", "aggressive"],
                        default="moderate", help="Learning rate (default: moderate)")
    parser.add_argument("--eval-only", action="store_true", help="Solo evaluar, no optimizar")
    parser.add_argument("--list", action="store_true", help="Listar skills disponibles")
    args = parser.parse_args()

    if args.list or not args.skill:
        listar_skills()
        return

    run_skillopt(args.skill, args.epochs, args.lr, args.eval_only)


if __name__ == "__main__":
    main()
