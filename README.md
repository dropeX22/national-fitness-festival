# National Fitness Festival — Sistema de Inscripciones

Sistema completo de inscripciones para el evento de CrossFit por equipos, con
pagos (Yappy), check-in por QR y panel de administración.

## 🚀 Instalación y ejecución (paso a paso)

### 1. Requisitos
- Python 3.10 o superior instalado.

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```
> Si te da error de permisos, en algunos sistemas necesitas:
> `pip install -r requirements.txt --user`

### 3. Configurar variables de entorno (opcional)
```bash
cp .env.example .env
```
Puedes dejar el `.env` vacío en correo y Yappy: el sistema usa **modo
simulado** automáticamente si no encuentra esas credenciales, así puedes
probar todo el flujo sin cuenta real de Yappy ni de Gmail.

### 4. Crear la base de datos
Se crea automáticamente al iniciar el servidor. Si quieres crearla a mano:
```bash
python -c "from app.database import init_db; init_db()"
```

### 5. (Opcional) Cargar 2 equipos de ejemplo
```bash
python seed_datos_ejemplo.py
```
> ⚠️ Corre este comando con el servidor **apagado** (o antes de arrancarlo).
> Si lo corres mientras `python run.py` está activo con auto-reload, puede
> haber una condición de carrera por el archivo SQLite y los datos no
> quedar guardados correctamente. En PostgreSQL (producción) esto no pasa,
> es una particularidad de SQLite con múltiples procesos escribiendo a la vez.

### 6. Ejecutar el servidor
```bash
python run.py
```
o directamente con uvicorn:
```bash
uvicorn app.main:app --reload
```

### 7. Abrir en el navegador
- Página principal: http://localhost:8000
- Inscripción: http://localhost:8000/registro
- Panel admin: http://localhost:8000/admin
- Check-in: http://localhost:8000/checkin
- Documentación automática de la API: http://localhost:8000/docs

## 🗂️ Estructura del proyecto

```
mi_evento/
├── app/
│   ├── main.py         # Arranque de FastAPI y registro de rutas
│   ├── database.py     # Conexión SQLAlchemy + creación de tablas
│   ├── models.py       # Tablas: Evento, Equipo, Atleta, Pago, CheckIn
│   ├── schemas.py       # Validación de datos (Pydantic) + reglas de negocio
│   ├── crud.py          # Funciones que hablan con la base de datos
│   ├── utils.py         # Generación de QR y envío de correos
│   ├── routes/
│   │   ├── public.py    # Inicio, registro, confirmación
│   │   ├── admin.py     # Panel admin, filtros, exportar Excel
│   │   ├── payments.py  # Yappy (real o simulado) + webhook
│   │   └── checkin.py   # Buscar equipo y registrar check-in
│   ├── templates/       # HTMLs (Jinja2 + Bootstrap)
│   └── static/          # CSS, JS y los QR generados
├── requirements.txt
├── .env.example
├── run.py
├── seed_datos_ejemplo.py
└── README.md
```

## ✅ Reglas de negocio implementadas

- Equipos de exactamente 4 personas: 2 hombres y 2 mujeres.
- Cada atleta tiene: nombre, apellido, cédula o pasaporte, fecha de
  nacimiento, género, nacionalidad, talla, box de origen y tipo de
  sangre. Solo el **capitán** llena además email (con confirmación) y
  teléfono — es el contacto principal del equipo.
- Un atleta (por cédula/pasaporte) no puede estar en más de un equipo
  dentro del mismo evento (sí puede repetirse entre ediciones de años
  distintos — ver sección "Eventos anuales").
- El **Atleta 1 siempre es el capitán** (no se elige, es quien llena el
  formulario) — es el único con email (con confirmación) y teléfono.
- El capitán debe aceptar el reglamento y el tratamiento de datos
  personales para poder inscribir al equipo.
- El pago se hace por equipo completo, con dos métodos disponibles:
  **Yappy** o **transferencia bancaria** (ver sección de pagos abajo).
- No hay límite de equipos ni lista de espera.
- Los **participantes** no pueden editar su equipo después de
  inscribirse. El **staff sí puede**, desde `/admin`, corregir
  integrantes o crear equipos manualmente (inscripciones extraordinarias).
- Código único por equipo (`NF-001`, `NF-002`, ...).

## 💳 Métodos de pago: Yappy y Transferencia

El capitán elige, desde la página de confirmación, cómo pagar:

**Yappy:**
- Se pide un **número de teléfono aparte** del teléfono del capitán —
  porque a veces usan el Yappy de otra persona ajena al equipo.
- Como es normal que todavía no tengas cuenta comercial de Yappy, el
  sistema detecta automáticamente si hay credenciales en `.env`:
  - **Sin credenciales (por defecto):** modo simulado, con una pantalla
    de prueba con botones "Confirmar pago" / "Rechazar pago".
  - **Con credenciales (`YAPPY_MERCHANT_ID` y `YAPPY_SECRET_KEY`):** el
    sistema intenta llamar a la API real de Yappy Comercial. Los nombres
    de endpoint/campos en `app/routes/payments.py` (función
    `_crear_orden_yappy_real`) son ilustrativos — ajústalos con la
    documentación oficial que Yappy entrega al afiliarte como comercio.
- El endpoint `/webhook/yappy` recibe notificaciones reales y maneja
  pagos duplicados.

**Transferencia bancaria:**
- Al elegir esta opción, el equipo queda en estado "Pendiente de
  verificación" con un plazo de **72 horas** (configurable en
  `crud.HORAS_PLAZO_VERIFICACION_TRANSFERENCIA`).
- Se envía un **correo 1** al capitán avisando del plazo.
- El staff revisa manualmente el estado de cuenta del banco y, desde
  `/admin`, hace clic en "Verificar transferencia" (escribiendo su
  nombre como responsable).
- Esto marca el pago como confirmado, el equipo pasa a "Pagado", y se
  envía un **correo 2** de confirmación al capitán.
- ⚠️ Los datos bancarios que se muestran en la página de confirmación
  (`app/templates/confirmacion.html`) son un placeholder — reemplázalos
  por los datos reales de la cuenta del evento antes de usarlo en producción.

**Correo interno a la organización:** cada vez que un equipo elige
método de pago (Yappy o transferencia), se manda un correo a
`ADMIN_NOTIFICACION_EMAIL` (.env) avisando qué deben verificar.

## 🛠️ Editar o crear equipos desde el admin

- **Editar** (`/admin/equipo/{id}/editar`): reemplaza los 4 integrantes
  de un equipo ya inscrito. Útil si cambia una persona después de
  inscribirse. Solo el staff tiene acceso (protegido con login).
- **Crear manual** (`/admin/equipo/nuevo`): inscribe un equipo
  directamente desde el panel, sin pasar por el formulario público —
  para inscripciones extraordinarias (ej. alguien que se inscribió por
  WhatsApp). No exige confirmación de email del capitán con el mismo
  rigor que el formulario público, ya que aquí es el staff quien
  transcribe los datos.

## 📧 Correos (vía Brevo)

Usa la **API HTTP de Brevo** (antes Sendinblue) en vez de SMTP
tradicional, porque Render bloquea los puertos SMTP en su plan gratuito.
Configura en `.env`:
```
BREVO_API_KEY=tu-api-key-de-brevo
EMAIL_REMITENTE=correo-verificado-en-brevo@ejemplo.com
ADMIN_NOTIFICACION_EMAIL=correo-del-staff@ejemplo.com
```
Si no configuras `BREVO_API_KEY`/`EMAIL_REMITENTE`, el sistema simula el
envío imprimiendo en consola, sin bloquear la inscripción. Hay 4 correos
distintos en el sistema (`app/utils.py`):
1. Confirmación de inscripción (con QR adjunto)
2. Aviso interno a la organización (al elegir método de pago)
3. Transferencia pendiente (correo 1 del flujo de transferencia)
4. Transferencia confirmada (correo 2, tras verificación manual)

## 📲 Check-in con QR

Cada equipo recibe un QR con el contenido `EQUIPO:<id>:<codigo>`. En la
página `/checkin`, el staff puede:
- Escribir el nombre o código del equipo, **o**
- Pegar el contenido leído por un escáner QR (cualquier app lectora de QR
  del celular funciona; no fue necesario integrar una librería de cámara
  en el navegador para mantenerlo simple).

## 🌐 Despliegue gratuito (opciones fáciles)

No necesitas un servidor complejo. Estas 3 opciones tienen plan gratuito
y son sencillas para un primer proyecto:

1. **Render** (recomendado para empezar)
   - Crea cuenta en render.com → "New Web Service" → conecta tu repo de GitHub.
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Nota: en el plan gratuito el disco se borra en cada deploy, así que
     SQLite no es ideal para producción real ahí; sirve bien para pruebas.

2. **Railway**
   - railway.app → "New Project" → "Deploy from GitHub".
   - Railway detecta Python automáticamente; agrega las variables de
     entorno del `.env` en su panel.

3. **PythonAnywhere**
   - Ideal si quieres algo aún más manual/guiado, con tutoriales en español.
   - Sube el código, crea un virtualenv, instala `requirements.txt` y
     configura la app WSGI apuntando a `app.main:app` (requiere adaptar
     con `a2wsgi` porque PythonAnywhere corre WSGI, no ASGI nativo).

> ⚠️ Para un evento real, considera migrar de SQLite a PostgreSQL cuando
> despliegues en producción (Render y Railway ofrecen PostgreSQL gratis),
> ya que SQLite no maneja bien muchos usuarios escribiendo al mismo tiempo.

## 📅 Eventos anuales (2026, 2027, ...)

El sistema soporta que el mismo atleta compita año tras año, sin que su
cédula quede "atrapada" en el evento anterior:

- La tabla `Evento` tiene un campo `activo`. Solo un evento está activo a
  la vez — es "el evento de este año", al que se conectan las inscripciones nuevas.
- La cédula de un atleta es única **por evento**, no global. Eso significa
  que la misma persona puede inscribirse otra vez el año siguiente, pero
  no puede inscribirse dos veces dentro del mismo evento.

**Cuando termine el evento de este año y quieras abrir el del año
siguiente:**
```bash
python abrir_nuevo_evento.py
```
Edita las variables al inicio del script (nombre, fecha, precio) antes de
correrlo. Esto cierra el evento actual (queda como historial, con sus
equipos y atletas intactos, solo que `activo=False`) y abre uno nuevo que
pasa a recibir las inscripciones nuevas.

> Nota: por ahora, el panel `/admin` muestra equipos de todos los eventos
> juntos (no filtra por evento activo). Si administras varios años en
> paralelo, es un buen candidato a mejora futura — pero no bloquea el uso
> normal de un evento a la vez.

## 🐘 Migrar de SQLite a PostgreSQL (recomendado antes de inscripciones reales)

El proyecto usa SQLite por defecto (archivo `evento.db`), ideal para
desarrollo pero **no persistente en el plan gratuito de Render** (el
disco se borra en cada reinicio del contenedor). Para pasar a PostgreSQL:

1. En el panel de Render, click **"New +"** → **"PostgreSQL"**.
2. Dale un nombre (ej. `nff-db`) y elige el plan **Free** para probar
   (⚠️ se borra automáticamente 30 días después de crearse — sube a un
   plan pago, desde $6/mes, antes de abrir inscripciones reales).
3. Una vez creada, copia el valor de **"Internal Database URL"**.
4. Ve a tu servicio web → pestaña **"Environment"** → agrega:
   ```
   DATABASE_URL = <pega aquí la Internal Database URL>
   ```
5. Guarda — Render redepliega solo. Al arrancar, `init_db()` crea las
   tablas automáticamente en PostgreSQL en vez de en el archivo SQLite.

No hace falta cambiar nada más: el código ya detecta automáticamente si
`DATABASE_URL` es de PostgreSQL o SQLite (ver `app/database.py`), y
corrige por ti el prefijo `postgres://` → `postgresql://` que a veces
entregan los proveedores de base de datos.

> Nota: al migrar, empiezas con una base de datos nueva y vacía — los
> datos que tenías en SQLite no se copian automáticamente. Si ya tienes
> datos reales que necesitas conservar, avisa antes de migrar para
> exportarlos primero.

## 🔒 Autenticación del panel admin y check-in

`/admin` y `/checkin` están protegidos con autenticación HTTP Basic: el
navegador pedirá usuario y contraseña automáticamente la primera vez que
entres. Se configuran en `.env`:

```
ADMIN_USUARIO=admin
ADMIN_CLAVE=cambia-esta-clave
```

**Cambia `ADMIN_CLAVE` antes de subir el proyecto a internet.** Si no
configuras estas variables, el sistema usa `admin` / `changeme` por
defecto — obvio y público en el código, así que no lo dejes así en
producción.

⚠️ HTTP Basic manda las credenciales en cada petición. Es seguro solo si
el sitio corre bajo HTTPS (Render y Railway lo dan gratis automáticamente
al desplegar). Nunca lo uses sobre HTTP plano con datos reales.
