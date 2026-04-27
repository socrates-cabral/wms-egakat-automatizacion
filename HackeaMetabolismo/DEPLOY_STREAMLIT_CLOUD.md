# Deploy a Streamlit Cloud

## Pasos para publicar en Streamlit Community Cloud (gratis)

### 1. Asegurate que el código está en GitHub

```bash
cd C:\ClaudeWork\HackeaMetabolismo
git status
git add .
git commit -m "feat: Supabase REST API + Streamlit Cloud ready"
git push origin main
```

### 2. Ve a Streamlit Cloud

1. https://streamlit.io/cloud
2. Haz click en **"Deploy an app"**
3. Autoriza con GitHub (si no lo has hecho)
4. Selecciona:
   - **Repository:** `socrates-cabral/ClaudeWork-...`
   - **Branch:** `main`
   - **Main file path:** `HackeaMetabolismo/dashboard/app.py`

### 3. Configura secretos (variables de entorno)

En Streamlit Cloud dashboard, ve a **Settings** → **Secrets**

Agrega:

```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-proj-...
SUPABASE_URL=https://rqaawisuwsvwpywlwnia.supabase.co
SUPABASE_KEY=sb_publishable_...
OPENFOODFACTS_URL=https://world.openfoodfacts.org/api/v2
USDA_API_KEY=DEMO_KEY
DB_PATH=data/hackea_metabolismo.db
STREAMLIT_PORT=8505
ENV=prod
APP_NAME=Hackea tu Metabolismo con IA
```

### 4. Deploy

Streamlit automáticamente:
- Instala `requirements.txt`
- Ejecuta `dashboard/app.py`
- Asigna URL pública: `https://[tu-app].streamlit.app`

### 5. Auto-redeploy en cada push

Cada `git push origin main` automáticamente redeploy la app.

---

## Troubleshooting

### "Module not found: src"
**Solución:** Asegúrate que la ruta en Streamlit Cloud es:
```
HackeaMetabolismo/dashboard/app.py
```
(no solo `dashboard/app.py`)

### "SUPABASE_URL/SUPABASE_KEY not found"
**Solución:** Verifica que los secretos estén en Settings → Secrets (no en .env)

### "Connection timeout to Supabase"
**Solución:** REST API funciona, pero si falla → fallback a SQLite (/tmp/hackea_metabolismo.db en cloud)

---

## URL de la app

Una vez deployado, accede en:
```
https://hackea-metabolismo.streamlit.app
```

(o el nombre custom que asignes)
