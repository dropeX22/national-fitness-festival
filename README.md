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
- Un atleta (por cédula) no puede estar en más de un equipo ni repetirse
  en otra categoría (se valida contra TODOS los equipos del evento).
- El capitán debe aceptar el reglamento para poder inscribir al equipo.
- El pago se hace por equipo completo; si el pago no está confirmado,
  el equipo queda en estado **Pendiente** y no puede hacer check-in.
- No hay límite de equipos ni lista de espera.
- Los integrantes no se pueden editar después de inscribirse (no existe
  ruta de edición a propósito).
- Código único por equipo (`NF-001`, `NF-002`, ...).

## 💳 Integración con Yappy

Como es normal que todavía no tengas una cuenta comercial de Yappy, el
sistema detecta automáticamente si hay credenciales en `.env`:

- **Sin credenciales (por defecto):** modo simulado. Al hacer clic en
  "Pagar", se abre una pantalla de prueba con botones "Confirmar pago" /
  "Rechazar pago" que dispara la misma lógica que usaría el webhook real.
- **Con credenciales (`YAPPY_MERCHANT_ID` y `YAPPY_SECRET_KEY`):** el
  sistema intenta llamar a la API real de Yappy Comercial. Los nombres de
  endpoint/campos en `app/routes/payments.py` (función
  `_crear_orden_yappy_real`) son ilustrativos — debes ajustarlos con la
  documentación oficial que Yappy entrega al afiliarte como comercio.
- El endpoint `/webhook/yappy` recibe las notificaciones reales de pago y
  maneja pagos duplicados (si Yappy reenvía la misma notificación, no se
  duplica nada).

## 📧 Correos

Usa `yagmail` con una **contraseña de aplicación de Gmail** (no tu
contraseña normal; se genera en la configuración de seguridad de tu
cuenta de Google). Si no configuras `EMAIL_REMITENTE` y `EMAIL_CLAVE_APP`
en `.env`, el sistema simplemente imprime en consola lo que habría
enviado, sin bloquear la inscripción.

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
