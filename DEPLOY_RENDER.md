# Despliegue de GrapeSense en Render

> **Estado:** GrapeSense se encuentra desplegado en Render. Esta guía documenta
> la configuración de producción y los pasos necesarios para verificar,
> mantener o recrear el entorno.

Esta guía publica una sola instalación multiempresa compuesta por:

- un servicio web Docker con React y FastAPI;
- una base PostgreSQL administrada;
- un disco persistente para los modelos entrenados por bodega.

La infraestructura se describe en `render.yaml`. No se deben copiar contraseñas ni URLs privadas dentro del repositorio.

## Recursos de producción y costos

El Blueprint define:

- servicio web Docker `0.5c-512mb`;
- PostgreSQL `0.1c-256mb` con 1 GB inicial;
- disco persistente de 1 GB para los modelos.

El disco persistente sólo está disponible para servicios web pagos. Antes de
crear el Blueprint se deben revisar los precios vigentes en Render; este
repositorio no crea recursos ni inicia facturación por sí mismo. La
[referencia oficial de Blueprints](https://render.com/docs/blueprint-spec) define
los identificadores de planes y la [documentación de discos](https://render.com/docs/disks)
explica sus restricciones.

El disco queda asociado a una única instancia del servicio y evita despliegues
sin interrupción. Durante una actualización puede existir una pausa breve hasta
que la nueva instancia supere el control de salud.

## 0. Verificación previa

Desde la raíz del repositorio:

```bash
./scripts/verificar_proyecto.sh
```

Confirmar además que el repositorio no contenga `.env`, respaldos, secretos ni
modelos particulares de una bodega:

```bash
git status --short
git ls-files | grep -E '(^|/)(\.env|backups|\.grapesense_secret|modelos/bodega_)' || true
```

## 1. Publicar el código en GitHub

Confirmar que los cambios estén guardados en la rama que se desplegará y subirlos al repositorio privado. Render volverá a desplegar GrapeSense automáticamente cuando esa rama reciba cambios.

Antes de subir, revisar:

```bash
git status
git diff --check
```

Los archivos `.env`, el secreto local, los modelos generados y la carpeta `venv` están excluidos de Git.

## 2. Crear el Blueprint

1. Ingresar a <https://dashboard.render.com/>.
2. Seleccionar **New → Blueprint**.
3. Conectar el repositorio privado de GrapeSense.
4. Elegir el archivo `render.yaml` de la raíz.
5. Revisar los dos recursos que se crearán:
   - `grapesense`, servicio web;
   - `grapesense-db`, PostgreSQL.
6. Confirmar la creación.

El primer despliegue construye React, instala Python, inicia FastAPI y ejecuta las migraciones al consultar la aplicación. El servicio queda disponible en una dirección similar a `https://grapesense.onrender.com`.

No modificar manualmente `DATABASE_URL`: el Blueprint la obtiene de PostgreSQL.
`GRAPESENSE_SECRET_KEY` también se genera en Render y no debe copiarse al código.
Render solicitará `GRAPESENSE_PLATFORM_ADMIN_PASSWORD` durante la sincronización
del Blueprint. Debe utilizarse una contraseña segura de al menos 10 caracteres;
su valor no queda guardado en GitHub. El nombre y el correo del administrador
global se toman de las demás variables declaradas en `render.yaml`.

## 3. Verificar el despliegue

Comprobar estas direcciones:

```text
https://<servicio>.onrender.com/api/health
https://<servicio>.onrender.com/
```

La verificación de salud debe responder con base conectada y modelo disponible. Si la base está vacía, la página mostrará la configuración de la primera organización.

## 4. Crear una instalación nueva o migrar la local

### Alternativa A: instalación nueva

Abrir la aplicación y completar el asistente inicial. Esta opción crea una plataforma vacía y luego permite importar muestras desde la interfaz.

### Alternativa B: conservar la base local

Crear primero un respaldo local mediante el script incluido:

```bash
./scripts/respaldo_postgresql.sh
```

El archivo y su suma de comprobación se guardan en `backups/render/`, con permisos privados y fuera de Git.

La base de `render.yaml` sólo acepta conexiones desde la red privada de Render. Para restaurar desde la computadora:

1. abrir `grapesense-db` en Render;
2. habilitar temporalmente la IP pública de la computadora en **Network / Inbound IP Rules**;
3. copiar la URL externa de PostgreSQL sin guardarla en ningún archivo;
4. restaurar el respaldo en la base vacía:

```bash
pg_restore --no-owner --no-acl --dbname="URL_EXTERNA_DE_RENDER" backups/render/tesis_uva_FECHA.dump
```

Después de comprobar los datos, eliminar nuevamente la regla pública. La aplicación utiliza internamente `DATABASE_URL`, suministrada de forma automática por Render.

## 5. Modelos existentes

El modelo base forma parte de la imagen y siempre está disponible. Los modelos nuevos se escriben en `/var/data/models`, que corresponde al disco persistente.

El candidato local anterior no se copia automáticamente porque pertenece a la computadora de desarrollo y no está activo. Se puede volver a entrenar desde la plataforma una vez migradas las muestras; el nuevo candidato quedará almacenado de forma persistente en Render.

## 6. Dominio propio

Cuando la dirección `onrender.com` funcione:

1. abrir el servicio `grapesense`;
2. ingresar en **Settings → Custom Domains**;
3. agregar, por ejemplo, `app.grapesense.com.ar`;
4. copiar en el proveedor del dominio los registros DNS indicados por Render;
5. esperar la verificación y el certificado HTTPS automático.

## 7. Copias de seguridad y operación

- Usar un plan PostgreSQL pago; la base gratuita vence y no es apropiada para clientes.
- Revisar periódicamente las copias y la restauración.
- No eliminar el disco `grapesense-models`: contiene los modelos entrenados por bodega.
- Revisar los registros de Render cuando falle una consulta climática o un entrenamiento.
- Probar los roles de cada bodega después de cada cambio relevante.
- Mantener la aplicación y PostgreSQL en la misma región.
- Recordar que el disco persistente permite una sola instancia del servicio.

## 8. Actualizaciones

Una actualización normal consiste en subir cambios a la rama conectada. Render construye una imagen nueva y conserva PostgreSQL y el disco de modelos.

Antes de publicar una actualización:

```bash
python -m py_compile app/backend/api.py app/backend/core/*.py app/backend/ml/*.py app/backend/services/*.py
cd app/frontend && npm ci && npm run build
```

No utilizar el archivo `iniciar.sh` en Render: está pensado exclusivamente para ejecutar GrapeSense en la computadora local.

## 9. Lista de aceptación

Antes de considerar finalizado el despliegue:

- `/api/health` responde `status: ok`;
- se puede crear o restaurar la primera organización;
- los tres roles acceden únicamente a las funciones permitidas;
- una predicción consulta clima y queda almacenada;
- una muestra y un seguimiento pueden crearse, editarse y eliminarse;
- el análisis corresponde al modelo activo de la bodega seleccionada;
- un entrenamiento candidato se conserva después de reiniciar el servicio;
- se realizó y verificó al menos una restauración de respaldo.
