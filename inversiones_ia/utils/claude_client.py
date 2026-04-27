"""
claude_client.py — Cliente de IA multi-proveedor con fallback automático.
Orden de fallback: Anthropic Claude → OpenAI GPT-4o → Google Gemini
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

# Modelos por proveedor
MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai":    "gpt-4o",
    "google":    "gemini-2.0-flash",
}

# Nombres legibles para la UI
PROVIDER_LABELS = {
    "anthropic": "Anthropic Claude",
    "openai":    "OpenAI GPT-4o",
    "google":    "Google Gemini",
}


def get_available_providers() -> list[str]:
    """Retorna los proveedores con API key configurada."""
    available = []
    if os.getenv("ANTHROPIC_API_KEY") and os.getenv("ANTHROPIC_API_KEY") != "tu_api_key_aqui":
        available.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")
    if os.getenv("GOOGLE_API_KEY"):
        available.append("google")
    return available


class ClaudeClient:
    """
    Cliente unificado. Acepta provider="anthropic"|"openai"|"google"|"auto".
    Con provider="auto" intenta en orden hasta que uno responde.
    """

    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self.available = get_available_providers()
        if not self.available:
            raise ValueError(
                "No hay API keys configuradas. Edita el archivo .env."
            )

    def analyze(self, prompt: str, system: str, use_web_search: bool = True) -> str:
        """
        Llama al proveedor seleccionado.
        Si falla por cuota/error de billing, prueba el siguiente en la cadena.
        Retorna (texto_respuesta, proveedor_usado).
        """
        # Idioma y Modo Simple: ajustar el system prompt globalmente
        try:
            import streamlit as st

            # ── Idioma ──────────────────────────────────────────────────
            lang = st.session_state.get("lang_code", "es")
            if lang == "es":
                system = system + (
                    "\n\nIMPORTANTE — IDIOMA: Responde SIEMPRE en español, "
                    "independientemente del idioma en que estén los datos de mercado "
                    "o el prompt. Usa terminología financiera en español."
                )
            else:
                system = system + (
                    "\n\nIMPORTANT — LANGUAGE: Always respond in English, "
                    "regardless of the language of the market data or prompt."
                )

            # ── Modo Simple ─────────────────────────────────────────────
            if st.session_state.get("modo_simple", False):
                if lang == "es":
                    system = system + (
                        "\n\nADEMÁS — MODO LENGUAJE SIMPLE ACTIVADO: "
                        "El usuario es un principiante absoluto en inversiones. "
                        "Usa lenguaje muy simple y cotidiano, sin jerga financiera. "
                        "Si usas un término técnico, explícalo con una analogía simple. "
                        "Usa emojis para hacer el texto más amigable y visual. "
                        "Usa ejemplos con números reales y situaciones cotidianas. "
                        "Sé alentador, positivo y motivador. "
                        "Prefiere párrafos cortos y directos."
                    )
                else:
                    system = system + (
                        "\n\nALSO — SIMPLE LANGUAGE MODE ACTIVE: "
                        "The user is an absolute beginner in investing. "
                        "Use very simple everyday language, no financial jargon. "
                        "If you use a technical term, explain it immediately with a simple analogy. "
                        "Use emojis to make the text friendly and visual. "
                        "Use examples with real numbers and everyday situations. "
                        "Be encouraging, positive and motivating."
                    )
        except Exception:
            pass  # Si streamlit no está disponible, continuar sin ajustes

        if self.provider == "auto":
            order = self.available
        elif self.provider in self.available:
            # Proveedor manual: si falla, fallback al resto
            order = [self.provider] + [p for p in self.available if p != self.provider]
        else:
            order = self.available

        last_error = None
        for prov in order:
            try:
                result = self._call(prov, prompt, system, use_web_search)
                return result, prov
            except _QuotaError as e:
                last_error = e
                continue  # Siguiente proveedor
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(
            f"Todos los proveedores fallaron. Último error: {last_error}"
        )

    # ── Llamadas específicas por proveedor ─────────────────────────────────

    def _call(self, provider: str, prompt: str, system: str, use_web_search: bool) -> str:
        if provider == "anthropic":
            return self._call_anthropic(prompt, system, use_web_search)
        elif provider == "openai":
            return self._call_openai(prompt, system)
        elif provider == "google":
            return self._call_google(prompt, system)
        raise ValueError(f"Proveedor desconocido: {provider}")

    def _call_anthropic(self, prompt: str, system: str, use_web_search: bool) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)
        kwargs = {
            "model": MODELS["anthropic"],
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if use_web_search:
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
            try:
                response = client.beta.messages.create(
                    **kwargs,
                    betas=["interleaved-thinking-2025-05-14"],
                )
            except Exception:
                response = client.messages.create(**kwargs)
        else:
            response = client.messages.create(**kwargs)

        parts = []
        for block in getattr(response, "content", []):
            if getattr(block, "type", "") == "text":
                text = getattr(block, "text", "")
                if text:
                    parts.append(text)
        result = "\n".join(parts)
        if not result:
            raise RuntimeError("Respuesta vacía de Anthropic")
        return result

    def _call_openai(self, prompt: str, system: str) -> str:
        try:
            from openai import OpenAI, RateLimitError, AuthenticationError
        except ImportError:
            raise RuntimeError("openai no instalado. Corre: py -m pip install openai")

        api_key = os.getenv("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=MODELS["openai"],
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content or "Sin respuesta de OpenAI"
        except RateLimitError as e:
            raise _QuotaError(f"OpenAI cuota agotada: {e}")
        except AuthenticationError as e:
            raise _QuotaError(f"OpenAI API key inválida: {e}")

    def _call_google(self, prompt: str, system: str) -> str:
        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError("google-generativeai no instalado. Corre: py -m pip install google-generativeai")

        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=MODELS["google"],
            system_instruction=system,
        )
        try:
            response = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": 4096},
            )
            return response.text or "Sin respuesta de Google Gemini"
        except Exception as e:
            err = str(e).lower()
            if "quota" in err or "billing" in err or "resource exhausted" in err:
                raise _QuotaError(f"Google cuota agotada: {e}")
            raise


class _QuotaError(Exception):
    """Error de cuota/billing — indica al cliente que pruebe el siguiente proveedor."""
    pass
